import os
import glob
import librosa
import numpy as np
import noisereduce
import tensorflow as tf
import resampy
import soundfile as sf
from scipy.spatial.distance import cdist
from .keras_yamnet import params
from .keras_yamnet.yamnet import YAMNet
from .keras_yamnet.preprocessing import preprocess_input

# Parameters
SAMPLE_RATE = 16000
WINDOW_DURATION = 0.96
EXAMPLE_HOP_SECONDS = 0.48
EXAMPLE_WINDOW_SECONDS = 0.96
MAX_CLUSTERS = 2
DIST_THRESHOLD = 0.24
DISTANCE_METRIC = 'cosine'
TOP_K_ONSETS = 3
MIN_ONSET_DISTANCE = 0.4
PRE_DURATION = 0.03
OVERLAP_ALLOWANCE = 0.1

# Load YAMNet model
yamnet_model = YAMNet(weights='C:/Users/DreamalityLab/Desktop/jayden/CoughDjangoServer/CoughToMusic/lib/keras_yamnet/yamnet.h5')

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
    return np.array(spec)

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
    try:
        y, sr = librosa.load(audio_file, sr=SAMPLE_RATE)
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

class CoughClusterManager:
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
    
    # Adjust thresholds for strict mode
    if strict_mode:
        global DIST_THRESHOLD
        DIST_THRESHOLD = 0.36  # Stricter threshold
    
    # Load template features
    template_feats = [extract_file_feature(f) for f in glob.glob(os.path.join(template_data_path, "*.wav"))]
    template_feats = [f for f in template_feats if f is not None]
    if not template_feats:
        return {'error': 'No valid template features found'}
    
    # Load user features
    manager = CoughClusterManager(personal_center=None)
    user_feats = []
    for f in sorted(glob.glob(os.path.join(user_data_path, "*.wav"))):
        feat = extract_file_feature(f)
        if feat is not None:
            user_feats.append(feat)
    
    if user_feats:
        manager.personal_center = np.mean(user_feats, axis=0)
        print(f"User_data: {len(user_feats)} files, personal center set")
    
    # Process the cough file
    y, sr = librosa.load(cough_wav_path, sr=SAMPLE_RATE)

    # 裁切音訊：只取前 4 秒
    max_duration_sec = 4
    max_samples = int(sr * max_duration_sec)
    y = y[:max_samples]

    y = noisereduce.reduce_noise(y=np.nan_to_num(y), sr=sr)
    onset_times = detect_onsets_for_plot(y, sr)
    
    if len(onset_times) == 0:
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
    # # Convert to seconds
    # user_segments_sec = [(s/sr, e/sr) for s, e in user_segs]
    # non_user_segments_sec = [(s/sr, e/sr) for s, e in non_user_segs]
    
    # total_duration_sec = sum(e - s for s, e in user_segments_sec + non_user_segments_sec)
    
    # user_output = np.concatenate([y[int(s * sr):int(e * sr)] for s, e in user_segments_sec]) if user_segments_sec else np.array([])
    # nonuser_output = np.concatenate([y[int(s * sr):int(e * sr)] for s, e in non_user_segments_sec]) if non_user_segments_sec else np.array([])
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


    result = {
        'has_user_cough': len(user_segs) > 0,
        'has_non_user_cough': len(non_user_segs) >= 1,
        'user_output': user_segments_sec,
        'non_user_output': non_user_segments_sec, 
        'sample_rate': sr
    }
    
    return result

# Example usage function
def classify_cough_example():
    result = classify_cough_file(
        cough_wav_path="cough.wav",
        user_data_path="User_data",
        template_data_path="template",
        strict_mode=True
    )
    
    print("Classification Result:")
    print(f"Contains user cough: {result['has_user_cough']}")
    print(f"Contains non-user cough: {result['has_non_user_cough']}")
    print(f"User segments: {result['user_segments']}")
    print(f"Non-user segments: {result['non_user_segments']}")
    print(f"Total cough duration: {result['total_duration']:.2f} seconds")
    
    return result 