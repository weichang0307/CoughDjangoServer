import ddsp.training.metrics
import librosa as ls
import numpy as np
import noisereduce
from scipy.signal import butter, lfilter


def get_pitch(audio_np, sr):
    # Get the pitch of the audio
    # compute audio features
    # print(audio_np)
    start_time = 0.1  # start trim at 0.5 seconds
    end_time = 2.1  # end trim at 1.5 seconds
    start_sample = int(start_time * sr)
    end_sample = int(end_time * sr)
    audio_trimmed = audio_np[start_sample:end_sample]
    audio_features = ddsp.training.metrics.compute_audio_features(audio_trimmed)
    f0s = ls.hz_to_midi(audio_features["f0_hz"])

    # fileter out large difference
    filtered_f0s = filter_outliers(f0s, 0.7)

    # get the most frequent pitch
    filtered_f0s = np.round(filtered_f0s).astype(int)
    pitchs, count = np.unique(filtered_f0s, return_counts=True)
    pitch = pitchs[np.argmax(count)]
    # print(f"Pitch: {pitch}")
    return pitch


def filter_outliers(arr_np, threshold):
    # Filter out the outliers of the array
    mean = np.mean(arr_np)
    std = np.std(arr_np)
    filtered_arr = [x for x in arr_np if abs(x - mean) <= threshold * std]

    return filtered_arr


def pitch_shift(audio_np, sr, pitch):
    # Pitch shift the audio
    bias = pitch - get_pitch(audio_np, sr)
    return ls.effects.pitch_shift(audio_np, sr=sr, n_steps=bias)


def pitch_shift_by(audio_np, sr, bias):
    # Pitch shift the audio by the given bias
    return ls.effects.pitch_shift(audio_np, sr=sr, n_steps=bias)


def butter_highpass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype="high", analog=False)
    y = lfilter(b, a, data)
    return y


def butter_lowpass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype="low", analog=False)
    y = lfilter(b, a, data)
    return y


def volumn_normalize(audio_np, db):
    # Normalize the audio to the given decibels
    before_db = get_max_db(audio_np)
    bias = db - int(before_db)

    amplitude_ratio = 10 ** (bias / 20)
    audio_np = audio_np * amplitude_ratio

    return audio_np


def get_max_db(audio_np):
    # Get the maximum decibels of the audio
    return ls.amplitude_to_db(audio_np).max()


def fadeout(audio_np, time, sample_rate):

    start_time = 0.1  # start trim at 0.5 seconds
    end_time = 1.1  # end trim at 1.5 seconds
    start_sample = int(start_time * sample_rate)
    end_sample = int(end_time * sample_rate)
    audio_trimmed = audio_np[start_sample:end_sample]

    length = len(audio_trimmed)

    fadeout_samples = int(length * time / 100)
    env = np.linspace(1, 0, fadeout_samples)
    env = np.pad(env, (0, length - fadeout_samples), mode="constant", constant_values=0)
    audio_faded = audio_trimmed * env

    return audio_faded


def normalize_length(audio_np, length):

    silent = np.zeros(length - len(audio_np))
    normalized = np.append(audio_np, silent)
    return normalized


def noise_reduce(audio_np, sr):
    # noise reduction
    reduced_noise = noisereduce.reduce_noise(y=audio_np, sr=sr)
    return reduced_noise
