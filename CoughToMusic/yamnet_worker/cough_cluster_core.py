import os
import librosa
import numpy as np
import noisereduce
import resampy
import tensorflow as tf
import soundfile as sf
from scipy.signal import resample
from scipy.spatial.distance import cdist
import glob
from keras_yamnet.preprocessing import preprocess_input
from keras_yamnet import params
from yamnet_loader import get_yamnet_model

import pandas as pd

# === 模型與參數 ===

def fast_load(path, sr=None):
    y, orig_sr = sf.read(path)
    if y.ndim > 1:
        y = y.mean(axis=1)  # convert to mono
    if sr and sr != orig_sr:
        y = resample(y, int(len(y) * sr / orig_sr))
        return y, sr
    return y, orig_sr

SAMPLE_RATE = 16000
WINDOW_DURATION = 0.96
EXAMPLE_HOP_SECONDS = 0.48
EXAMPLE_WINDOW_SECONDS = 0.96
ONSET_THRESHOLD = 0.2
TOP_K_ONSETS = 2
#DIST_THRESHOLD = 0.12
DIST_THRESHOLD = 0.24
MAX_CLUSTERS = 2
DISTANCE_METRIC = 'cosine'
# Parameters

MAX_CLUSTERS = 2
MIN_ONSET_DISTANCE = 0.4
PRE_DURATION = 0.03
OVERLAP_ALLOWANCE = 0.1

def waveform_to_examples(data, sample_rate):
    # 若長度不足一個 window，自動補零到一個 window 長度
    min_len = int(round(params.SAMPLE_RATE * EXAMPLE_WINDOW_SECONDS))
    if sample_rate != params.SAMPLE_RATE:
        data = resampy.resample(data, sample_rate, params.SAMPLE_RATE)
    if len(data) < min_len:
        # 補零到 min_len
        data = np.pad(data, (0, min_len - len(data)), mode='constant')
    data = data / np.abs(data).max()
    n_samples = len(data)
    hop_length_samples = int(round(params.SAMPLE_RATE * EXAMPLE_HOP_SECONDS))
    window_length_samples = int(round(params.SAMPLE_RATE * EXAMPLE_WINDOW_SECONDS))
    spectrogram = []
    for start in range(0, n_samples - window_length_samples + 1, hop_length_samples):
        patch = data[start:start + window_length_samples]
        mel = preprocess_input(patch, sr=params.SAMPLE_RATE)
        if mel.shape[0] < 96:
            pad_width = 96 - mel.shape[0]
            mel = np.pad(mel, ((0, pad_width), (0, 0)), mode='constant')
        elif mel.shape[0] > 96:
            mel = mel[:96]
        spectrogram.append(mel)
    return np.array(spectrogram)


def detect_onsets(audio_data, sr, threshold=0.2, top_k=3):
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sr)
    onset_env = (onset_env - np.min(onset_env)) / (np.max(onset_env) - np.min(onset_env) + 1e-9)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_times = librosa.frames_to_time([
        f for f in onset_frames if onset_env[f] > threshold
    ], sr=sr)
    if not onset_times.any():
        return []
    energies = [np.sum(audio_data[int(t * sr):int(t * sr) + int(0.2 * sr)] ** 2) for t in onset_times]
    top_indices = np.argsort(energies)[::-1][:top_k]
    return [min([onset_times[ i] for i in top_indices])]


def extract_feature_from_audio(audio_data, sr):
    yamnet_model = get_yamnet_model()
    if len(audio_data) < int(WINDOW_DURATION * sr):
        return None
    y = noisereduce.reduce_noise(y=audio_data, sr=sr)
    y = np.nan_to_num(y)
    onsets = detect_onsets(y, sr, threshold=ONSET_THRESHOLD, top_k=TOP_K_ONSETS)
    if not onsets:
        return None
    embeddings = []
    for t in onsets:
        start = int(t * sr)
        window = y[start:start + int(WINDOW_DURATION * sr)]
        if len(window) < int(WINDOW_DURATION * sr):
            continue
        mels = waveform_to_examples(window, sr)
        mels = mels.astype(np.float32)  # <--- 強制 float32
        preds = yamnet_model(mels)
        embeddings.append(tf.reduce_mean(preds, axis=0).numpy())
    return np.mean(embeddings, axis=0) if embeddings else None


