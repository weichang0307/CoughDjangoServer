import numpy as np
import librosa

def normalization(data):
    _range = np.max(data) - np.min(data)
    return (data - np.min(data)) / _range

def detect(audio_data, sr, threshold=0.2):
    if audio_data.ndim == 2:
        audio_data = librosa.to_mono(audio_data.T)
    
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sr)
    onset_env = normalization(onset_env)
    
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_frames = [frame for frame in onset_frames if onset_env[frame] > threshold]
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    
    return onset_times
