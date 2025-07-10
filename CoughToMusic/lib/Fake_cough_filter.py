import librosa
import numpy as np
import noisereduce as nr

def noise_reduction(audio_data, sample_rate, n_fft=1024, hop_length=None, prop_decrease=1.0):
    audio_data = nr.reduce_noise(y=audio_data, sr=sample_rate, n_fft=n_fft, hop_length=hop_length, prop_decrease=prop_decrease)
    if np.isnan(audio_data).any() or np.isinf(audio_data).any():
        audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
    return audio_data

def normalization(data):
    _range = np.max(data) - np.min(data)
    return (data - np.min(data)) / _range if _range != 0 else data

def detect_onsets(audio_data, sr, threshold=0.2, energy_window=0.2, top_k=3):
    if audio_data.ndim == 2:
        audio_data = librosa.to_mono(audio_data.T)

    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sr)
    onset_env = normalization(onset_env)

    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_frames = [f for f in onset_frames if onset_env[f] > threshold]
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    if not onset_times.any():
        return []

    win_len = int(energy_window * sr)
    energies = []
    for t in onset_times:
        start_sample = int(t * sr)
        end_sample = start_sample + win_len
        segment = audio_data[start_sample:end_sample] if end_sample <= len(audio_data) else audio_data[start_sample:]
        energy = np.sum(segment**2)
        energies.append(energy)

    top_indices = np.argsort(energies)[::-1][:top_k]
    top_onsets = [onset_times[i] for i in top_indices]
    selected_onset = min(top_onsets)

    return [selected_onset]

def has_inhale(audio_data, sr, onset_time, thresholds):
    inhale_samples = int(thresholds['inhale_duration'] * sr)
    onset_sample = int(onset_time * sr)

    if onset_sample < inhale_samples:
        return False

    inhale_segment = audio_data[onset_sample - inhale_samples:onset_sample]
    
    energy = np.mean(np.abs(inhale_segment))
    zcr = librosa.feature.zero_crossing_rate(inhale_segment)[0].mean()
    centroid = librosa.feature.spectral_centroid(y=inhale_segment, sr=sr)[0].mean()
    mfcc = librosa.feature.mfcc(y=inhale_segment, sr=sr, n_mfcc=13)
    mfcc1 = mfcc[0].mean()
    
    return (energy > thresholds['energy_threshold'] or 
            zcr > thresholds['zcr_threshold'] or 
            centroid > thresholds['centroid_threshold'] or 
            mfcc1 > thresholds['mfcc1_threshold'])

def detect_inhale(audio_data, sample_rate):
    """
    Detects inhale sound in audio data.
    
    Args:
        audio_data (np.ndarray): Input audio data as numpy array
        sample_rate (int): Sample rate of the audio data
    
    Returns:
        bool: True if inhale is detected, False otherwise
    """
    np.complex = complex  # Fix for librosa np.complex deprecation
    thresholds = {
        'inhale_duration': 0.7,
        'energy_threshold': 0.01, #0.02
        'zcr_threshold': 0.08,
        'centroid_threshold': 3700,
        'mfcc1_threshold': 140
    }

    # Apply noise reduction
    audio_data = noise_reduction(audio_data, sample_rate)
    
    # Detect onsets
    onset_times = detect_onsets(audio_data, sample_rate)
    
    # Check for inhale in each onset
    for onset_time in onset_times:
        if has_inhale(audio_data, sample_rate, onset_time, thresholds):
            return True
    
    return False