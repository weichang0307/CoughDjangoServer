import tensorflow_datasets as tfds
import tensorflow as tf
import numpy as np
import copy
import os
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
    print("Converting to NoteSequence...", end="")
    start_pm = pretty_midi.PrettyMIDI(midi_path_start)
    end_pm = pretty_midi.PrettyMIDI(midi_path_end)
    start_note_seq = mm.midi_to_note_sequence(start_pm)
    end_note_seq = mm.midi_to_note_sequence(end_pm)
    print("Done")
    return start_note_seq, end_note_seq

# def generate_16_mel():
#     mel_16bar_models = {}
#     hierdec_mel_16bar_config = configs.CONFIG_MAP["hierdec-mel_16bar"]
#     model_path = "./model/hierdec-mel_16bar/hierdec-mel_16bar.ckpt"
#     mel_16bar_models["hierdec_mel_16bar"] = TrainedModel(
#         hierdec_mel_16bar_config, batch_size=4, checkpoint_dir_or_path=model_path
#     )
#     mel_sample_model = (
#         "hierdec_mel_16bar"  # @param ["hierdec_mel_16bar", "baseline_flat_mel_16bar"]
#     )
#     temperature = 0.5  # @param {type:"slider", min:0.1, max:1.5, step:0.1}
#     mel_16_samples = mel_16bar_models[mel_sample_model].sample(
#         n=4, length=256, temperature=temperature
#     )
#     for i, ns in enumerate(mel_16_samples):
#         mm.sequence_proto_to_midi_file(ns, f"./mel_16bar_{i}.mid")


def normalize_sequence_duration(note_seq, target_duration=4.0):
    if note_seq.total_time < target_duration:
        time_padding = target_duration - note_seq.total_time
        silence_note = note_seq.notes.add()
        silence_note.start_time = note_seq.total_time
        silence_note.end_time = target_duration
        silence_note.velocity = 0  # Add silence at the end
    note_seq.total_time = target_duration
    return note_seq

def interpolate_melody_tensors(
    start_note_seq, end_note_seq, num_steps, config_name, max_length=32, temperature=0.5):
    # model_path = f"./model/{config_name}/{config_name}.ckpt"
    model_path = str(Path("CoughToMusic/cocreate/model") / config_name / f"{config_name}.ckpt")
    data_converter = configs.CONFIG_MAP["cat-mel_2bar_big"].data_converter
    music_vae = TrainedModel(configs.CONFIG_MAP["cat-mel_2bar_big"], batch_size=4, checkpoint_dir_or_path=model_path)
    

    start_tensors = data_converter.from_tensors(data_converter.to_tensors(start_note_seq)[1])
    # print(data_converter.to_tensors(start_note_seq))
    
    end_tensors = data_converter.from_tensors(data_converter.to_tensors(end_note_seq)[1])
    # print("start_noteseq:", start_note_seq)

    start_tensor = next((tensor for tensor in start_tensors if tensor.total_time >3.5), None)
    end_tensor = next((tensor for tensor in end_tensors if tensor.total_time >3.5), None)     
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

def concate_interpolation(start_note_seq, end_note_seq, interp_note_seq, output_path, target_duration=4.0):
    interp_note_seq = [normalize_sequence_duration(seq, target_duration) for seq in interp_note_seq]

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
    return print(f"Interpolated MIDI file has been saved to: {output_path}")

