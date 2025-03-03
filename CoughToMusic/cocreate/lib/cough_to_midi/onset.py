import numpy as np
import librosa

def normalization(data):
    _range = np.max(data) - np.min(data)
    return (data - np.min(data)) / _range

def detect(audio_data , sr):
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sr)
    onset_env = normalization(onset_env)
    # threshold = np.percentile(onset_env, 90) 
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_frames = [frame for frame in onset_frames if onset_env[frame] > 0.2]
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    onset_times = merge_onset(onset_times, 0.05)
    return onset_times

def merge_onset(onset_times, min_time_gap):
    if len(onset_times) > 0:
        filtered_onsets = [onset_times[0]]
        for onset in onset_times[1:]:
            if onset - filtered_onsets[-1] > min_time_gap:
                filtered_onsets.append(onset)
        onset_times = np.array(filtered_onsets)
    return onset_times
    
def mask_generation(onset_time, f0 , range_x):
    mask = np.ones_like(f0, dtype=bool)
    for index in onset_time:
        start = index 
        end = min(len(f0), index + range_x + 1)  
        mask[start:end] = False  

    masked_f0 = np.where(mask, np.nan, f0)
    masked_f0 = np.array(masked_f0)
    return masked_f0

def compute_loudness(audio_data):
    return np.sqrt(np.mean(audio_data ** 2))  # RMS energy


def detect_offsets(audio_data, sr, onset_times):
    rms_energy = librosa.feature.rms(y=audio_data)[0]
    frame_times = librosa.frames_to_time(range(len(rms_energy)), sr=sr)

    offsets = []
    for i, onset in enumerate(onset_times):
        onset_idx = np.searchsorted(frame_times, onset)
        offset = frame_times[-1]  # Default: last frame in case no drop detected

        # Find next low-energy point AFTER onset
        for j in range(onset_idx, len(rms_energy)):
            if rms_energy[j] < 0.1 * rms_energy[onset_idx]:  # Energy threshold
                offset = frame_times[j]
                break

        # Ensure offset is not beyond the next onset
        if i < len(onset_times) - 1:
            offset = min(offset, onset_times[i + 1])

        offsets.append(offset)

    return onset_times, offsets



def compute_durations(onset_times, offset_times):
    durations = np.array(offset_times) - np.array(onset_times)
    return durations
