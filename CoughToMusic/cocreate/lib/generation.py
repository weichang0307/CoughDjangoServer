import tensorflow_datasets as tfds
import tensorflow as tf
import numpy as np
import copy
import os
import logging
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
import magenta.music as mm
import pretty_midi
from model.music_vae import configs
from model.music_vae.trained_model import TrainedModel
import note_seq
import mido as md
import midi
from pathlib import Path
from note_seq.protobuf import music_pb2

logger = logging.getLogger(__name__)

"""
HELPER FUNCTIONS

"""
def create_tensor_from_sequence(note_seq):
    new_note_sequence = music_pb2.NoteSequence()
    new_note_sequence.ticks_per_quarter = note_seq.ticks_per_quarter
    if note_seq.tempos:
        new_note_sequence.tempos.add().qpm = note_seq.tempos[0].qpm
    if note_seq.time_signatures:
        time_signature = new_note_sequence.time_signatures.add()
        time_signature.numerator = note_seq.time_signatures[0].numerator
        time_signature.denominator = note_seq.time_signatures[0].denominator

    qpm = note_seq.tempos[0].qpm if note_seq.tempos else 120.0
    seconds_per_quarter = 60.0 / qpm
    eighth_note_duration = seconds_per_quarter / 2
    for note in note_seq.notes:
        new_note = new_note_sequence.notes.add()
        new_note.pitch = note.pitch
        new_note.start_time = round(note.start_time / eighth_note_duration) * eighth_note_duration
        new_note.end_time = round(note.end_time / eighth_note_duration) * eighth_note_duration
        new_note.velocity = note.velocity

    # Update total_time
    new_note_sequence.total_time = max(note.end_time for note in new_note_sequence.notes)

    return new_note_sequence

def path_to_note_seq(midi_path_start, midi_path_end):
    start_pm = pretty_midi.PrettyMIDI(midi_path_start)
    end_pm = pretty_midi.PrettyMIDI(midi_path_end)
    start_note_seq = mm.midi_to_note_sequence(start_pm)
    end_note_seq = mm.midi_to_note_sequence(end_pm)
    return start_note_seq, end_note_seq

def normalize_sequence_duration(note_seq, target_duration=4.0):
    if note_seq.total_time < target_duration:
        time_padding = target_duration - note_seq.total_time
        silence_note = note_seq.notes.add()
        silence_note.start_time = note_seq.total_time
        silence_note.end_time = target_duration
        silence_note.velocity = 0  # Add silence at the end
    elif note_seq.total_time > target_duration:
        note_seq = note_seq.trim(0, target_duration)
    note_seq.total_time = target_duration
    return note_seq

def concatenate_sequences(midi_path_start, midi_path_end, output_path):
    start_note_seq, end_note_seq = path_to_note_seq(midi_path_start, midi_path_end)
    
    all_seq = [start_note_seq]  + [end_note_seq] 
    # print(start_note_seq.total_time)
    seq_durations =  (
        [4.0]
        + [end_note_seq.total_time]
    )
    final_seq = mm.sequences_lib.concatenate_sequences(all_seq, seq_durations)
    mm.sequence_proto_to_midi_file(final_seq, output_path)


def concatenate_note_sequence_objects(start_note_seq, end_note_seq, output_path, start_duration=4.0):
    final_seq = mm.sequences_lib.concatenate_sequences(
        [start_note_seq, end_note_seq],
        [start_duration, end_note_seq.total_time],
    )
    mm.sequence_proto_to_midi_file(final_seq, output_path)


def concate_interpolation(start_note_seq, end_note_seq, interp_note_seq, output_path, target_duration=4.0):
    interp_note_seq = [normalize_sequence_duration(seq, target_duration) for seq in interp_note_seq]
    # print(f'concate:', interp_note_seq)

    if end_note_seq == None:
        all_seq = [start_note_seq] + interp_note_seq
        seq_durations = (
            [start_note_seq.total_time]
            + [seq.total_time for seq in interp_note_seq]
        )
    else:
        all_seq = [start_note_seq] + interp_note_seq + [end_note_seq] 
        
        seq_durations =  (
            [start_note_seq.total_time]
            + [seq.total_time for seq in interp_note_seq]+ [end_note_seq.total_time]
        )
    final_seq = mm.sequences_lib.concatenate_sequences(all_seq, seq_durations)
    mm.sequence_proto_to_midi_file(final_seq, output_path)


