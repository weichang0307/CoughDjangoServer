from midi_ddsp.utils.midi_synthesis_utils import synthesize_mono_midi, conditioning_df_to_audio
from midi_ddsp.midi_ddsp_synthesize import load_pretrained_model
from midi_ddsp.data_handling.instrument_name_utils import INST_NAME_TO_ID_DICT
from midi_ddsp.utils.audio_io import save_wav
import audio
import tensorflow as tf
import numpy as np

def get_instrument_settings(track, inst):
    settings = {
        'string': {
            'mel': ('violin', 7, 0.5, 0.3, 0.3),
            'acc': ('cello', 3, 0.4, 0.2, 0.2),
            'bass': ('double bass', 4, 0.2, 0.2, 0.2)
        },
        'wind': {
            'mel': ('flute', 7, 0.5, 0.3, 0.3),
            'acc': ('clarinet', 3, 0.4, 0.2, 0.2),
            'bass': ('french horn', 4, 0.2, 0.2, 0.2)
        }
    }
    return settings[inst][track]



def synthesize(track, inst, midi_path, output_path):

    with tf.device('/device:GPU:0'):

        instrument, Db, Room_size, Damping, Wet_level = get_instrument_settings(track, inst)
        instrument_id = INST_NAME_TO_ID_DICT[instrument]

        synthesis_generator, expression_generator = load_pretrained_model()

        midi_audio, midi_control_params, midi_synth_params, conditioning_df = synthesize_mono_midi(
            synthesis_generator, expression_generator, midi_path, instrument_id, output_dir=None
        )

        synthesized_audio = midi_audio[0].numpy()
    # board = Pedalboard([
    #     Gain(gain_db=Db),
    #     Reverb(room_size=Room_size, damping=Damping, wet_level=Wet_level),
    # ])
    # processed_audio = board(synthesized_audio, sample_rate)
        save_wav(synthesized_audio, output_path)
        return synthesized_audio


def generate_trio(inst, midi_paths: dict, wav_paths: dict, merged_output_path, sample_rate):
    
    print("mel_trk generating")
    mel_audio = synthesize( 'mel', inst, midi_paths['mel'], wav_paths['mel'])
    audio.gain_db_from_wav(wav_paths['mel'], 15)
    print("mel_trk generated")
    print("acc_trk generating")
    acc_audio = synthesize('acc', inst, midi_paths['acc'], wav_paths['acc'])
    audio.gain_db_from_wav(wav_paths['acc'], 3)
    print("acc_trk generated")

    print("bass_trk generating")
    bass_audio = synthesize('bass', inst, midi_paths['bass'], wav_paths['bass'])
    audio.gain_db_from_wav(wav_paths['bass'], 7)
    print("bass_trk generated")
    max_length = max(len(mel_audio), len(acc_audio), len(bass_audio))
    mel_audio = np.pad(mel_audio, (0, max_length - len(mel_audio)), 'constant')
    acc_audio = np.pad(acc_audio, (0, max_length - len(acc_audio)), 'constant')
    bass_audio = np.pad(bass_audio, (0, max_length - len(bass_audio)), 'constant')
    merged_audio = mel_audio + acc_audio + bass_audio
    print(f'output path: {merged_output_path}')
    save_wav(merged_audio, merged_output_path, sample_rate)        


# def generate_trio(inst, track_id, folder='tracks'):
#     mel = synthesize('mel', track_id, inst)
#     acc = synthesize('acc', track_id, inst)
#     bass = synthesize('bass', track_id, inst)
#     output_path = str(Path(folder) / f"trio_wav" / f"trio_{track_id}.wav")
#     # Ensure all tracks have the same length
#     max_length = max(len(mel), len(acc), len(bass))
#     mel = np.pad(mel, (0, max_length - len(mel)), 'constant')
#     acc = np.pad(acc, (0, max_length - len(acc)), 'constant')
#     bass = np.pad(bass, (0, max_length - len(bass)), 'constant')
#     # Merge the tracks
#     merged_audio = mel + acc + bass
#     # Save the merged audio to a WAV file
#     save_wav(merged_audio, output_path, sample_rate=16000)

# def generate_trio(inst, midi_paths: dict, wav_paths: dict):
#     print(f"mel  path: {wav_paths['mel']}")
#     mel_audio = synthesize(inst, midi_paths['mel'], wav_paths['mel'])
#     print(f"mel_audio len: {len(mel_audio)}, min: {mel_audio.min()}, max: {mel_audio.max()}")

#     # pedalboard_process(wav_paths['mel'], 7, 0.5, 0.3, 0.3)
#     print("mel_trk generated")

#     print("acc_trk generating")
#     acc_audio = synthesize(inst, midi_paths['acc'], wav_paths['acc'])
#     print(f"acc_audio len: {len(acc_audio)}, min: {acc_audio.min()}, max: {acc_audio.max()}")
#     # pedalboard_process(wav_paths['acc'], 3, 0.4, 0.2, 0.2)
#     print("acc_trk generated")

#     print("bass_trk generating")
#     bass_audio = synthesize(inst, midi_paths['bass'], wav_paths['bass'])
#     print(f"bass_audio len: {len(bass_audio)}, min: {bass_audio.min()}, max: {bass_audio.max()}")
#     # pedalboard_process(wav_paths['bass'], 4, 0.2, 0.2, 0.2)
#     print("bass_trk generated")



