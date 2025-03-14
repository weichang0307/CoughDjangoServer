import sys
from pathlib import Path
import os
import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoughToMusicDjango.settings')
django.setup()
from django.conf import settings
from .cocreate.lib import cough2mid
from .cocreate.lib.calculate_similarity.generate_order import generate_midi_sequence
from .cocreate.lib.generation import generate_melody_from_sequence
from .cocreate.lib.timbre_synthesize import generate_trio  
from .cocreate.lib.drum import generate_drum_motif
# from cocreate.lib.audio import pedalboard_process


MEL_CONFIG = {
    "threshold": 0.3,
    "freq_range_th": 0.2,
    "note_interval_th": 20,
    "min_target": "C3",
    "max_target": "C6",
    "energy_th": -50,
}

ACC_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.25,
    "note_interval_th": 50,
    "min_target": "C2",
    "max_target": "C4",
    "energy_th": -50,
}

BASS_CONFIG = {
    "threshold": 0.3,
    "freq_range_th": 0.95,
    "note_interval_th": 50,
    "min_target": "C1",
    "max_target": "C3",
    "energy_th": -50,
}

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
    
def id_to_pth(id, track, music_motif):
    if music_motif == 'mtf':
        if track == 'mel':
            return os.path.join(settings.MOTIF_MEL_MID, f'mel_{id}.mid')
        elif track == 'acc':
            return os.path.join(settings.MOTIF_ACC_MID, f'acc_{id}.mid')
        elif track == 'bass':
            return os.path.join(settings.MOTIF_BASS_MID, f'bass_{id}.mid')
        elif track == 'drum':
            return os.path.join(settings.MOTIF_DRUM_MID, f'drum_{id}.mid')

    elif music_motif == 'mid':
        if track == 'mel':
            return os.path.join(settings.TRACK_MEL_MID, f'mel_{id}.mid')
        elif track == 'acc':
            return os.path.join(settings.TRACK_ACC_MID, f'acc_{id}.mid')
        elif track == 'bass':
            return os.path.join(settings.TRACK_BASS_MID, f'bass_{id}.mid')
        elif track == 'drum':
            return os.path.join(settings.TRACK_DRUM_MID, f'drum_{id}.mid')

    elif music_motif == 'wav':
        if track == 'mel':
            return os.path.join(settings.TRACK_MEL_WAV, f'mel_{id}.wav')
        elif track == 'acc':
            return os.path.join(settings.TRACK_ACC_WAV, f'acc_{id}.wav')
        elif track == 'bass':
            return os.path.join(settings.TRACK_BASS_WAV, f'bass_{id}.wav')
        elif track == 'drum':
            return os.path.join(settings.TRACK_DRUM_WAV, f'drum_{id}.wav')
        elif track == 'trio':
            return os.path.join(settings.TRACK_TRIO_WAV, f'trio_{id}.wav')

    # fallback: raise an exception if no match
    raise ValueError(f"No path matched for track='{track}', music_motif='{music_motif}'")


def cough2midi(id):
    COUGH_PATH = os.path.join(settings.PUBLIC_COUGH, f'{id}.wav')
    mel_mtf = id_to_pth(id, 'mel', 'mtf')
    acc_mtf = id_to_pth(id, 'acc', 'mtf')
    bass_mtf = id_to_pth(id, 'bass', 'mtf')
    cough2mid.cough2midi(COUGH_PATH, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf,mel_mtf)
    cough2mid.cough2midi(COUGH_PATH, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf,acc_mtf)
    cough2mid.cough2midi(COUGH_PATH, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf,bass_mtf)
    print("Cough to mid Execution")

def gen_trio_mid(id):
    tracks = ['mel', 'acc', 'bass']
    mel_mtf = id_to_pth(id, 'mel', 'mtf')
    sequence = generate_midi_sequence(mel_mtf, settings.MOTIF_MEL_MID)
    print(f"MIDI sequence: {sequence}")
    for trk in tracks:
        sequence_pth =[id_to_pth(id, trk, 'mtf') for id in sequence]
        intrp_mid_pth = id_to_pth(id, trk, 'mid')
        generate_melody_from_sequence(sequence_pth, intrp_mid_pth)
        if trk != 'mel':
            ref_pth = id_to_pth(id, 'mel', 'mid')
            print(f"Correcting key for {ref_pth, intrp_mid_pth}")
            cough2mid.correct_key(ref_pth,intrp_mid_pth)
    print("Generate Trio Execution")

def gen_trio_trk(id, inst, sample_rate=16000):
    midi_paths = {
        'mel': id_to_pth(id, 'mel', 'mid'),
        'acc': id_to_pth(id, 'acc', 'mid'),
        'bass': id_to_pth(id, 'bass', 'mid')
    }
    wav_paths = {
        'mel':  id_to_pth(id, 'mel', 'wav'),
        'acc': id_to_pth(id, 'acc', 'wav'),
        'bass': id_to_pth(id, 'bass', 'wav')
    }
    merged_output_path = id_to_pth(id, 'trio', 'wav')
    generate_trio(inst, midi_paths, wav_paths, merged_output_path, sample_rate)
    return merged_output_path

# cough2midi(15)
# gen_trio_mid(15)
# gen_trio_trk(15, 'string')



import soundfile as sf
import pedalboard
from pedalboard import Pedalboard, Reverb, Gain
from pathlib import Path
import numpy as np
def pedalboard_process(path, DB, RS, DA, WET):
    try:

        reloaded_audio, sr = sf.read(path, dtype='float32')
        print(f"RELOADED AUDIO: {reloaded_audio.shape}, SR: {sr}")

        # Step 1: Reshape mono (1D) audio to (N, 1)
        if len(reloaded_audio.shape) == 1:
            reloaded_audio = reloaded_audio[:, np.newaxis]
            print(f"Reshaped mono audio to: {reloaded_audio.shape}")

        # Step 2: Duplicate mono to stereo if necessary
        if reloaded_audio.shape[1] == 1:
            reloaded_audio = np.repeat(reloaded_audio, 2, axis=1)
            print(f"Duplicated mono channel to stereo: {reloaded_audio.shape}")

        board = Pedalboard([
            Gain(gain_db=DB),
            Reverb(room_size=RS, damping=DA, wet_level=WET),
        ])
        print(f"PROCESSing WAV for at {path}")


        processed_audio = board(reloaded_audio, sample_rate=int(sr))
        print(f"Finished processing. Saving...")

        sf.write(path, processed_audio, sr)
        print(f"SAVED WAV for at {path}")

    except Exception as e:
        print(f"pedalboard_process failed: {e}")



# pth = Path(r"C:\Users\JYWang\Desktop\CoughDjangoServer\media\public_music\mel_wav\mel_15.wav")
# pedalboard_process(pth, 7, 0.5, 0.3, 0.3 )