# def concatenate_midi(sequences, output_path, segment_duration=4.0):
#     normalized_sequences = [normalize_to_zero(seq) for seq in sequences]
#     durations = [segment_duration] * len(normalized_sequences)
#     final_seq = mm.sequences_lib.concatenate_sequences(normalized_sequences, durations)
#     mm.sequence_proto_to_midi_file(final_seq, output_path)
#     print(f"Concatenated MIDI saved to {output_path}")
#     return final_seq
# import random

# def ensure_min_note_density(note_seq, min_notes, total_time=4.0):
#     if len(note_seq.notes) >= min_notes:
#         return note_seq
    
#     min_pitch =min(n.pitch for n in note_seq.notes)
#     max_pitch =max(n.pitch for n in note_seq.notes)
#     pitch_range = (min_pitch, max_pitch) if min_pitch < max_pitch else (0, 127)
#     # Collect existing note start times to avoid overlap
#     existing_times = {(n.start_time, n.pitch) for n in note_seq.notes}
    
#     # Generate random non-overlapping notes
#     while len(note_seq.notes) < min_notes:
#         start = round(random.uniform(0, total_time - 0.1), 2)
#         duration = 0.25
#         pitch = random.randint(*pitch_range)
#         if (start, pitch) in existing_times:
#             continue
#         note = note_seq.notes.add()
#         note.start_time = start
#         note.end_time = start + duration
#         note.pitch = pitch
#         note.velocity = 80
#         note.instrument = 0
#         note.program = 0
#         existing_times.add((start, pitch))

#     note_seq.total_time = max(note.end_time for note in note_seq.notes)
#     print(f'modify to {len(note_seq.notes)}' )
#     return note_seq

# def ensure_min_note_density(note_seq, min_notes, total_time=4.0):
#     if len(note_seq.notes) >= min_notes and note_seq.total_time >= total_time:
#         return note_seq

#     min_pitch = min(n.pitch for n in note_seq.notes)
#     max_pitch = max(n.pitch for n in note_seq.notes)
#     pitch_range = (min_pitch, max_pitch) if min_pitch < max_pitch else (0, 127)
#     # Collect existing note start times to avoid overlap
#     existing_times = {(n.start_time, n.pitch) for n in note_seq.notes}

#     # Generate random non-overlapping notes
#     while len(note_seq.notes) < min_notes:
#         start = round(random.uniform(0, total_time - 0.125), 2)
#         duration = 0.125
#         pitch = random.randint(*pitch_range)
#         if (start, pitch) in existing_times:
#             continue
#         note = note_seq.notes.add()
#         note.start_time = start
#         note.end_time = start + duration
#         note.pitch = pitch
#         note.velocity = 80
#         note.instrument = 0
#         note.program = 0
#         existing_times.add((start, pitch))

    # # Check if total time is less than 4.0 and add a note from 3.875 to 4.0
    # if note_seq.total_time < total_time:
    #     last_note_pitch = note_seq.notes[-1].pitch if note_seq.notes else 60  # Default to pitch 60 if no notes
    #     note = note_seq.notes.add()
    #     note.start_time = 3.875
    #     note.end_time = 4.0
    #     note.pitch = last_note_pitch
    #     note.velocity = 80
    #     note.instrument = 0
    #     note.program = 0

    # note_seq.total_time = max(note.end_time for note in note_seq.notes)
    # print(f'modify to {len(note_seq.notes)} notes, total time: {note_seq.total_time}')
    # return note_seq
