from __future__ import annotations

import numpy as np


def select_analysis_window(
    audio_data,
    sample_rate,
    *,
    target_seconds=4.0,
    pre_roll_seconds=0.2,
    silence_ratio=0.02,
    onset_detector=None,
):
    audio_data = np.asarray(audio_data, dtype=np.float32)
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    target_samples = max(1, int(round(target_seconds * sample_rate)))
    if audio_data.size == 0 or not sample_rate:
        window = _pad_or_crop(audio_data, target_samples)
        return window, {
            "reason": "empty",
            "trim_start_sample": 0,
            "window_start_sample": 0,
            "window_end_sample": len(window),
            "target_samples": target_samples,
        }

    trimmed_audio, trim_start_sample = _trim_leading_silence(audio_data, sample_rate, silence_ratio)
    if trimmed_audio.size == 0:
        trimmed_audio = audio_data
        trim_start_sample = 0

    if trimmed_audio.size <= target_samples:
        window = _pad_or_crop(trimmed_audio, target_samples)
        return window, {
            "reason": "short",
            "trim_start_sample": trim_start_sample,
            "window_start_sample": trim_start_sample,
            "window_end_sample": trim_start_sample + len(trimmed_audio),
            "target_samples": target_samples,
        }

    onset_detector = onset_detector or detect_onsets
    onset_times = onset_detector(trimmed_audio, sample_rate)
    if len(onset_times) > 0:
        start_sample = max(0, int(round((float(onset_times[0]) - pre_roll_seconds) * sample_rate)))
        start_sample = min(start_sample, trimmed_audio.size - target_samples)
        reason = "onset"
    else:
        start_sample = _highest_energy_window_start(trimmed_audio, target_samples)
        reason = "energy"

    window = trimmed_audio[start_sample : start_sample + target_samples]
    if window.size < target_samples:
        window = _pad_or_crop(window, target_samples)

    return window.astype(np.float32, copy=False), {
        "reason": reason,
        "trim_start_sample": trim_start_sample,
        "window_start_sample": trim_start_sample + start_sample,
        "window_end_sample": trim_start_sample + start_sample + len(window),
        "target_samples": target_samples,
        "onset_count": len(onset_times),
    }


def detect_onsets(audio_data, sample_rate, initial_threshold=0.2, min_threshold=0.05, step=0.05):
    import librosa

    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sample_rate)
    onset_env = _normalize_array(onset_env)

    threshold = initial_threshold
    onset_frames = []
    while threshold >= min_threshold and not onset_frames:
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sample_rate)
        onset_frames = [frame for frame in onset_frames if onset_env[frame] > threshold]
        if not onset_frames:
            threshold -= step

    if not onset_frames:
        return np.array([])

    onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate)
    return _merge_onsets(onset_times, 0.05)


def _trim_leading_silence(audio_data, sample_rate, silence_ratio):
    if audio_data.size == 0:
        return np.asarray(audio_data, dtype=np.float32), 0
    if silence_ratio <= 0:
        return np.asarray(audio_data, dtype=np.float32), 0

    peak = float(np.max(np.abs(audio_data)))
    if peak <= 1e-8:
        return np.asarray([], dtype=np.float32), 0

    threshold = peak * silence_ratio
    non_silent = np.flatnonzero(np.abs(audio_data) > threshold)
    if non_silent.size == 0:
        return np.asarray([], dtype=np.float32), 0

    pre_roll = int(round(sample_rate * 0.05))
    start_sample = max(0, int(non_silent[0]) - pre_roll)
    return audio_data[start_sample:], start_sample


def _highest_energy_window_start(audio_data, target_samples):
    if audio_data.size <= target_samples:
        return 0

    abs_audio = np.abs(audio_data).astype(np.float64, copy=False)
    cumulative = np.concatenate(([0.0], np.cumsum(abs_audio)))
    window_energy = cumulative[target_samples:] - cumulative[:-target_samples]
    return int(np.argmax(window_energy))


def _pad_or_crop(audio_data, target_samples):
    audio_data = np.asarray(audio_data, dtype=np.float32)
    if audio_data.size >= target_samples:
        return audio_data[:target_samples]

    padded = np.zeros(target_samples, dtype=np.float32)
    padded[: audio_data.size] = audio_data
    return padded


def _normalize_array(data):
    if len(data) == 0:
        return np.asarray(data)
    min_val = np.min(data)
    max_val = np.max(data)
    if np.isclose(max_val, min_val):
        return np.zeros_like(data)
    return (data - min_val) / (max_val - min_val)


def _merge_onsets(onset_times, min_gap):
    if len(onset_times) == 0:
        return np.asarray(onset_times)

    merged = [float(onset_times[0])]
    for onset_time in onset_times[1:]:
        onset_time = float(onset_time)
        if onset_time - merged[-1] >= min_gap:
            merged.append(onset_time)
    return np.asarray(merged)
