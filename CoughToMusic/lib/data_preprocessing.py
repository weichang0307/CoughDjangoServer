import numpy as np
import noisereduce
import librosa

def stereo_to_mono(audio_data):
    if audio_data.ndim > 1 and audio_data.shape[1] == 2:
        audio_data = audio_data.mean(axis=1)
    return audio_data

def noise_reduction(audio_data, sample_rate, n_fft=1024, hop_length=None, prop_decrease=1.0):
    audio_data = noisereduce.reduce_noise(y=audio_data, sr=sample_rate, n_fft=n_fft, hop_length=hop_length, prop_decrease=prop_decrease)
    if np.isnan(audio_data).any() or np.isinf(audio_data).any():
        audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
    return audio_data

def filter_audio_by_rms(audio_data, threshold, segment_length=128):
    filtered_audio = []
    for start in range(0, len(audio_data), segment_length):
        end = start + segment_length
        segment = audio_data[start:end]
        rms = np.sqrt(np.mean(segment**2))
        if rms < threshold:
            filtered_segment = np.zeros_like(segment)  
        else:
            filtered_segment = segment
        filtered_audio.append(filtered_segment)
    return np.concatenate(filtered_audio)

def load_audio(audio_path, sample_rate, S2M=True, NR=True, RMS_threshold=0.0005):
    audio_data, _ = librosa.load(audio_path, sr=sample_rate)
    
    if S2M:
        audio_data = stereo_to_mono(audio_data)
    
    if RMS_threshold is not None:
        audio_data = filter_audio_by_rms(audio_data, RMS_threshold)
        
    if NR:
        audio_data = noise_reduction(audio_data, sample_rate)
    
    return audio_data
    