def ensure_min_note_density(note_seq, min_notes, total_time=4.0):
    import random

    duration = 0.125
    if len(note_seq.notes) >= min_notes and note_seq.total_time >= total_time:
        return note_seq

    notes = sorted(note_seq.notes, key=lambda n: n.start_time)
    intervals = []
    prev_end = 0.0
    prev_pitch = None

    for i, n in enumerate(notes):
        start, end = n.start_time, n.end_time
        if start - prev_end >= duration:
            next_pitch = n.pitch
            intervals.append({
                "start": prev_end,
                "end": start,
                "length": start - prev_end,
                "prev_pitch": prev_pitch,
                "next_pitch": next_pitch
            })
        prev_end = max(prev_end, end)
        prev_pitch = n.pitch

    # Tail gap
    if total_time - prev_end >= duration:
        intervals.append({
            "start": prev_end,
            "end": total_time,
            "length": total_time - prev_end,
            "prev_pitch": prev_pitch,
            "next_pitch": None
        })

    intervals.sort(key=lambda x: -x["length"])  # biggest gap first
    existing = {(n.start_time, n.pitch) for n in note_seq.notes}

    while len(note_seq.notes) < min_notes and intervals:
        interval = intervals.pop(0)
        legal_start = interval["start"]
        legal_end = interval["end"]
        max_start = legal_end - duration
        if legal_start > max_start:
            continue

        start = round(random.uniform(legal_start, max_start), 3)
        pp, np = interval["prev_pitch"], interval["next_pitch"]
        if pp is not None and np is not None:
            low, high = sorted([pp, np])
        elif pp is not None:
            low, high = pp - 2, pp + 2
        elif np is not None:
            low, high = np - 2, np + 2
        else:
            low, high = 60, 72  # fallback pitch range

        pitch = random.randint(max(0, low), min(127, high))
        if (start, pitch) in existing:
            continue

        note = note_seq.notes.add()
        note.start_time = start
        note.end_time = start + duration
        note.pitch = pitch
        note.velocity = 80
        note.instrument = 0
        note.program = 0
        existing.add((start, pitch))
    # Check if total time is less than 4.0 and add a note from 3.875 to 4.0
    if note_seq.total_time < total_time:
        last_note_pitch = note_seq.notes[-1].pitch if note_seq.notes else 60  # Default to pitch 60 if no notes
        note = note_seq.notes.add()
        note.start_time = 3.875
        note.end_time = 4.0
        note.pitch = last_note_pitch
        note.velocity = 80
        note.instrument = 0
        note.program = 0

    note_seq.total_time = max(note.end_time for note in note_seq.notes)
    return note_seq


"""MELODY GENERATION , MELODY INTERPOLATIOAN FUNCTIONS"""

def generate_16_mel():
    mel_16bar_models = {}
    hierdec_mel_16bar_config = configs.CONFIG_MAP["hierdec-mel_16bar"]
    model_path = "./model/hierdec-mel_16bar/hierdec-mel_16bar.ckpt"
    mel_16bar_models["hierdec_mel_16bar"] = TrainedModel(
        hierdec_mel_16bar_config, batch_size=4, checkpoint_dir_or_path=model_path
    )
    mel_sample_model = (
        "hierdec_mel_16bar"  # @param ["hierdec_mel_16bar", "baseline_flat_mel_16bar"]
    )
    temperature = 0.5  # @param {type:"slider", min:0.1, max:1.5, step:0.1}
    mel_16_samples = mel_16bar_models[mel_sample_model].sample(
        n=4, length=256, temperature=temperature
    )
    for i, ns in enumerate(mel_16_samples):
        mm.sequence_proto_to_midi_file(ns, f"./mel_16bar_{i}.mid")