class CoughClusterManager_1:
    def __init__(self, personal_center, clusters, threshold=0.15, max_clusters=5, k=3, metric='cosine'):
        self.personal_center = personal_center
        self.clusters = clusters
        self.threshold = threshold
        self.max_clusters = max_clusters
        self.k = k
        self.metric = metric

    def _knn_avg_distance(self, vec, cluster):
        if not cluster:
            return np.inf
        dists = cdist([vec], cluster, metric=self.metric)[0]
        return np.mean(np.sort(dists)[:min(self.k, len(dists))])

    def assign_cluster(self, feature_vec):
        if self.personal_center is not None:
            dist = cdist([feature_vec], [self.personal_center], metric=self.metric)[0][0]
            if dist < self.threshold:
                return 0
        best_id, min_dist = -1, float('inf')
        for cid, cluster in self.clusters.items():
            dist = self._knn_avg_distance(feature_vec, cluster)
            if dist < min_dist:
                best_id, min_dist = cid, dist
        if min_dist < self.threshold:
            self.clusters[best_id].append(feature_vec)
            return best_id
        new_id = max(self.clusters.keys(), default=0) + 1
        self.clusters[new_id] = [feature_vec]
        return new_id


def cluster_audio(audio_path, sample_rate, all_cough_file_path, csv_file_path, template_path_dir):
    print(f"[cluster_audio] Start clustering for audio: {audio_path}")
    
    user_cough_list = []
    clusters = {}

    if os.path.exists(csv_file_path):
        df = pd.read_csv(csv_file_path)
        print(f"[cluster_audio] Found CSV with {len(df)} rows")
        for index, row in df.iterrows():
            if str(row.get("clusterID")) == "0":
                filename = f"{row.get('time')}.wav"
                filepath = os.path.join(all_cough_file_path, filename)
                if os.path.exists(filepath):
                    user_cough_list.append(filepath)
                else:
                    print(f"[cluster_audio] Missing user file: {filepath}")
    else:
        print(f"[cluster_audio] CSV file not found: {csv_file_path}")
        return "1"

    print(f"[cluster_audio] Collected {len(user_cough_list)} user cough files")

    template_features = []
    for file in os.listdir(template_path_dir):
        if file.endswith(".wav"):
            path = os.path.join(template_path_dir, file)
            try:
                y, sr = fast_load(path, sr=sample_rate)
                feat = extract_feature_from_audio(y, sample_rate)
                if feat is not None:
                    template_features.append(feat)
                else:
                    print(f"[cluster_audio] Feature is None for template: {file}")
            except Exception as e:
                print(f"[cluster_audio] Failed to load template {file}: {e}")

    print(f"[cluster_audio] Extracted {len(template_features)} template features")

    user_features = []
    for filepath in user_cough_list:
        try:
            y, sr = fast_load(filepath, sr=sample_rate)
            feat = extract_feature_from_audio(y, sample_rate)
            if feat is not None:
                user_features.append(feat)
            else:
                print(f"[cluster_audio] Feature is None for user file: {filepath}")
        except Exception as e:
            print(f"[cluster_audio] Failed to load user cough: {filepath}, error: {e}")

    print(f"[cluster_audio] Extracted {len(user_features)} user features")

    all_features = template_features + user_features
    if all_features:
        personal_center = np.mean(all_features, axis=0)
        print(f"[cluster_audio] Computed personal center with shape {personal_center.shape}")
    else:
        personal_center = None
        print(f"[cluster_audio] No features available to compute personal center")

    try:
        y, sr = fast_load(audio_path, sr=sample_rate)
        print(f"[cluster_audio] Loaded target audio with length {len(y)} samples")
        target_feature = extract_feature_from_audio(y, sample_rate)
        if target_feature is None:
            print("[cluster_audio] Failed to extract target feature, returning default cluster ID 1")
            return "1"
        print(f"[cluster_audio] Extracted target feature shape: {target_feature.shape}")
    except Exception as e:
        print(f"[cluster_audio] Failed to extract target feature: {e}, returning default cluster ID 1")
        return "1"

    print(f"[cluster_audio] Initializing CoughClusterManager")
    cluster_manager = CoughClusterManager_1(
        personal_center=personal_center,
        clusters=clusters,
        threshold=DIST_THRESHOLD,
        max_clusters=MAX_CLUSTERS,
        metric=DISTANCE_METRIC
    )

    assigned_cluster = cluster_manager.assign_cluster(target_feature)
    print(f"[cluster_audio] Assigned to cluster {assigned_cluster}")

    return str(assigned_cluster)


    

