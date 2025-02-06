import numpy as np
from . import onset, freq

def process_audio_to_normalized_rms(f0, audio_data, sample_rate, onset_seg=True, freq_range_th=0.18, note_interval_th=15, break_th=20):
    """
    處理音頻數據並返回正規化的RMS值。
    """
    # 計算時間框架
    time_start_array, time_end_array = calculate_timeframes(f0, audio_data, sample_rate, onset_seg, freq_range_th, note_interval_th, break_th)
    
    # 計算RMS值
    rms_values = calculate_rms(audio_data, sample_rate, time_start_array, time_end_array)
    
    # 將RMS值正規化到0到1之間
    normalized_rms_values = map_rms_to_velocity(rms_values)
    
    return normalized_rms_values

def calculate_timeframes(f0, audio_data, sample_rate, onset_seg=True, freq_range_th=0.18, note_interval_th=15, break_th=20):
    if onset_seg:
        onset_time = onset.detect(audio_data, sample_rate, threshold=0.4)
        audio_duration = freq.get_duration(audio_data, sample_rate)
        _, notes_on_frame, notes_off_frame = freq.to_note_msg(onset_time, f0, freq_range_th, note_interval_th, break_th, audio_duration)
        time_start_array_nstd, time_end_array_nstd = freq.timeframes_to_sec(notes_on_frame, notes_off_frame, audio_duration / len(f0))
        return time_start_array_nstd, time_end_array_nstd
    return [], []

def calculate_rms(audio_data, sample_rate, time_start_array, time_end_array):
    """
    計算每個音符段的RMS能量。
    """
    rms_values = []
    for start, end in zip(time_start_array, time_end_array):
        # 計算對應時間段的樣本索引
        start_sample = int(start * sample_rate)
        end_sample = int(end * sample_rate)
        # 提取音頻段
        segment = audio_data[start_sample:end_sample]
        # 計算RMS
        rms = np.sqrt(np.mean(segment**2))
        rms_values.append(rms)
    return rms_values
        
def map_rms_to_velocity(rms_values, min_velocity=30, max_velocity=127, normalize_min=0.60, normalize_max=0.90):
    """
    將RMS值映射到MIDI音符的力度，並將其歸一化到0.3-0.7之間。
    """
    rms_array = np.array(rms_values)
    # 避免除以零
    if np.max(rms_array) == 0:
        return [min_velocity for _ in rms_values]
    normalized = (rms_array - np.min(rms_array)) / (np.max(rms_array) - np.min(rms_array))
    velocity_values = (normalized * (max_velocity - min_velocity) + min_velocity).astype(int)
    normalized_velocity_values = (velocity_values - min_velocity) / (max_velocity - min_velocity)
    scaled_normalized_velocity_values = normalized_velocity_values * (normalize_max - normalize_min) + normalize_min
    
    return scaled_normalized_velocity_values.tolist()