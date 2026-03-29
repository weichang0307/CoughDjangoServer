import numpy as np
import librosa
import os
import glob
import math
import noisereduce
import pretty_midi
from pydub import AudioSegment
import soundfile as sf
# from pedalboard import Pedalboard, Gain, Reverb


def load_from_dir(audio_path):
    audio_path = glob.glob(os.path.join(dir, "*.wav"))

    audios_data = [sf.read(file)[0] for file in audio_path]
    audios_data = [stereo_to_mono(audio_data) for audio_data in audios_data]
    audios_data = [
        denoise(audio_data, sample_rate)
        for audio_data, sample_rate in zip(
            audios_data, [sf.read(file)[1] for file in audio_path]
        )
    ]

    sample_rate = sf.read(audio_path[0])[1]
    return audios_data, sample_rate


def load_from_file(audio_file_path):
    audio_data, sample_rate = sf.read(audio_file_path)
    audio_data = stereo_to_mono(audio_data)
    audio_data = denoise(audio_data, sample_rate)
    return audio_data, sample_rate


def denoise(audio_data, sr):
    return noisereduce.reduce_noise(y=audio_data, sr=sr)


def stereo_to_mono(audio_data):
    if audio_data.ndim > 1 and audio_data.shape[1] == 2:
        audio_data = audio_data.mean(axis=1)
    return audio_data


def get_note_time(f0):
    locker = 0
    total = 0
    time_start = []
    time_end = []

    for i in range(len(f0)):
        if math.isnan(f0[i]):
            if locker == 1:
                time_end.append(total)
                locker = 0
        else:
            if locker == 0:
                time_start.append(total)
                locker = 1
            if i == len(f0) - 1:
                time_end.append(total)
        total += 1
    time_start = np.array(time_start)
    time_end = np.array(time_end)
    return time_start, time_end


def get_tempo(audio_data, sample_rate):
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sample_rate)
    tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sample_rate, max_tempo=80)
    return tempo

def gain_db_from_wav(audio_file, gain_db):
    audio_segment = AudioSegment.from_wav(audio_file)
    audio_segment = audio_segment + gain_db
    audio_segment.export(audio_file, format="wav")




def sec_to_timeframe(time_array, total_time, f0):
    onset_time_array = []
    for i in range(0, len(time_array)):
        temp = time_array[i] / total_time
        outcome = temp * len(f0)
        outcome = int(outcome)
        onset_time_array.append(outcome)
    onset_time_array = np.array(onset_time_array)
    return onset_time_array


def get_duration(audio_data, sr):
    duration = len(audio_data) / sr
    return duration


def get_midi_length(file_path):
    midi_data = pretty_midi.PrettyMIDI(file_path)
    midi_duration = midi_data.get_end_time()
    return midi_duration


def tempo_adjust(wavefile_time, tempo, file_name):
    midi_time = get_midi_length(file_name)
    factor = midi_time / wavefile_time
    tempo_new = tempo * factor

    return tempo_new


def overlap(file_path1, file_path2, output_path):
    audio1 = AudioSegment.from_file(file_path1)
    audio2 = AudioSegment.from_file(file_path2)
    max_length = max(len(audio1), len(audio2))
    if len(audio1) < max_length:
        audio1 += AudioSegment.silent(duration=(max_length - len(audio1)))
    elif len(audio2) < max_length:
        audio2 += AudioSegment.silent(duration=(max_length - len(audio2)))
    combined = audio1.overlay(audio2, position=0)
    combined.export(output_path, format="wav")


def overlap_short(file_path1, file_path2, output_path):
    audio1 = AudioSegment.from_file(file_path1)
    audio2 = AudioSegment.from_file(file_path2)
    # Determine the shorter audio
    min_length = min(len(audio1), len(audio2))
    # Trim the longer audio to the length of the shorter audio
    if len(audio1) > min_length:
        audio1 = audio1[:min_length]
    if len(audio2) > min_length:
        audio2 = audio2[:min_length]
    # Overlap the two audio files
    combined = audio1.overlay(audio2, position=0)
    combined.export(output_path, format="wav")


# write_from_midi('derive_results/midis/output_1.mid', 'output.wav', 'violin')


def remove_silence_from_start(audio_file, silence_threshold=-80.0, chunk_size=1):
    """
    Removes silence from the beginning of an AudioSegment.
    """
    audio_segment = AudioSegment.from_wav(audio_file)
    trim_ms = 0  # ms to trim from the start

    assert chunk_size > 0  # chunk_size must be positive
    duration_ms = len(audio_segment)

    while trim_ms < duration_ms:
        chunk_start = trim_ms
        chunk_end = trim_ms + chunk_size
        chunk = audio_segment[chunk_start:chunk_end]

        if chunk.dBFS < silence_threshold:
            trim_ms += chunk_size
        else:
            break
    audio_segment[trim_ms:].export(audio_file, format="wav")


def remove_silence_from_end(audio_file, silence_threshold=-60.0, chunk_size=1):
    """
    Removes silence from the end of an AudioSegment.
    """
    audio_segment = AudioSegment.from_wav(audio_file)
    trim_ms = len(audio_segment)  # ms to trim from the end

    assert chunk_size > 0  # chunk_size must be positive

    while trim_ms > 0:
        chunk_start = max(0, trim_ms - chunk_size)
        chunk_end = trim_ms
        chunk = audio_segment[chunk_start:chunk_end]

        if chunk.dBFS < silence_threshold:
            trim_ms -= chunk_size
        else:
            break
    audio_segment[:trim_ms].export(audio_file, format="wav")

def padd_to_4_seconds(audio_file):
    audio_segment = AudioSegment.from_wav(audio_file)
    duration = len(audio_segment)
    if duration < 4000:
        silence = AudioSegment.silent(duration=4000 - duration)
        audio_segment = audio_segment + silence
        audio_segment.export(audio_file, format="wav")

def save_audio(np_audio, output_path, sample_rate = 16000):
    sf.write(output_path, np_audio, sample_rate)

def sound_synthesis(Db, Room_size, Damping, Wet_level, synthesized_audio, sample_rate):
    board = Pedalboard([
        Gain(gain_db=Db),
        Reverb(room_size=Room_size, damping=Damping, wet_level=Wet_level),
    ])
    processed_audio = board(synthesized_audio, sample_rate)
    return processed_audio