def normalization(data):
    return (data - np.min(data)) / (np.max(data) - np.min(data) + 1e-6)

def waveform_to_examples(data, sample_rate):
    if sample_rate != params.SAMPLE_RATE:
        data = resampy.resample(data, sample_rate, params.SAMPLE_RATE)
    data = data / np.abs(data).max()
    hop = int(round(params.SAMPLE_RATE * EXAMPLE_HOP_SECONDS))
    win = int(round(params.SAMPLE_RATE * EXAMPLE_WINDOW_SECONDS))
    spec = []
    for i in range(0, len(data) - win + 1, hop):
        mel = preprocess_input(data[i:i+win], sr=params.SAMPLE_RATE)
        mel = np.pad(mel, ((0, max(0, 96 - mel.shape[0])), (0,0)), mode='constant')[:96]
        spec.append(mel)
    return np.array(spec, dtype=np.float32)

def detect_onsets_for_plot(audio_data, sr, threshold=0.2, min_distance=MIN_ONSET_DISTANCE):
    onset_env = normalization(librosa.onset.onset_strength(y=audio_data, sr=sr))
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    filtered, last = [], -np.inf
    for t in onset_times:
        if t - last >= min_distance and onset_env[librosa.time_to_frames(t, sr=sr)] > threshold:
            filtered.append(t); last = t
    return np.array(filtered)

def extract_file_feature(audio_file):

    yamnet_model = get_yamnet_model()
    try:
        y, sr = fast_load(audio_file, sr=SAMPLE_RATE)
        y = noisereduce.reduce_noise(y=np.nan_to_num(y), sr=sr)
        onset_times = detect_onsets_for_plot(y, sr)
        if len(onset_times) == 0:
            return None
        win = int(WINDOW_DURATION * sr)

        # Get energy-based top-k segments
        energies = []
        for t in onset_times:
            s = int(t * sr)
            patch = y[s:s+win]
            if len(patch) < win:
                continue
            energy = np.sqrt(np.mean(patch**2))
            energies.append((t, energy))

        if not energies:
            return None

        # Get top-k energy segments
        top_k = sorted(energies, key=lambda x: x[1], reverse=True)[:TOP_K_ONSETS]
        top_k_sorted_by_time = sorted(top_k, key=lambda x: x[0])
        t, _ = top_k_sorted_by_time[0]

        # Extract features
        s = int(t * sr)
        patch = y[s:s+win]
        mel = waveform_to_examples(patch, sr)
        emb = tf.reduce_mean(yamnet_model(mel), axis=0).numpy()
        return emb

    except Exception as e:
        print(f"[Error] Failed to extract from {audio_file}: {e}")
        return None

