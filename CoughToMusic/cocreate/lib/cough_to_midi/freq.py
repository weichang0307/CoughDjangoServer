import crepe
import numpy as np
import librosa
import math
import logging
from midiutil import MIDIFile
import os
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
import audio
from cough_to_midi import onset

logger = logging.getLogger(__name__)



def predict_crepe(audio_data, sr):
    """Run CREPE inference once; returns raw (time, frequency, confidence) before any threshold filtering."""
    time, frequency, confidence, _ = crepe.predict(audio_data, sr=sr, viterbi=True)
    return time, frequency, confidence


def apply_crepe_threshold(time, raw_frequency, confidence, threshold, energy_threshold=-1000,
                          audio_data=None, sr=None, energy_filter=True):
    """Apply confidence threshold (and optional energy filter) to cached CREPE output."""
    frequency = np.where(confidence < threshold, np.nan, raw_frequency.copy())
    if energy_filter and audio_data is not None and sr is not None and energy_threshold > -1000:
        S = librosa.feature.melspectrogram(y=audio_data, sr=sr, n_mels=128, fmax=8000)
        mel_times = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=512)
        S_dB = librosa.power_to_db(S, ref=np.max)
        energy_mask = np.interp(time, mel_times, S_dB.max(axis=0)) > energy_threshold
        frequency = np.where(energy_mask, frequency, np.nan)
    return time, frequency


def get_by_crepe(audio_data, sr, threshold, energy_threshold, energy_filter=True):
    """Backward-compatible wrapper: predict + threshold in one call."""
    time, raw_frequency, confidence = predict_crepe(audio_data, sr)
    return apply_crepe_threshold(time, raw_frequency, confidence, threshold, energy_threshold,
                                 audio_data, sr, energy_filter)

def get_by_pyin(audio_data):
    f0, _, _ = librosa.pyin(audio_data, fmin=librosa.note_to_hz('C1'), fmax=librosa.note_to_hz('C7'))
    time = librosa.times_like(f0)
    f0 = np.array(f0)
    return time, f0

def interval_avg(f0):
    
    locker = 0
    total = 0
    count = 0
    result = []

    for i in range(len(f0)):
        if not math.isnan(f0[i]):
            locker = 1
            total += f0[i]
            count += 1
        elif math.isnan(f0[i]) and locker == 1:
            locker = 0
            result.append(total / count)
            total = 0
            count = 0

    if locker == 1:
        result.append(total / count)
    result_array = np.array(result)
    return result_array

def to_midi(frequency):
    if frequency <= 0:
        return 0
    # midi = 69 + 12 * np.log2(frequency / 440) -12
    midi = 69 + 12 * np.log2(frequency / 440) 
    # Round to the nearest integer
    return round(midi) 

def list_to_midis(freqs):
    return list(map(lambda freq: to_midi(freq), freqs))

def log_scale_frequency(frequency, log_fmin_input, log_fmax_input, min_target, max_target):
    fmin_target=librosa.note_to_hz(min_target)
    fmax_target=librosa.note_to_hz(max_target)
    log_freq = np.log2(frequency)
    scaled_log_freq = (log_freq - log_fmin_input) / (log_fmax_input - log_fmin_input)  # Normalized 0-1
    scaled_log_freq = scaled_log_freq * (np.log2(fmax_target) - np.log2(fmin_target)) + np.log2(fmin_target)
    # print(f"Frequency: {frequency}, Log frequency: {log_freq}, Scaled log frequency: {2 ** scaled_log_freq}")
    return 2 ** scaled_log_freq

def log_scale_frequencies(frequencies, min_target, max_target):
    valid_freqs = frequencies[~np.isnan(frequencies) & (frequencies > 0)]
    if len(valid_freqs) == 0:
        return frequencies
    fmin_input = np.min(valid_freqs)
    fmax_input = np.max(valid_freqs)
    log_fmin_input = np.log2(fmin_input)
    log_fmax_input = np.log2(fmax_input)
    # print(f"Min frequency: {fmin_input}, Max frequency: {fmax_input}, Log min: {log_fmin_input}, Log max: {log_fmax_input}")  
    return np.array([log_scale_frequency(freq, log_fmin_input, log_fmax_input, min_target, max_target) for freq in frequencies])

