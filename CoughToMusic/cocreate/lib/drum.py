import os
import numpy as np
import pandas as pd
import librosa
import librosa.display
import matplotlib.pyplot as plt
import random
from cough_to_midi.onset import *
import audio
import pretty_midi


DRUM_MAPPING = {
    "kick": 36, "snare": 38, "closed_hihat": 42, "open_hihat": 46,
    "mid_tom": 48, "low_tom": 45, "crash": 49
}
VELOCITY_MAPPING = {
    "kick": 95, "snare": 100, "closed_hihat": 80, "open_hihat": 75,
    "mid_tom": 95, "low_tom": 95, "crash": 80
}



# def detect_offsets(audio_data, sr, onset_times):
#     # Compute offsets (example logic)
#     offset_times = onset_times + 0.2  # Assume 200ms per cough event
#     return onset_times, np.clip(offset_times, 0, librosa.get_duration(y=audio_data, sr=sr))

def compute_durations(onset_times, offset_times):
    return offset_times - onset_times

def compute_loudness(audio_segment):
    return np.mean(np.abs(audio_segment))

def visualize_cough(audio_data, sr, file_index, onset_times, offset_times, durations):
    plt.figure(figsize=(6, 4))
    librosa.display.waveshow(audio_data, sr=sr, alpha=0.8)
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')

    for on_set, off_set in zip(onset_times, offset_times):
        plt.axvline(x=on_set, color='g', linestyle='--', linewidth=3)
        plt.axvline(x=off_set, color='r', linestyle=':', linewidth=3)

    plt.legend(["Onset", "Offset"])
    plt.tight_layout()
    plt.show()

def process_all_coughs(folder_path):
    all_files = [f for f in os.listdir(folder_path) if f.endswith(".wav")]
    data = []

    for file in all_files:
        file_index = file.split("_")[-1].split(".")[0]
        audio_path = os.path.join(folder_path, file)
        audio_data, sr = audio.load_from_file(audio_path)

        onset_times = detect(audio_data, sr)
        onset_times, offset_times = detect_offsets(audio_data, sr, onset_times)
        durations = compute_durations(onset_times, offset_times)

        avg_duration = np.mean(durations)
        loudness_values = [compute_loudness(audio_data[int(start * sr):int(end * sr)]) 
                           for start, end in zip(onset_times, offset_times)]
        avg_loudness = np.mean(loudness_values)

        data.append([file_index, avg_duration, avg_loudness])
        # visualize_cough(audio_data, sr, file_index, onset_times, offset_times, durations)

    return pd.DataFrame(data, columns=["id", "avg_duration", "avg_loudness"])

def normalize_and_rank(df):
    df["duration_percentile"] = df["avg_duration"].rank(pct=True)
    df["loudness_percentile"] = df["avg_loudness"].rank(pct=True)
    return df

def classify(duration_pct, loudness_pct):
    if duration_pct <= 0.4:
        return "closed_hihat" if loudness_pct <= 0.25 else "kick" if loudness_pct <= 0.6 else "snare"
    elif duration_pct <= 0.9:
        return "open_hihat" if loudness_pct <= 0.3 else "low_tom" if loudness_pct <= 0.66 else "mid_tom"
    return "open_hihat" if loudness_pct <= 0.6 else "crash"

def classify_coughs(df):
    df["drum"] = df.apply(lambda row: classify(row["duration_percentile"], row["loudness_percentile"]), axis=1)
    print(df)
    return df

def select_related_drums(df, target_id, num ):
    if "drum" not in df.columns:
        raise ValueError("Missing 'drum' column.")

    target_row = df[df["id"] == str(target_id)]
    if target_row.empty:
        raise ValueError(f"No cough found with ID: {target_id}")

    selected_coughs = {target_row["drum"].values[0]: target_id}
    df_shuffled = df.sample(frac=1, random_state=random.randint(1, 1000))

    for _, row in df_shuffled.iterrows():

        if len(selected_coughs) == num:
            break
        if row["drum"] not in selected_coughs:
            selected_coughs[row["drum"]] = row["id"]       
    return selected_coughs

# def write_midi_pretty(selected_coughs, df, folder_path, output_midi):
#     midi = pretty_midi.PrettyMIDI()

#     for drum_type, cough_id in selected_coughs.items():
#         row = df[df["id"] == cough_id]
#         if row.empty:
#             print(f"Warning: No data found for ID {cough_id}")
#             continue      