def interpolate_melody_tensors(
    start_note_seq, end_note_seq, num_steps, config_name, max_length=32, temperature=0.5):

    start_note_seq = ensure_min_note_density(start_note_seq, min_notes=5, total_time=4.0)
    end_note_seq = ensure_min_note_density(end_note_seq, min_notes=5, total_time=4.0)

    model_path = str(Path("CoughToMusic/cocreate/model") / config_name / f"{config_name}.ckpt")
    data_converter = configs.CONFIG_MAP["cat-mel_2bar_big"].data_converter
    music_vae = TrainedModel(configs.CONFIG_MAP["cat-mel_2bar_big"], batch_size=4, checkpoint_dir_or_path=model_path)
    try:
        s_input_output = data_converter.to_tensors(start_note_seq)
        # print("s_input_output:", s_input_output)
        s_tensors = s_input_output[0] if s_input_output[0] else s_input_output[1]
        start_tensors = data_converter.from_tensors(s_tensors)

        e_input_output = data_converter.to_tensors(end_note_seq)
        # print("e_input_output:", e_input_output)
        e_tensors = e_input_output[0] if e_input_output[0] else e_input_output[1]
        end_tensors = data_converter.from_tensors(e_tensors)
    except Exception as e:
        logger.exception("Error converting to tensors")


    # fallback if either list is empty
    if not start_tensors and not end_tensors:
        raise ValueError("Both start and end tensors are empty. Cannot interpolate.")
    elif not start_tensors:
        logger.warning("Start tensors empty. Using end tensor for both start and end.")
        start_tensors = end_tensors
    elif not end_tensors:
        logger.warning("End tensors empty. Using start tensor for both start and end.")
        end_tensors = start_tensors

    start_tensor = next((t for t in start_tensors if t.total_time > 3.5), start_tensors[0])
    end_tensor = next((t for t in end_tensors if t.total_time > 3.5), end_tensors[0])

    try:
        note_sequences = music_vae.interpolate(
            start_tensor,
            end_tensor,
            num_steps=num_steps,
            length=max_length,
            temperature=temperature,
        )
    except Exception as e:
        logger.exception("Interpolation failed")

    return note_sequences


def melody_interpolation(start_midi_path, end_midi_path, interp_output_path , num_steps, is_first):

    start_note_seq, end_note_seq = path_to_note_seq(start_midi_path, end_midi_path)
    interpolated_seq = interpolate_melody_tensors(
        start_note_seq, end_note_seq, num_steps, config_name="cat-mel_2bar_big"
    )

    if is_first == True:
        concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, interp_output_path)
    elif is_first == False:
        first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
        first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
        concate_interpolation(first_inp_note_seq, end_note_seq, interpolated_seq, interp_output_path)
    elif is_first == None:
        first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
        first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
        concate_interpolation(first_inp_note_seq, is_first, interpolated_seq, interp_output_path)
    note_seq.midi_io.midi_file_to_note_sequence(interp_output_path)
    # return interpolated_note_sequence


def generate_melody_from_sequence(sequence, interp_output_path):
    """Generates melodies based on the given order."""
    num_steps_map = {2: [3, 3], 3: [1, 1, 3], 4: [1, 1, 1, 1]}
    if len(sequence) not in num_steps_map:
        raise ValueError("Only sequences of length 2, 3, or 4 are supported.")
    num_steps = num_steps_map[len(sequence)]
    # Generate interpolations in order
    for i in range(len(sequence)):
        start_midi_path = sequence[i]
        end_midi_path = sequence[(i + 1) % len(sequence)]
        is_first = True if i == 0 else (None if i == len(sequence) - 1 else False)
        # print('f{num_steps[i]}:', num_steps[i])
        melody_interpolation(start_midi_path, end_midi_path, interp_output_path, num_steps[i], is_first)

"""
DRUM ACCOMPANIMENT GENERATION, DRUM INTERPOLATION , GENERATE GROOVE VARIATION FUNCTIONS"""

def interpolate_drum_tensors(
    start_note_seq, end_note_seq, num_steps, max_length=32, temperature=0.5):
    # model_path = f"./model/drums_2bar_oh_hikl/drums_2bar_oh_hikl.ckpt"
    model_path = str(Path("CoughToMusic/cocreate/model") / "cat-drums_2bar_small.hikl" / "cat-drums_2bar_small.hikl.ckpt")
    drums_config = configs.CONFIG_MAP["cat-drums_2bar_small"]
    data_converter = drums_config.data_converter
    music_vae = TrainedModel(
        drums_config, batch_size=4, checkpoint_dir_or_path=model_path
    )
    start_tensors = drums_config.data_converter.from_tensors(data_converter.to_tensors(start_note_seq)[1])
    end_tensors = drums_config.data_converter.from_tensors(data_converter.to_tensors(end_note_seq)[1])
    # print("start_tensors:", start_tensors)
    # print("end_tensors", end_tensors)
    start_tensor = next((tensor for tensor in start_tensors if tensor.total_time >3.5 ), start_tensors[0])
    end_tensor = next((tensor for tensor in end_tensors if tensor.total_time >3.5), end_tensors[0])
    # print("start_tensors:", start_tensors)
    # print("end_tensors", end_tensors)
    note_sequences = music_vae.interpolate(
        start_tensor,
        end_tensor,
        num_steps=num_steps,
        length=max_length,
        temperature=temperature,
    )
    return note_sequences

