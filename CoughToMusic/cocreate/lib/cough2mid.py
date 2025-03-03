import audio, midi
from cough_to_midi import freq, onset
import glob
import os
import random
import itertools
import numpy as np
import soundfile as sf
from music21 import converter, key, interval
import pretty_midi
from pathlib import Path
import librosa

def normalize_wav_length(input_path, output_path, target_length_sec):
    y, sr = librosa.load(input_path, sr=None)   
    target_length_samples = int(target_length_sec * sr)   
    y_resampled = librosa.util.fix_length(y, size=target_length_samples)  
    sf.write(output_path, y_resampled, sr)

def cough_to_midi_wavs(
    threshold, freq_range_th, note_interval_th, min_target, max_target, num, energy_th, folder_path, out_dir="results"):
    recorded_coughs = Path("recorded_coughs").glob("cough_*.wav")
    for cough in recorded_coughs:
        cough = str(cough)
        normalize_wav_length(cough, cough, 4.0)
        # audio.remove_silence_from_start(cough, silence_threshold=-30.0, chunk_size=1) #trim the beginning of coughs
        file_index = cough.split("_")[-1].split(".")[0]
        cough_data, sample_rate = audio.load_from_file(cough)
        cough_freq = freq.get_by_crepe(cough_data, sample_rate, threshold, energy_threshold=energy_th)
        onset_time = onset.detect(cough_data, sample_rate) 
        # midi_file = f"./{out_dir}/{folder_path}_mid/{folder_path}_{file_index}.mid"
        midi_file = str(Path(out_dir) / f"{folder_path}_mid" / f"{folder_path}_{file_index}.mid")
        freq.write_midi(cough_data,sample_rate,cough_freq,midi_file,min_target,max_target,freq_range_th,note_interval_th,)
        if (freq.write_midi(cough_data,sample_rate,cough_freq,midi_file,min_target,max_target,freq_range_th,note_interval_th,)== False):
                continue
        else:
            midi_2bars = midi.to_2bars(midi_file, midi_file )  
            midi_2bars.save(midi_file)
            # midi.quantize_midi(midi_file, midi_file, num)  # quantize the midi
            # output_path = f"{out_dir}/{folder_path}_wav/{folder_path}_{file_index}.wav"  # write the coughs to wav
            if folder_path == "mel":
                midi.correct_midi_to_ref_key(midi_file, midi_file)
            else:
                ref_file = str(Path(out_dir) / "mel_mid" / f"mel_{file_index}.mid")
                midi.correct_midi_to_ref_key(ref_file, midi_file)
            output_path = str(Path(out_dir) / f"{folder_path}_wav" / f"{folder_path}_{file_index}.wav")
            midi.write_from_midi(midi_file, output_path, "piano")
            print(f"Wrote {output_path}")

cough_to_midi_wavs(0.3, 0.2, 20, "C3", "C6", 16, -50 ,"mel")
cough_to_midi_wavs(0.25, 0.25, 50, 'C2', 'C4', 16, -50, 'acc')
cough_to_midi_wavs(0.3, 0.95, 50, 'C1', 'C3', 4, -50, 'bass')