def interpolate_drum_tensors(
    start_note_seq, end_note_seq, num_steps, max_length=32, temperature=0.5):
    # model_path = f"./model/drums_2bar_oh_hikl/drums_2bar_oh_hikl.ckpt"
    model_path = str(Path("model") / "cat-drums_2bar_small.hikl" / "cat-drums_2bar_small.hikl.ckpt")
    drums_config = configs.CONFIG_MAP["cat-drums_2bar_small"]
    data_converter = drums_config.data_converter
    music_vae = TrainedModel(
        drums_config, batch_size=4, checkpoint_dir_or_path=model_path
    )
    start_tensors = drums_config.data_converter.from_tensors(data_converter.to_tensors(start_note_seq)[1])
    end_tensors = drums_config.data_converter.from_tensors(data_converter.to_tensors(end_note_seq)[1])
    # print("start_tensors:", start_tensors)
    # print("end_tensors", end_tensors)
    start_tensor = next((tensor for tensor in start_tensors if tensor.total_time >3.5 ), None)
    end_tensor = next((tensor for tensor in end_tensors if tensor.total_time >3.5), None)
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
    print("interpolated_seq:", interpolated_seq)
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

    print("drum interpolate generated")
    return interpolated_note_sequence

def drumify(s, temperature=1.0):
    config_2bar_tap = configs.CONFIG_MAP["groovae_2bar_tap_fixed_velocity"]
    groovae_2bar_tap = TrainedModel(
        config_2bar_tap,
        1,
        # checkpoint_dir_or_path="./model/groovae_2bar_tap_fixed_velocity/model.ckpt-3668",
        checkpoint_dir_or_path=str(Path("model") / "groovae_2bar_tap_fixed_velocity" / "model.ckpt-3668"),
        
    )
    encoding, mu, sigma = groovae_2bar_tap.encode([s])
    decoded = groovae_2bar_tap.decode(encoding, length=32, temperature=temperature)
    return decoded[0]

# def generate_drum_seq(melody_seq, output_file_path):
#     def split_and_normalize_note_sequence(note_sequence, tpb, qpm):
#         ticks_per_two_bars = tpb * 4 * 2
#         seconds_per_tick = 60.0 / (qpm * tpb)
#         seconds_per_two_bars = ticks_per_two_bars * seconds_per_tick

#         def create_segment_with_metadata(start_time, end_time):
#             segment = note_seq.NoteSequence()
#             segment.ticks_per_quarter = note_sequence.ticks_per_quarter
#             segment.time_signatures.extend(note_sequence.time_signatures)
#             segment.tempos.extend(note_sequence.tempos)
#             segment.total_time = min(
#                 4, end_time - start_time
#             )  # Normalize total time to max 4 seconds per segment
#             segment.source_info.CopyFrom(note_sequence.source_info)
#             segment.instrument_infos.extend(note_sequence.instrument_infos)
#             for note in note_sequence.notes:
#                 if note.start_time >= start_time and note.start_time < end_time:
#                     new_note = segment.notes.add()
#                     new_note.CopyFrom(note)
#                     new_note.start_time -= start_time
#                     new_note.end_time -= start_time
#             return segment

#         total_duration = note_sequence.total_time
#         segments = []
#         current_start = 0
#         while current_start < total_duration:
#             current_end = min(current_start + seconds_per_two_bars, total_duration)
#             segment = create_segment_with_metadata(current_start, current_end)
#             segments.append(segment)
#             current_start = current_end
#         return segments

#     two_bar_segments = split_and_normalize_note_sequence(melody_seq, 220, 120)
#     midi_ls = []
#     for i, segment in enumerate(two_bar_segments):
#         print(f"\nSegment {i + 1} has {len(segment.notes)} notes")
#         # output_drum_path = f"temp/output_drum_sequence_{i}.mid"
#         output_drum_path = str(Path("temp") / f"output_drum_sequence_{i}.mid")
#         drum_seq = drumify(segment, temperature=1.0)
#         note_seq.sequence_proto_to_midi_file(drum_seq, output_drum_path)
#         midi_ls.append(output_drum_path)
#     midi.concatenate(midi_ls, output_file_path)
#     print("Drum sequence generated")
#     return md.MidiFile(output_file_path)

# musicVAE interpolation functions