def drum_interpolation(start_midi_path, end_midi_path, interp_output_path, num_steps, is_first):
    start_note_seq, end_note_seq = path_to_note_seq(start_midi_path, end_midi_path)
    interpolated_seq = interpolate_drum_tensors(start_note_seq, end_note_seq, num_steps)
    # print("interpolated_seq:", interpolated_seq)
    if is_first == True:
        concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, interp_output_path)
    elif is_first == False:
        first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
        first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
        concate_interpolation(first_inp_note_seq, end_note_seq, interpolated_seq, interp_output_path)
    elif is_first == None:
        first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
        first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
        concate_interpolation(first_inp_note_seq, is_first, interpolated_seq, interp_output_path)
    interpolated_note_sequence = note_seq.midi_io.midi_file_to_note_sequence(interp_output_path)

    # print("drum interpolate generated")
    return interpolated_note_sequence

def drumify(s, temperature=1.0):
    config_2bar_tap = configs.CONFIG_MAP["groovae_2bar_tap_fixed_velocity"]
    groovae_2bar_tap = TrainedModel(
        config_2bar_tap,
        1,
        # checkpoint_dir_or_path="./model/groovae_2bar_tap_fixed_velocity/model.ckpt-3668",
        checkpoint_dir_or_path=str(Path("CoughToMusic/cocreate/model") / "groovae_2bar_tap_fixed_velocity" / "model.ckpt-3668"),
        
    )
    encoding, mu, sigma = groovae_2bar_tap.encode([s])
    decoded = groovae_2bar_tap.decode(encoding, length=32, temperature=temperature)
    return decoded[0]

def set_to_drums(ns):
    for n in ns.notes:
        n.instrument = 9
        n.is_drum = True

def start_notes_at_0(seq):
    for n in seq.notes:
        if n.start_time < 0:
            n.end_time -= n.start_time
            n.start_time = 0
    return seq

def change_tempo(note_sequence, new_tempo):
    new_sequence = copy.deepcopy(note_sequence)
    ratio = note_sequence.tempos[0].qpm / new_tempo
    for note in new_sequence.notes:
        note.start_time *= ratio
        note.end_time *= ratio
    new_sequence.tempos[0].qpm = new_tempo
    return new_sequence

def humanize(s, model, temperature=1):  
    encoding, mu, sigma = model.encode([s])
    decoded = model.decode(encoding, length=32,  temperature=temperature )[0]
    return change_tempo(decoded, s.tempos[0].qpm)

def generate_humanize_groove(mid_pth, output_pth):

    config_2_bar_humanize = configs.CONFIG_MAP['groovae_2bar_humanize']

    model_path = str(Path("CoughToMusic/cocreate/model") / "groovae_2bar_humanize" / "model.ckpt-3061")
    groovae_model = TrainedModel(config_2_bar_humanize, batch_size=1, checkpoint_dir_or_path=model_path)
    origin_pm = pretty_midi.PrettyMIDI(mid_pth)
    original_seq = mm.midi_to_note_sequence(origin_pm)
    set_to_drums(original_seq)
    q_ns = midi.snap_on_grid_noteseq(mid_pth, output_pth, 16)
    humanized_seqs = []
    for i in range(3):
        seq = humanize(q_ns if i == 0 else humanized_seqs[i-1], groovae_model)
        humanized_seqs.append(seq)
    
    for seq in humanized_seqs:
        for note in seq.notes:
            note.velocity = min(note.velocity + 60, 127)

    combined_seq = music_pb2.NoteSequence()
    current_time = 0.0
    # Add original sequence notes first
    for note in original_seq.notes:
        new_note = combined_seq.notes.add()
        new_note.CopyFrom(note)
        new_note.start_time += current_time
        new_note.end_time += current_time
    current_time = max(n.end_time for n in combined_seq.notes)
    # Add the 3 humanized sequences one after another
    for seq in humanized_seqs:
        
        for note in seq.notes:
            new_note = combined_seq.notes.add()
            new_note.CopyFrom(note)
            new_note.start_time += current_time
            new_note.end_time += current_time
        current_time = max(n.end_time for n in combined_seq.notes)
    combined_seq.tempos.add(qpm=original_seq.tempos[0].qpm if original_seq.tempos else 120.0)
    
    note_seq.sequence_proto_to_midi_file(combined_seq, output_pth)


