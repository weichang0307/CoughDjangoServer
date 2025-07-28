import os
import csv
import librosa
import numpy as np
import noisereduce
import resampy
import tensorflow as tf
from scipy.spatial.distance import cdist

from .keras_yamnet import params
from .keras_yamnet.yamnet import YAMNet
from .keras_yamnet.preprocessing import preprocess_input

import pandas as pd

# === 模型與參數 ===
yamnet_model = YAMNet(weights='C:/Users/DreamalityLab/Desktop/jayden/CoughDjangoServer/CoughToMusic/lib/keras_yamnet/yamnet.h5')

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


class CoughClusterManager:
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
    
    # === 讀取 CSV 與歸為使用者的音檔 ===
    user_cough_list = []
    clusters = {}


    if os.path.exists(csv_file_path):
        df = pd.read_csv(csv_file_path)
        for index, row in df.iterrows():
            # 如果 clusterID 是 "1"
            if str(row["clusterID"]) == "0":
                # 取得 time 欄位並加上 .wav
                filename = f"{row['time']}.wav"
                filepath = os.path.join(all_cough_file_path, filename)
                user_cough_list.append(filepath)

    else:
        print(f"CSV 檔案 {csv_file_path} 不存在")
        return


    # === 讀取 template 音檔並提取特徵 ===
    template_features = []
    for file in os.listdir(template_path_dir):
        if file.endswith(".wav"):
            path = os.path.join(template_path_dir, file)
            y, _ = librosa.load(path, sr=sample_rate)
            feat = extract_feature_from_audio(y, sample_rate)
            if feat is not None:
                template_features.append(feat)

    # === 使用者咳嗽音檔提取特徵 ===
    user_features = []
    for filepath in user_cough_list:
        y, _ = librosa.load(filepath, sr=sample_rate)
        feat = extract_feature_from_audio(y, sample_rate)
        if feat is not None:
            user_features.append(feat)

    # === 動態個人中心 ===
    all_features = template_features + user_features
    personal_center = np.mean(all_features, axis=0) if all_features else None



    # === 擷取新音檔的特徵 ===
    try:
        y, _ = librosa.load(audio_path, sr=sample_rate)
        target_feature = extract_feature_from_audio(y, sample_rate)
        if target_feature is None:
            raise ValueError("無法從音訊中提取有效特徵")
    except Exception as e:
        raise ValueError(f"處理音訊檔案 {audio_path} 時發生錯誤: {e}")
    


    # === 分群管理器建立與分群 ===
    cluster_manager = CoughClusterManager(
        personal_center=personal_center,
        clusters=clusters,
        threshold=DIST_THRESHOLD,
        max_clusters=MAX_CLUSTERS,
        metric=DISTANCE_METRIC
    )


    assigned_cluster = cluster_manager.assign_cluster(target_feature)

    """
    # === 寫入新記錄到 CSV ===
    
    if os.path.exists(csv_file_path):
        df = pd.read_csv(csv_file_path)
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]

        # 找到對應這個音檔的那一列
        match_idx = df[df['time'] == audio_name].index
        if not match_idx.empty:
            df.at[match_idx[0], 'clusterID'] = str(assigned_cluster)
            print(f"更新 {audio_name}.wav 的 clusterID 為 {assigned_cluster}")
        else:
            print(f"找不到對應 audio_path={audio_name} 的列")

        # ✅ 存回 CSV
        df.to_csv(csv_file_path, index=False)"""
    
    
    return str(assigned_cluster)

    