# def melody_interpolation(start_idx, end_idx, intp_idx , track, num_steps, is_first):
#     # start_midi_path = f"./results/{track}_mid/cough_{start_idx}.mid"
#     start_midi_path = str(Path("results") / f"{track}_mid" / f"{track}_{start_idx}.mid")
#     end_midi_path = str(Path("results") / f"{track}_mid" / f"{track}_{end_idx}.mid")
#     interp_output_path = str(Path("tracks") / f"{track}_mid" / f"{track}_{intp_idx}.mid")
#     start_note_seq, end_note_seq = path_to_note_seq(start_midi_path, end_midi_path)
#     interpolated_seq = interpolate_melody_tensors(
#         start_note_seq, end_note_seq, num_steps, config_name="cat-mel_2bar_big"
#     )
#     if is_first == True:
#         concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, interp_output_path)
#     elif is_first == False:
#         first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
#         first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
#         concate_interpolation(first_inp_note_seq, end_note_seq, interpolated_seq, interp_output_path)
#     elif is_first == None:
#         first_inp_mid = pretty_midi.PrettyMIDI(interp_output_path)
#         first_inp_note_seq = mm.midi_to_note_sequence(first_inp_mid)
#         concate_interpolation(first_inp_note_seq, is_first, interpolated_seq, interp_output_path)
#     interpolated_note_sequence = note_seq.midi_io.midi_file_to_note_sequence(interp_output_path)
#     print("melody interpolate generated")
#     # return interpolated_note_sequence





# def drum_accompany(melody_seq, drum_output_path):
#     drum_midi = generate_drum_seq(melody_seq, drum_output_path)
#     print("Drum sequence generated")
#     return drum_midi


# mel_seq1 =  note_seq.midi_io.midi_file_to_note_sequence('./cough_to_midi/midis/cough_6.mid')
# mel_seq2 =  note_seq.midi_io.midi_file_to_note_sequence('./cough_to_midi/midis/cough_1.mid')
# mel_seq3 =  note_seq.midi_io.midi_file_to_note_sequence('./cough_to_midi/midis/cough_15_q.mid')

# drum_accompany(mel_seq1, './temp/drum_output.mid')
# drum_accompany(mel_seq2, './temp/drum_output2.mid')
# drum_accompany(mel_seq3, './temp/drum_output3.mid')

# def generate_melody_from_sequence(sequence, track, id):
#     """Generates melodies based on the given order."""
#     num_steps_map = {2: [3, 3], 3: [1, 1, 3], 4: [1, 1, 1, 1]}
#     if len(sequence) not in num_steps_map:
#         raise ValueError("Only sequences of length 2, 3, or 4 are supported.")
#     num_steps = num_steps_map[len(sequence)]
#     print(f"Generating melody for track: {track} with sequence {sequence}")
#     # Generate interpolations in order
#     for i in range(len(sequence)):
#         start_idx = sequence[i]
#         end_idx = sequence[(i + 1) % len(sequence)]
#         is_first = True if i == 0 else (None if i == len(sequence) - 1 else False)
#         melody_interpolation(start_idx, end_idx, id, track, num_steps[i], is_first)

#     print("Melody generation completed.")
        
# melody_generation([16, 15, 1], 'bass', 1)

# melody_interpolation('./cough_to_midi/midis/cough_8_q.mid', './cough_to_midi/midis/cough_5_q.mid', 'temp/interpolated_acc.mid', 3, True)
# int_seq = note_seq.midi_io.midi_file_to_note_sequence('temp/interpolated.mid')
# drum_accompany(int_seq, './temp/drum_output.mid')
# drum_interpolation('results\drum_mid\drum_3.mid', 'results\drum_mid\drum_15.mid', 'tracks\drum_mid\drum_1.mid', 3, True)
# drum_interpolation('results\drum_mid\drum_15.mid', 'results\drum_mid\drum_3.mid', 'tracks\drum_mid\drum_1.mid', 3, None)

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
    print("melody interpolate generated")
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
        melody_interpolation(start_midi_path, end_midi_path, interp_output_path, num_steps[i], is_first)
    print("Melody generation completed.")