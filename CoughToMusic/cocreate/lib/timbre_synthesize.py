from midi_ddsp.utils.midi_synthesis_utils import synthesize_mono_midi, conditioning_df_to_audio
from midi_ddsp.midi_ddsp_synthesize import load_pretrained_model
from midi_ddsp.data_handling.instrument_name_utils import INST_NAME_TO_ID_DICT
from midi_ddsp.utils.audio_io import save_wav
import tensorflow as tf
from scipy.signal import resample
from scipy.io.wavfile import write
import numpy as np
import pedalboard
from pedalboard import Pedalboard, Chorus, Reverb, Gain, Phaser, Compressor
from pathlib import Path

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
    # midi_path = str(Path(folder) / f"{track}_mid" / f"{track}_{track_id}.mid")
    # output_path = str(Path(folder) / f"{track}_wav" / f"{track}_{track_id}.wav")

    instrument, db, room_size, damping, wet_level = get_instrument_settings(track, inst)
    instrument_id = INST_NAME_TO_ID_DICT[instrument]

    synthesis_generator, expression_generator = load_pretrained_model()

    midi_audio, midi_control_params, midi_synth_params, conditioning_df = synthesize_mono_midi(
        synthesis_generator, expression_generator, midi_path, instrument_id, output_dir=None
    )

    synthesized_audio = midi_audio[0].numpy()
    board = Pedalboard([
        Gain(gain_db=db),
        Reverb(room_size=room_size, damping=damping, wet_level=wet_level),
    ])
    processed_audio = board(synthesized_audio, sample_rate=16000)
    save_wav(processed_audio, output_path)
    return processed_audio
    

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

def generate_trio(inst, midi_paths: dict, wav_paths: dict, merged_output_path, sample_rate=16000):
    mel_audio = synthesize('mel', inst, midi_paths['mel'], wav_paths['mel'], sample_rate=sample_rate)
    acc_audio = synthesize('acc', inst, midi_paths['acc'], wav_paths['acc'], sample_rate=sample_rate)
    bass_audio = synthesize('bass', inst, midi_paths['bass'], wav_paths['bass'], sample_rate=sample_rate)

    max_length = max(len(mel_audio), len(acc_audio), len(bass_audio))

    mel_audio = np.pad(mel_audio, (0, max_length - len(mel_audio)), 'constant')
    acc_audio = np.pad(acc_audio, (0, max_length - len(acc_audio)), 'constant')
    bass_audio = np.pad(bass_audio, (0, max_length - len(bass_audio)), 'constant')

    merged_audio = mel_audio + acc_audio + bass_audio

    save_wav(merged_audio, merged_output_path, sample_rate=sample_rate)        
        