#         audio_path = os.path.join(folder_path, f"cough_{cough_id}.wav")
#         if not os.path.exists(audio_path):
#             print(f"Warning: File {audio_path} not found.")
#             continue

#         audio_data, sr = librosa.load(audio_path, sr=None)
#         onset_times = detect(audio_data, sr)

#         drum_track = pretty_midi.Instrument(program=0, is_drum=True)
#         for onset_time in onset_times:
#             note = pretty_midi.Note(
#                 velocity=VELOCITY_MAPPING.get(drum_type, 100),
#                 pitch=DRUM_MAPPING.get(drum_type, 38),
#                 start=onset_time,
#                 end=onset_time + 0.05
#             )
#             drum_track.notes.append(note)

#         midi.instruments.append(drum_track)

#     midi.write(output_midi)
#     print(f"MIDI file saved: {output_midi}")
#     print(f"MIDI file saved: {output_midi}")

def write_midi_pretty(selected_coughs, df, folder_path, output_midi, db_scale=30):
    drum_mapping = {
        "kick": 36,
        "snare": 38,
        "closed_hihat": 42,
        "open_hihat": 46,
        "mid_tom": 50,
        "low_tom": 45,
        "crash": 49
    }
    
    velocity_mapping = {
        "kick": 90,
        "snare": 95,
        "closed_hihat": 80,
        "open_hihat": 65,
        "mid_tom": 90,
        "low_tom": 90,
        "crash": 70
    }
    
    mid = pretty_midi.PrettyMIDI()
    for drum_type, cough_id in selected_coughs.items():
        row = df[df["id"] == str(cough_id)]
        if row.empty:
            print(f"Warning: No data found for ID {cough_id}")
            continue
        audio_path = os.path.join(folder_path, f"{cough_id}.wav")
        if not os.path.exists(audio_path):
            print(f"Warning: File {audio_path} not found.")
            continue
        audio_data, sr = audio.load_from_file(audio_path)
        print(f"Processing {cough_id}...", "drum_type:", drum_type)
        onset_times = detect(audio_data, sr)
        onset_times, offset_times = detect_offsets(audio_data, sr, onset_times)
        
        onset_loudness = [compute_loudness(audio_data[int(start * sr):int(end * sr)]) 
                          for start, end in zip(onset_times, offset_times)]
        if not onset_loudness:
            continue
        baseline_loudness = np.mean(onset_loudness)
        loudness_diffs = [loud - baseline_loudness for loud in onset_loudness]
        actual_max_diff = max(abs(min(loudness_diffs)), abs(max(loudness_diffs)))
        
        drum_track = pretty_midi.Instrument(program=0, is_drum=True)
        for onset_time, diff in zip(onset_times, loudness_diffs):
            if actual_max_diff != 0:
                normalized_diff = (diff / actual_max_diff) * db_scale
            else:
                normalized_diff = 0
            base_velocity = velocity_mapping.get(drum_type, 90)
           
            final_velocity = int(np.clip(base_velocity + normalized_diff, 1, 127))
            note = pretty_midi.Note(
                velocity=final_velocity,
                pitch=drum_mapping.get(drum_type, 38),
                start=onset_time,
                end=onset_time + 0.125
            )
            drum_track.notes.append(note)
        mid.instruments.append(drum_track)
    mid.write(output_midi)
    merge_midi_tracks(output_midi, output_midi)
    print(f"MIDI file saved: {output_midi}")
    
    

def merge_midi_tracks(input_midi, output_midi):
    midi_data = pretty_midi.PrettyMIDI(input_midi)
    merged_drum_track = pretty_midi.Instrument(program=0, is_drum=True)

    all_notes = []
    for instrument in midi_data.instruments:
        if instrument.is_drum:
            all_notes.extend(instrument.notes)

    all_notes.sort(key=lambda note: note.start)
    merged_drum_track.notes.extend(all_notes)

    merged_midi = pretty_midi.PrettyMIDI()
    merged_midi.instruments.append(merged_drum_track)
    merged_midi.write(output_midi)
    print(f"Merged MIDI saved: {output_midi}")

def generate_drum_motif(folder_path, target_id, output_midi):
    
    df = process_all_coughs(folder_path)
    df = normalize_and_rank(df)
    df = classify_coughs(df)
    selected_coughs = select_related_drums(df, target_id, 7)
    print(f"Selected coughs: {selected_coughs}")
    write_midi_pretty(selected_coughs, df, folder_path, output_midi)
    
    print(f"Drum motif generation to {output_midi } completed.")
