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
from .cocreate.lib.generation import generate_melody_from_sequence, generate_humanize_groove, interpolated_groove
from .cocreate.lib.timbre_synthesize import generate_trio  
from .cocreate.lib.drum import *
from .cocreate.lib import midi

# from cocreate.lib.audio import pedalboard_process


MEL_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.2,
    "note_interval_th": 20,
    "min_target": "C3",
    "max_target": "C6",
    "energy_th": -70,
}

ACC_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.25,
    "note_interval_th": 50,
    "min_target": "C2",
    "max_target": "C4",
    "energy_th": -60,
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
    audio.gain_db_from_wav(merged_output_path, 7)
    return merged_output_path


cough2midi(24)
gen_trio_mid(24)
gen_trio_trk(24, 'string')

def generate_groove_intp(folder_path, target_id):

    drum_mid = id_to_pth(target_id, 'drum', 'mid') 
    drum_trk = id_to_pth(target_id, 'drum', 'wav')

    df = classify_coughs(normalize_and_rank(process_all_coughs(folder_path)))
    cough7 = select_related_drums(df, target_id, 7)
    tmp_first = 'tmp/first.mid'
    tmp = 'tmp/tmp.mid'
    tmp_last = 'tmp/last.mid'
    tmp_last_2 = 'tmp/last_2.mid'
    def save_midi(neg_offset, path):
        subset = dict(list(cough7.items())[:neg_offset])
        write_midi_pretty(subset, df, folder_path, path)
        midi.adjust_to_2bars(path, path)
        return path

    tmp_first = save_midi(-6, tmp_first)  # 2 items (7 - 5)
    tmp = save_midi(-4, tmp)          # 4 items (7 - 3)
    tmp_last = save_midi(None, tmp_last)  # all 7
    midi.snap_on_grid_noteseq(tmp_first, tmp_first, 32)
    midi.snap_on_grid_noteseq(tmp, tmp, 16)
    midi.snap_on_grid_noteseq(tmp_last, tmp_last_2, 32)
    midi.snap_on_grid_noteseq(tmp_last, tmp_last, 16)
    midi.concatenate([tmp_first, tmp], tmp_first)
    midi.concatenate([tmp_last, tmp_last_2], tmp_last)

    interpolated_groove(tmp_first, tmp_last, drum_mid)
    midi.write_from_midi(drum_mid, drum_trk)
    print(f"Drum motif generation to {drum_mid} completed.")



generate_groove_intp(settings.PUBLIC_COUGH, 24)


def cough_to_drum_trk(id):
    
    drum_mtf = id_to_pth(id, 'drum', 'mtf')
    drum_mid = id_to_pth(id, 'drum', 'mid')
    drum_trk = id_to_pth(id, 'drum', 'wav')
    
    generate_drum_motif(settings.PUBLIC_COUGH, id, drum_mtf)
    generate_humanize_groove(drum_mtf, drum_mid)
    midi.write_from_midi(drum_mid, drum_trk)
   
    print("Cough to Drum Execution")

# cough_to_drum_trk(15)

# import soundfile as sf
# import pedalboard
# from pedalboard import Pedalboard, Reverb, Gain
# from pathlib import Path
# import numpy as np
# def pedalboard_process(path, DB, RS, DA, WET):
#     try:

#         reloaded_audio, sr = sf.read(path, dtype='float32')
#         print(f"RELOADED AUDIO: {reloaded_audio.shape}, SR: {sr}")

#         # Step 1: Reshape mono (1D) audio to (N, 1)
#         if len(reloaded_audio.shape) == 1:
#             reloaded_audio = reloaded_audio[:, np.newaxis]
#             print(f"Reshaped mono audio to: {reloaded_audio.shape}")

#         # Step 2: Duplicate mono to stereo if necessary
#         if reloaded_audio.shape[1] == 1:
#             reloaded_audio = np.repeat(reloaded_audio, 2, axis=1)
#             print(f"Duplicated mono channel to stereo: {reloaded_audio.shape}")

#         board = Pedalboard([
#             Gain(gain_db=DB),
#             Reverb(room_size=RS, damping=DA, wet_level=WET),
#         ])
#         print(f"PROCESSing WAV for at {path}")


#         processed_audio = board(reloaded_audio, sample_rate=int(sr))
#         print(f"Finished processing. Saving...")

#         sf.write(path, processed_audio, sr)
#         print(f"SAVED WAV for at {path}")

#     except Exception as e:
#         print(f"pedalboard_process failed: {e}")



# # pth = Path(r"C:\Users\JYWang\Desktop\CoughDjangoServer\media\public_music\mel_wav\mel_15.wav")
# # pedalboard_process(pth, 7, 0.5, 0.3, 0.3 )