def interpolated_groove_note_sequences(start_note_seq, end_note_seq, steps=2):
    config_4_bar = configs.CONFIG_MAP['groovae_4bar']
    model_path = str(Path("CoughToMusic/cocreate/model") / "groovae_4bar" / "model.ckpt-2721")
    groovae_model = TrainedModel(config_4_bar, batch_size=1, checkpoint_dir_or_path=model_path)
    start_outputs = config_4_bar.data_converter.to_tensors(start_note_seq).outputs
    end_outputs = config_4_bar.data_converter.to_tensors(end_note_seq).outputs
    start_tensors = config_4_bar.data_converter.from_tensors(start_outputs)
    end_tensors = config_4_bar.data_converter.from_tensors(end_outputs)
    if not start_tensors or not end_tensors:
        raise ValueError(
            "Groove interpolation could not tensorize staged drum MIDI inputs for the groovae_4bar model."
        )

    start_tensor = start_tensors[0]
    # print(f'start_tensor: {start_tensor}')

    end_tensor = end_tensors[0]
    # print(f'end_tensor: {end_tensor}')
    interpolated_seq = groovae_model.interpolate(start_tensor, end_tensor, steps, length=64, temperature=1.5)
    for seq in interpolated_seq:
        for note in seq.notes:
            note.velocity = min(note.velocity + 55, 127)
    # print(f"Interpolated drum sequence generated {len(interpolated_seq)}")
    
    return interpolated_seq


def interpolated_groove(start_path, end_path, interp_output_path, steps =2):
    start_note_seq, end_note_seq = path_to_note_seq(start_path, end_path)
    return interpolated_groove_note_sequences(start_note_seq, end_note_seq, steps=steps)
  

# #import magenta.music as mm
# import note_seq
# from note_seq.protobuf import music_pb2

# def normalize_to_zero(seq):
#     if not seq.notes:
#         return seq
#     min_start = min(n.start_time for n in seq.notes)
#     for n in seq.notes:
#         n.start_time -= min_start
#         n.end_time -= min_start
#     return seq

# def midi_path_to_note_sequence(midi_path):
#     pm = mm.midi_io.midi_file_to_note_sequence(midi_path)
#     return pm

# def concatenate_two_midis(midi_path_1, midi_path_2, output_path, segment_duration=4.0):
#     seq1 = midi_path_to_note_sequence(midi_path_1)
#     seq2 = midi_path_to_note_sequence(midi_path_2)
    
#     seq1 = normalize_to_zero(seq1)
#     print(f"seq1 total time: {seq1.total_time:.3f}")
#     print(f"seq1 notes:", seq1.notes)

#     seq2 = normalize_to_zero(seq2)
#     print(f"seq2 total time: {seq2.total_time:.3f}")
#     print(f"seq2 notes:", seq2.notes)

#     all_seq = [seq1, seq2]
#     durations = [segment_duration] * 2

#     final_seq = mm.sequences_lib.concatenate_sequences(all_seq, durations)
#     for note in final_seq.notes:
#         print(f"{note.start_time:.3f}", note.pitch)
#     mm.sequence_proto_to_midi_file(final_seq, output_path)
#     print(f"Saved concatenated MIDI to: {output_path}")

# # Example usage:
# concatenate_two_midis(
#     './media/public_motif/mel_mid/mel_11.mid',
#     './media/public_motif/mel_mid/mel_15.mid',
#     './concatenated.mid',
#     segment_duration=4.0
# )

# melody_interpolation('./media/public_motif/mel_mid/mel_11.mid','./media/public_motif/mel_mid/mel_15.mid', './interpolated.mid', 3, True)