class CoughClusterManager_2:
    def __init__(self, personal_center=None, max_clusters=MAX_CLUSTERS, distance_threshold=DIST_THRESHOLD, k=3, metric=DISTANCE_METRIC):
        self.clusters = []
        self.personal_center = personal_center
        self.threshold = distance_threshold
        self.k = k
        self.metric = metric

    def _knn_avg_distance(self, vec, cl):
        if not cl:
            return np.inf
        d = cdist([vec], cl, metric=self.metric)[0]
        return np.mean(np.sort(d)[:min(self.k, len(d))])

    def add_feature(self, vec):
        if self.personal_center is not None:
            d0 = cdist([vec], [self.personal_center], metric=self.metric)[0][0]
            if d0 < self.threshold:
                return 0
        if not self.clusters:
            self.clusters.append([vec])
            return 1
        best_i, best_d = -1, np.inf
        for i, cl in enumerate(self.clusters):
            d = self._knn_avg_distance(vec, cl)
            if d < best_d:
                best_i, best_d = i, d
        if best_d < self.threshold:
            self.clusters[best_i].append(vec)
            return best_i + 1
        if len(self.clusters) >= MAX_CLUSTERS - 1:
            self._merge_nearest_clusters()
        self.clusters.append([vec])
        return len(self.clusters)

    def predict_cluster(self, vec):
        if self.personal_center is not None:
            d0 = cdist([vec], [self.personal_center], metric=self.metric)[0][0]
            if d0 < self.threshold:
                return 0
        if not self.clusters:
            return 1
        best_i, best_d = -1, np.inf
        for i, cl in enumerate(self.clusters):
            d = self._knn_avg_distance(vec, cl)
            if d < best_d:
                best_i, best_d = i, d
        if best_d < self.threshold:
            return best_i + 1
        return len(self.clusters) + 1

    def _merge_nearest_clusters(self):
        md, pair = np.inf, (-1, -1)
        for i in range(len(self.clusters)):
            for j in range(i + 1, len(self.clusters)):
                d = cdist([np.mean(self.clusters[i], axis=0)], [np.mean(self.clusters[j], axis=0)], metric=self.metric)[0][0]
                if d < md:
                    md, pair = d, (i, j)
        self.clusters[pair[0]].extend(self.clusters[pair[1]])
        del self.clusters[pair[1]]