def write_midi(audio_data, sample_rate, audio_freq, filename,
               min_target, max_target, freq_range_th, note_interval_th,
               break_th=60, onset_seg=True, fallback_used=False):
    
    _, f0 = audio_freq
    f0_scaled = log_scale_frequencies(f0, min_target, max_target)
    tempo = audio.get_tempo(audio_data, sample_rate)
    if tempo <= 0:
        tempo = 120

    if onset_seg:
        onset_time = onset.detect(audio_data, sample_rate)
        audio_duration = audio.get_duration(audio_data, sample_rate)

        result_array, notes_on_frame, notes_off_frame = to_note_msg(
            onset_time, f0_scaled, freq_range_th, note_interval_th, break_th, audio_duration)

        if not result_array or all(p <= 1e-3 for p in result_array):
            if fallback_used:
                logger.error("Fallback config also failed. Skipping %s.", filename)
                return False
            logger.warning("Pitch tracking failed. Retrying with fallback config...")
            fallback_config = {
                "threshold": 0.1,
                "freq_range_th": 0.45,
                "note_interval_th": 60,
                "min_target": "C1",
                "max_target": "C3",
                "energy_th": -1000
            }
            return write_midi(audio_data, sample_rate, audio_freq, filename,
                              fallback_config["min_target"], fallback_config["max_target"],
                              fallback_config["freq_range_th"], fallback_config["note_interval_th"],
                              break_th, onset_seg, fallback_used=True)
        time_start_array_nstd, time_end_array_nstd = timeframes_to_sec(notes_on_frame, notes_off_frame, audio_duration / len(f0))
    if len(result_array) == 0 or len(notes_on_frame) == 0 or len(notes_off_frame) == 0:
        logger.warning("Skipping file %s due to insufficient valid pitch data.", filename)
        return False

    def add_notes_to_midi(midi, time_start_array, time_end_array, result_array):
        track = 0
        for i in range(len(result_array)):
            start_time = time_start_array[i]
            end_time = time_end_array[i]
            pitch = to_midi(result_array[i])
            if pitch != 0:
                volume = 80
                duration_midi = end_time - start_time
                midi.addNote(track, 0, pitch, start_time, duration_midi, volume)

    midi = MIDIFile(1)
    midi.addTrackName(0, 0, "Sample Track")
    midi.addTempo(0, 0, tempo)
    add_notes_to_midi(midi, time_start_array_nstd, time_end_array_nstd, result_array)
    
    with open(f"{filename}", "wb") as output_file:
        midi.writeFile(output_file)

    try:
        new_tempo = audio.tempo_adjust(audio_duration, tempo, filename)
    except ValueError as e:
        logger.exception("Error adjusting tempo for %s", filename)
        return False

    midi = MIDIFile(1)
    midi.addTrackName(0, 0, "Sample Track")
    midi.addTempo(0, 0, new_tempo)
    add_notes_to_midi(midi, time_start_array_nstd, time_end_array_nstd, result_array)

    with open(f"{filename}", "wb") as output_file:
        midi.writeFile(output_file)

    time = audio.get_midi_length(filename)

    return True


def to_note_msg(onset_time, f0, freq_range_th, note_interval_th, break_th , wavefile_time):
    # print(f"Onset time: {onset_time}, F0: {f0}, Frequency range threshold: {freq_range_th}, Note interval threshold: {note_interval_th}, Break threshold: {break_th}, Wavefile time: {wavefile_time}")
    onset_point = audio.sec_to_timeframe(onset_time, wavefile_time, f0)
    result_array = []
    time_start_array = []
    time_end_array = []

    def process_interval(start, end):
        temp_array = []
        nan_count = 0
        f_locker = 0
        nan_token = 0
        # print(f"Processing interval from {start} to {end}")
        # print(f"f0 values: {f0[start:end]}")
        for j in range(start, end):           
            if np.isnan(f0[j]):
                if f_locker:
                    nan_count += 1
                    f_locker = 0
                else:
                    if nan_count > note_interval_th:
                        if temp_array:
                            avg = np.mean(temp_array)
                            result_array.append(avg)
                            time_end_array.append(j - nan_count )
                            temp_array = []
                            nan_count = 0
                        elif nan_token < break_th:
                            nan_token += 1
                        else:
                            break
                    else:
                        nan_count += 1
            else:
                if not temp_array:
                    temp_array.append(f0[j])
                    time_start_array.append(j)
                    nan_count = 0
                    f_locker = 1
                else:
                    avg = np.mean(temp_array)
                    if abs(f0[j] - avg) > (freq_range_th * avg):
                        time_end_array.append(j -1)
                        result_array.append(avg)
                        temp_array = [f0[j]]
                        time_start_array.append(j)
                        nan_count = 0
                        f_locker = 1
                    else:
                        temp_array.append(f0[j])
                        nan_count = 0
                        f_locker = 1

        if temp_array:
            avg = np.mean(temp_array)
            result_array.append(avg)
            time_end_array.append(end - 1)
        # print(f"Processed interval {start} to {end}")
        # print(f"Temp array: {temp_array}")
        # print(f"Result array: {result_array}")
        # print(f"Time start array: {time_start_array}")
        # print(f"Time end array: {time_end_array}")

    for i in range(0,len(onset_point)):
        if  i == len(onset_point)-1:
            start = onset_point[i]
            end = len(f0)
            process_interval(start, end)
        else:
            start = onset_point[i]
            end = onset_point[i+1]
            process_interval(start, end)
    
    
    for i in range(0 , len(time_start_array)):
        if time_start_array[i] == time_end_array[i]:
            time_end_array[i] += 1

    return result_array, time_start_array, time_end_array


def timeframes_to_sec(notes_on_frame , notes_off_frame , time_unit):
    notes_on_frame = np.array(notes_on_frame)
    notes_off_frame = np.array(notes_off_frame)
    notes_on_time=[]
    notes_off_time=[]
    notes_on_time = notes_on_frame * time_unit
    notes_off_time = notes_off_frame * time_unit
    notes_on_time = np.array(notes_on_time)
    notes_off_time = np.array(notes_off_time)

    return notes_on_time,notes_off_time
