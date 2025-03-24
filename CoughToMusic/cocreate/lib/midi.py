
import glob
import os
import audio
import pretty_midi
import mido
from mido import MidiFile, MidiTrack, MetaMessage, Message
import note_seq
import numpy as np
import pandas as pd
import music21
import soundfile as sf
from music21 import converter, key, note, pitch, chord, interval, midi, tempo
from pathlib import Path
import subprocess


# Harmonization

note_to_midi = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 
                'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11, 'D-': 1, 'E-': 3, 'G-': 6, 'A-': 8, 'B-': 10}

note_to_normalized_tone = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 
                'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}

circle_of_fifths = ['C', 'G', 'D', 'A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'F']

midi_to_note = {v: k for k, v in note_to_midi.items()}

def detect_key(midi_file_path):
    midi_data = converter.parse(midi_file_path)
    key_signature = midi_data.analyze('key')
    main_key = key_signature.tonic.name
    tonic_pitch = pitch.Pitch(key_signature.tonic.name)
    normalized_key = normalize_key_name_with_midi(key_signature.tonic.name)  # 使用標準化函式
    return normalized_key, key_signature.mode

def quantize_midi(input_midi_file, output_midi_file, num, qpm=120, ticks_per_beat=220):
    midi_data = pretty_midi.PrettyMIDI(input_midi_file)
    note_duration = 60 / (qpm * num)
    quantization_step = note_duration 
    print(f"Quantizing MIDI to {quantization_step} seconds")
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            note.start = round(note.start / quantization_step) * quantization_step
            note.end = round(note.end / quantization_step) * quantization_step
    midi_data.write(output_midi_file)

def pitch_to_note(pitch, transpose=-12):
    note_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    transposed_pitch = pitch + transpose
    note_name = note_names[transposed_pitch % 12]
    octave = (transposed_pitch // 12) - 1  # MIDI octave starts at -1 (C-1 is 0)
    return note_name, octave

def get_scale_notes(tonic, scale_type):
    """Returns the MIDI numbers for the notes in a given key."""
    major_scale_intervals = [0, 2, 4, 5, 7, 9, 11]  # Intervals for a major scale
    minor_scale_intervals = [0, 2, 3, 5, 7, 8, 10]  # Intervals for a natural minor scale
    tonic_midi = note_to_midi[tonic]  # Convert tonic to MIDI number
    if scale_type.lower() == "major":
        intervals = major_scale_intervals
    elif scale_type.lower() == "minor":
        intervals = minor_scale_intervals
    else:
        raise ValueError("Unsupported scale type. Use 'major' or 'minor'.")
    scale_notes = [(tonic_midi + interval) % 12 for interval in intervals]
    return scale_notes

def move_note_to_scale(note_pitch, scale_notes):
    """Move a note to the nearest pitch in the scale, keeping the same octave."""
    note_name_in_octave = note_pitch % 12  # Get the note in the same octave
    nearest_note = min(scale_notes, key=lambda n: abs(n - note_name_in_octave))
    new_pitch = note_pitch - note_name_in_octave + nearest_note
    return new_pitch

def correct_midi_to_key(midi_data, tonic, scale_type, output_file):
    scale_notes = get_scale_notes(tonic, scale_type)
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            original_pitch = note.pitch
            new_pitch = move_note_to_scale(original_pitch, scale_notes)
            if original_pitch != new_pitch:
                print(f"Correcting {midi_to_note[original_pitch % 12]} (Pitch {original_pitch}) "
                      f"to {midi_to_note[new_pitch % 12]} (Pitch {new_pitch})")
                note.pitch = new_pitch  # Correct the pitch
    midi_data.write(output_file)
    print(f"Corrected MIDI file saved as {output_file}")
    
def correct_midi_to_ref_key(midi_ref, midi_fp):
    ref_tone, ref_mode = detect_key(midi_ref)
    print(ref_tone, ref_mode)
    midi_data = pretty_midi.PrettyMIDI(midi_fp)
    correct_midi_to_key(midi_data, ref_tone, ref_mode, midi_fp)

def normalize_key_name_with_midi(key_name):
    """使用 MIDI 映射將調性名稱標準化為升記號格式"""
    midi_value = note_to_midi[key_name] 
    normalized_name = midi_to_note[midi_value]  
    return normalized_name

# midi to audio

import os
import subprocess
import shutil

def write_from_midi(midi_file, output_file, sf="drum"):
    print(f"Converting {midi_file} to WAV...")

    current_path = os.getcwd()
    conda_env = os.environ.get("CONDA_PREFIX")

    if not conda_env:
        raise EnvironmentError("Conda environment not found.")

    # Try to locate fluidsynth.exe automatically
    fluidsynth_path = shutil.which("fluidsynth")  
    if not fluidsynth_path:
        # Fallback: Assume it's inside Conda
        fluidsynth_path = os.path.join(conda_env, "Library", "bin", "fluidsynth.exe")
        # fluidsynth_path = "D:\Cough\PortableProgram\fluidsynth\lib\libfluidsynth.dll.a"
    
    # Ensure fluidsynth.exe exists
    if not os.path.exists(fluidsynth_path):
        raise FileNotFoundError(f"FluidSynth executable not found: {fluidsynth_path}")

    # Define SoundFont Paths (Windows-friendly paths)
    soundfonts = {
        "piano": os.path.join(current_path, "soundfonts", "Yamaha_C3_Grand_Piano.sf2"),
        "drum": os.path.join(current_path, "CoughToMusic\cocreate\soundfonts", "alex_gm.sf2"),
    }

    if sf not in soundfonts:
        raise ValueError(f"Invalid soundfont type '{sf}'. Choose from {list(soundfonts.keys())}.")

    soundfont = soundfonts[sf]

    if not os.path.exists(soundfont):
        raise FileNotFoundError(f"SoundFont file not found: {soundfont}")

    # Convert to absolute paths for Windows compatibility
    midi_file = os.path.abspath(midi_file)
    output_file = os.path.abspath(output_file)

    if not os.path.exists(midi_file):
        raise FileNotFoundError(f"MIDI file not found: {midi_file}")

    # Run FluidSynth Command
    command = [
        fluidsynth_path, "-ni", soundfont, midi_file, "-F", output_file, "-r", "44100"
    ]

    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if process.returncode != 0:
        print(f"Error: FluidSynth exited with code {process.returncode}")
        print(f"FluidSynth stderr: {process.stderr.strip()}")
    elif process.stderr.strip():
        print(f"Warning: FluidSynth stderr: {process.stderr.strip()}")
    else:
        print(f"WAV file successfully generated: {output_file}")


#midi meta adjustment

def get_tempo(midi_path):
    mid = mido.MidiFile(midi_path)
    for msg in mid:
        if msg.type == "set_tempo":
            return round(60000000 / msg.tempo)
    return 120  # Default tempo if not set in MIDI

def adjust_bpm(midi, target_bpm):
    tempo = mido.bpm2tempo(target_bpm)
    new_midi = MidiFile(ticks_per_beat=midi.ticks_per_beat)
    for track in midi.tracks:
        new_track = MidiTrack()
        new_midi.tracks.append(new_track)
        for msg in track:
            if msg.type == 'set_tempo':
                new_track.append(MetaMessage('set_tempo', tempo=tempo))
            else:
                new_track.append(msg)
    return new_midi

def calculate_measures(mid):
    tempo = mido.bpm2tempo(120)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempo = msg.tempo
                break
    
    ticks_per_beat = mid.ticks_per_beat
    total_ticks = sum(msg.time for track in mid.tracks for msg in track)
    total_seconds = mido.tick2second(total_ticks, ticks_per_beat, tempo)
    beats_per_minute = mido.tempo2bpm(tempo)
    total_beats = total_seconds / (60 / beats_per_minute)
    bar_num = total_beats / 4
    return bar_num, tempo

def adjust_ticks_per_beat(mid, new_ticks_per_beat=220):
    original_ticks_per_beat = mid.ticks_per_beat
    time_adjustment_factor = original_ticks_per_beat / new_ticks_per_beat

    new_mid = MidiFile(ticks_per_beat=new_ticks_per_beat)
    for track in mid.tracks:
        new_track = MidiTrack()
        new_mid.tracks.append(new_track)
        for msg in track:
            adjusted_time = int(msg.time / time_adjustment_factor)
            new_msg = msg.copy(time=adjusted_time)
            new_track.append(new_msg)
    return new_mid

def to_2bars(ori_midi_path, preprocessed_midi_path, default_tempo=True):
    mid = MidiFile(ori_midi_path)

    bar_num, tempo = calculate_measures(mid)
    target_bars = 2
    time_factor = target_bars / bar_num if bar_num != 0 else 1
    target_tempo = round(tempo / time_factor) if not default_tempo else mido.bpm2tempo(120)

    new_mid = MidiFile(ticks_per_beat=mid.ticks_per_beat)
    for track in mid.tracks:
        new_track = MidiTrack()
        new_mid.tracks.append(new_track)
        for msg in track:
            if msg.type in ['note_on', 'note_off']:
                new_msg = msg.copy(time=int(msg.time * time_factor))
                new_track.append(new_msg)
            elif not msg.is_meta or msg.type != 'set_tempo':
                new_track.append(msg)
            else:
                new_track.append(MetaMessage('set_tempo', tempo=target_tempo))

    new_mid = adjust_ticks_per_beat(new_mid, 220)
    new_mid.save(preprocessed_midi_path)
    print(f"Converted {ori_midi_path} to {preprocessed_midi_path} with 2 bars, 120 QPM, and 220 ticks per quarter note.")
    # return new_mid

#midi arrangement 

def concatenate(midi_files, output_file_path, tpb=220, qpm=120):
    output = mido.MidiFile(ticks_per_beat=tpb)
    output_track = mido.MidiTrack()
    output.tracks.append(output_track)
    two_bar_tick = int(4 * tpb * (qpm / 60))
    prev_total_time = 0

    for i, midi_file in enumerate(midi_files):
        print(f"prev_total_time {prev_total_time}")
        mid = mido.MidiFile(midi_file)
        current_track = mid.tracks[2]
        track_time = 0
        offset = 0
        if i == 0:
            for msg in current_track:
                if not msg.is_meta:
                    track_time += msg.time
                output_track.append(msg)
            prev_total_time = track_time
        else:
            for msg in current_track:
                if not msg.is_meta:
                    if track_time == 0:
                        offset = two_bar_tick - prev_total_time
                        print(f"offset: {offset}")
                        msg.time += offset
                        print(f"after msg.time: {msg.time}")
                    track_time += msg.time
                output_track.append(msg)
            prev_total_time = track_time - offset
    output.save(output_file_path)

def overlap_midi_files(mids, tpb):
    combined_midi = md.MidiFile(ticks_per_beat=tpb)
    for mid in mids:
        for track in mid.tracks:
            combined_midi.tracks.append(track)
    return combined_midi  

 
#midi features extraction

def note_density(midi_file_path):
    midi_data = converter.parse(midi_file_path)
    total_notes = len(midi_data.flat.getElementsByClass("Note"))
    total_measures = len(midi_data.getElementsByClass("Measure"))
    notes_per_measure = total_notes / total_measures
    print(f"Note Density: {notes_per_measure} notes per measure")

def pitch_range(midi_file_path):
    midi_data = converter.parse(midi_file_path)
    pitches = midi_data.pitches
    highest_pitch = max(pitches).midi
    lowest_pitch = min(pitches).midi
    pitch_range = highest_pitch - lowest_pitch
    average_pitch = sum(p.midi for p in pitches) / len(pitches)
    print(f"Pitch Range: {average_pitch}")

def print_midi_information(midi_file_path):# Load the MIDI file into a NoteSequence
    note_sequece = note_seq.midi_io.midi_file_to_note_sequence(midi_file_path)
    
    print(f"MIDI file: {midi_file_path}")
    print(f"Ticks per quarter note: {note_sequece.ticks_per_quarter}")
    print(f"Total time: {note_sequece.total_time} seconds")
    print(f"qpm: {note_sequece.tempos[0].qpm}")
    
    for tempo in note_sequece.tempos:
        print(f"Tempo: {tempo.qpm} BPM at time {tempo.time}")
    for time_signature in note_sequece.time_signatures:
        print(f"Time signature: {time_signature.numerator}/{time_signature.denominator} at time {time_signature.time}")
    for key_signature in note_sequece.key_signatures:
        print(f"Key signature: {key_signature.key} at time {key_signature.time}")
    print(f"Number of notes: {len(note_sequece.notes)}")
    for note in note_sequece.notes:
        print(f"Pitch {note.pitch}, Velocity {note.velocity}, "
              f"Note {pitch_to_note(note.pitch)}, "
              f"Start time {note.start_time}, End time {note.end_time}, "
              f"Instrument {note.instrument}, Program {note.program}")
    print(f"Number of instruments: {len(note_sequece.instrument_infos)}")
    for instrument_info in note_sequece.instrument_infos:
        print(f"Instrument name: {instrument_info.name}, Instrument {instrument_info.instrument}")

def note_shift(midi_file_path, desired_key):
    midi_stream = converter.parse(midi_file_path)
    current_key = midi_stream.analyze('key')
    print(f"Current key of the MIDI file: {current_key.tonic.name} {current_key.mode}")
    transpose_interval = interval.Interval(current_key.tonic, desired_key.tonic)
    print(f"Interval to transpose: {transpose_interval.semitones} semitones ({transpose_interval.directedName})")
    transposed_stream = midi_stream.transpose(transpose_interval)
    transposed_stream.write('midi', fp=midi_file_path)


def snap_on_grid_noteseq(midi_file_path, output_file_path, quantization_level):
    # Load MIDI as NoteSequence
    note_sequence = note_seq.midi_io.midi_file_to_note_sequence(midi_file_path)
    # Assume fixed QPM (or get from tempos)
    qpm = note_sequence.tempos[0].qpm
    seconds_per_beat = 60.0 / qpm
    grid_interval = seconds_per_beat / (quantization_level / 4)
    print(f"Quantizing with qpm={qpm}, grid_interval={grid_interval}")
    # Iterate and quantize notes
    for note in note_sequence.notes:
        print(f"Original program: {note.program}, instrument: {note.instrument}, is_drum: {note.is_drum}")
        # print(f"Original start: {note.start_time}, end: {note.end_time}") 
        new_start = round(note.start_time / grid_interval) * grid_interval
        new_end = new_start +0.125
        note.start_time = new_start
        note.end_time = new_end
        # print(f"New start: {note.start_time}, end: {note.end_time}")
    # Convert back to MIDI and save
    quantized_midi = note_seq.midi_io.note_sequence_to_pretty_midi(note_sequence)
    quantized_midi.write(output_file_path)
    print(f"Quantized MIDI saved as {output_file_path}")
    return note_sequence

# snap_on_grid_noteseq('./temp/dy_1.mid', './quantized_output.mid', 16)