def classify_cough_file(cough_wav_path, user_data_path, template_data_path, strict_mode=True):
    """
    Classify a cough.wav file to determine if it contains user's cough, non-user's cough, or both.
    
    Args:
        cough_wav_path: Path to the cough.wav file to classify
        user_data_path: Path to directory containing user's cough samples
        template_data_path: Path to directory containing template cough samples
        strict_mode: If True, use stricter thresholds for classification
    
    Returns:
        dict: Classification result with keys:
            - 'has_user_cough': bool
            - 'has_non_user_cough': bool
            - 'user_segments': list of (start, end) tuples in seconds
            - 'non_user_segments': list of (start, end) tuples in seconds
            - 'total_duration': float (total cough duration in seconds)
    """
    yamnet_model = get_yamnet_model()
    
    # Adjust thresholds for strict mode
    if strict_mode:
        global DIST_THRESHOLD
        DIST_THRESHOLD = 0.24  # Stricter threshold
    
    # Load template features
    template_feats = [extract_file_feature(f) for f in glob.glob(os.path.join(template_data_path, "*.wav"))]
    template_feats = [f for f in template_feats if f is not None]
    if not template_feats:
        return {'error': 'No valid template features found'}
    
    # Load user features
    manager = CoughClusterManager_2(personal_center=None)
    user_feats = []
    for f in sorted(glob.glob(os.path.join(user_data_path, "*.wav"))):
        feat = extract_file_feature(f)
        if feat is not None:
            user_feats.append(feat)
    
    if user_feats:
        manager.personal_center = np.mean(user_feats, axis=0)
        print(f"User_data: {len(user_feats)} files, personal center set")
    
    # Process the cough file
    y, sr = fast_load(cough_wav_path, sr=SAMPLE_RATE)

    # 裁切音訊：只取前 4 秒
    max_duration_sec = 4
    max_samples = int(sr * max_duration_sec)
    y = y[:max_samples]

    y = noisereduce.reduce_noise(y=np.nan_to_num(y), sr=sr)
    onset_times = detect_onsets_for_plot(y, sr)
    
    if len(onset_times) == 0:
        print("No cough onsets detected.")
        return {
            'has_user_cough': False,
            'has_non_user_cough': False,
            'user_segments': [],
            'non_user_segments': [],
            'total_duration': 0.0
        }
    
    total_duration = WINDOW_DURATION
    expected_len = int(total_duration * sr)
    segs = []
    
    for idx, onset in enumerate(onset_times):
        start_time = max(0.0, onset - PRE_DURATION)
        end_time = onset + (total_duration - PRE_DURATION)
        
        s_exp = int(start_time * sr)
        e_exp = int(end_time * sr)
        
        patch = y[s_exp:e_exp]
        if len(patch) < expected_len:
            patch = np.pad(patch, (0, expected_len - len(patch)))
        
        mel = waveform_to_examples(patch, sr)
        emb = tf.reduce_mean(yamnet_model(mel), axis=0).numpy()
        cid = manager.add_feature(emb)
        
        print(f"Segment {idx+1}: cluster {cid} at time {onset:.3f}")
        segs.append({'cid': cid, 'start': s_exp, 'end': e_exp})
    
    # Merge segments by cluster ID
    def merge_segments_by_cid(segs, target_cid):
        merged = []
        current = None
        for seg in segs: 
            if seg['cid'] != target_cid:
                continue
            if current is None:
                current = {'start': seg['start'], 'end': seg['end']}
            elif seg['start'] - current['end'] <= int(OVERLAP_ALLOWANCE * sr):
                current['end'] = max(current['end'], seg['end'])
            else:
                merged.append((current['start'], current['end']))
                current = {'start': seg['start'], 'end': seg['end']}
        if current is not None:
            merged.append((current['start'], current['end']))
        return merged
    
    user_segs = merge_segments_by_cid(segs, target_cid=0)
    non_user_segs = merge_segments_by_cid(segs, target_cid=1)

    def remove_overlapping_segments(primary, secondary, sr):
        cleaned = []
        for s2, e2 in secondary:
            overlap_found = False
            new_segments = [(s2, e2)]

            for s1, e1 in primary:
                temp = []
                for ns, ne in new_segments:
                    if e1 <= ns or s1 >= ne:
                        temp.append((ns, ne))  # no overlap
                    else:
                        # 有重疊，切出非重疊的左右段
                        if ns < s1:
                            temp.append((ns, min(ne, s1)))
                        if ne > e1:
                            temp.append((max(ns, e1), ne))
                        overlap_found = True
                new_segments = temp

            cleaned.extend(new_segments)
        return cleaned 

    # === 合併、排除重疊 ===
    user_segs = merge_segments_by_cid(segs, target_cid=0)
    non_user_segs = merge_segments_by_cid(segs, target_cid=1)
    user_segs = remove_overlapping_segments(non_user_segs, user_segs, sr)

    # === 製作遮罩 ===
    mask_u = np.zeros_like(y)
    mask_n = np.zeros_like(y)

    for s, e in user_segs:
        mask_u[s:e] = 1
    for s, e in non_user_segs:
        mask_n[s:e] = 1

    # === 輸出音檔 ===
    user_segments_sec = y * mask_u
    non_user_segments_sec = y * mask_n

    print(f"User segments: {len(user_segs)} segments, Non-user segments: {len(non_user_segs)} segments")
    result = {
        'has_user_cough': len(user_segs) > 0,
        'has_non_user_cough': len(non_user_segs) >= 2,
        'user_output': user_segments_sec,
        'non_user_output': non_user_segments_sec, 
        'sample_rate': sr
    }
    print(f"Classification result: {result}")
    
    return result

