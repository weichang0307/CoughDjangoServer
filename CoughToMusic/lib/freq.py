import numpy as np
from midiutil import MIDIFile
import librosa
from . import onset
import os

def get_note_time(f0):
    print("Calculating note time...")
    is_note = ~np.isnan(f0)
    changes = np.diff(is_note.astype(int))
    time_start = np.where(changes == 1)[0] + 1
    time_end = np.where(changes == -1)[0] + 1

    if is_note[0]:
        time_start = np.insert(time_start, 0, 0)
    if is_note[-1]:
        time_end = np.append(time_end, len(f0))

    return time_start, time_end

def to_midi(frequency, locker=True):
    if frequency <= 0:
        return 0  # 無效頻率對應無音符
    
    midi = 69 + 12 * np.log2(frequency / 440)
    midi = round(midi)
    
    if locker:
        if midi < 38:  # 限制在 D2 (MIDI 38)
            midi = 38
        if midi > 107:  # 限制在 G6 (MIDI 107)
            midi = 107
    return midi


def write_midi(audio_data, sample_rate, audio_freq, foldername, filename, onset_seg=True, freq_range_th=0.18, note_interval_th=15, break_th=20, min_timeframe=30):
    """
    將音頻數據轉換為MIDI文件，並生成三個不同範圍的MIDI文件。
    """
    path = f"{foldername}/{filename}"
    
    f0 = audio_freq
    notes_on_frame, notes_off_frame = get_note_time(f0)
    print("Converting to MIDI...")
    
    if onset_seg:
        onset_time = onset.detect(audio_data, sample_rate, threshold=0.4)
        audio_duration = get_duration(audio_data, sample_rate)
        result_array, notes_on_frame, notes_off_frame = to_note_msg(onset_time, f0, freq_range_th, note_interval_th, break_th, audio_duration)
        for i in range(len(notes_on_frame)):
            if notes_off_frame[i] - notes_on_frame[i] < min_timeframe:
                # 計算需要增加的時間
                time_to_add = min_timeframe - (notes_off_frame[i] - notes_on_frame[i])
        
                # 更新當前音符的結束時間
                notes_off_frame[i] += time_to_add
        
                # 調整後續音符的開始和結束時間
                for j in range(i + 1, len(notes_on_frame)):
                    notes_on_frame[j] += time_to_add
                    notes_off_frame[j] += time_to_add
        print(notes_on_frame)
        print(notes_off_frame)
        time_start_array_nstd, time_end_array_nstd = timeframes_to_sec(notes_on_frame, notes_off_frame, audio_duration / len(f0))

    # 創建資料夾
    if not os.path.exists(path):
        os.makedirs(path)

    # 定義音高範圍
    pitch_ranges = {
        "Bass": (to_midi(73.42), to_midi(130.81)),  # D2 (73.42 Hz) to C3 (130.81 Hz)
        "Alto": (to_midi(130.81), to_midi(1046.50)),  # C3 (130.81 Hz) to G5 (1046.50 Hz)
        "High": (to_midi(1046.50), to_midi(1396.91))  # G5 (1046.50 Hz) to G6 (1396.91 Hz)
    }

    # 生成三個不同範圍的MIDI文件
    for name, pitch_range in pitch_ranges.items():
        midi = MIDIFile(1, ticks_per_quarternote=220)
        track = 0
        time = 0
        midi.addTrackName(track, time, f"{filename}_{name}")
        midi.addTempo(track, time, 60)
        
        # 記錄是否有加入音符的標記
        has_notes = False
        
        # 加入音符並檢查是否有音符在該音域範圍內
        for i, freq in enumerate(result_array):
            if freq > 0:  # 確保頻率大於0
                midi_note = to_midi(freq)
                if pitch_range[0] <= midi_note <= pitch_range[1]:
                    start_time = time_start_array_nstd[i]
                    duration = time_end_array_nstd[i] - time_start_array_nstd[i]
                    midi.addNote(track, 0, midi_note, start_time, duration, 100)
                    has_notes = True
        
        # 只有在有音符的情況下才創建文件
        if has_notes:
            filepath = os.path.join(path, f"{filename}_{name}.mid")
            with open(filepath, "wb") as output_file:
                midi.writeFile(output_file)
            print(f"File {filepath} created successfully!")
        else:
            print(f"No notes added for {name}, skipping file creation.")

def to_note_msg(onset_time, f0, freq_range_th, note_interval_th, break_th, wavefile_time):
    """
    將音符訊息轉換為MIDI格式。
    """
    onset_point = sec_to_timeframe(onset_time, wavefile_time, f0)
    result_array = []
    time_start_array = []
    time_end_array = []

    def process_interval(start, end):
        temp_array = []
        nan_count = 0
        f_locker = 0
        nan_token = 0

        for j in range(start, end):
            if np.isnan(f0[j]).any():
                if f_locker:
                    nan_count += 1
                    f_locker = 0
                else:
                    if nan_count > note_interval_th:
                        if temp_array:
                            avg = np.mean(temp_array)
                            result_array.append(avg)
                            time_end_array.append(j - nan_count)
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
                        time_end_array.append(j - 1)
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

    for i in range(len(onset_point)):
        if i == len(onset_point) - 1:
            start = onset_point[i]
            end = len(f0)
            process_interval(start, end)
        else:
            start = onset_point[i]
            end = onset_point[i + 1]
            process_interval(start, end)
    
    for i in range(len(time_start_array)):
        if time_start_array[i] == time_end_array[i]:
            time_end_array[i] += 1

    return result_array, time_start_array, time_end_array

def timeframes_to_sec(notes_on_frame, notes_off_frame, time_unit):
    """
    將音符時間框架轉換為秒。
    """
    notes_on_frame = np.array(notes_on_frame)
    notes_off_frame = np.array(notes_off_frame)
    notes_on_time = notes_on_frame * time_unit
    notes_off_time = notes_off_frame * time_unit
    return notes_on_time, notes_off_time

def sec_to_timeframe(time_array, total_time, f0):
    return np.array([int(t / total_time * len(f0)) for t in time_array])

def get_tempo(audio_data, sample_rate):
    onset_env = librosa.onset.onset_strength(y=audio_data, sr=sample_rate)
    tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sample_rate, max_tempo=80)
    return tempo

def get_duration(audio_data, sr):
    return len(audio_data) / sr