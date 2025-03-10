from django.conf import settings
from .cocreate.lib import cough2mid
from .cocreate.lib.calculate_similarity.generate_order import generate_midi_sequence
from .cocreate.lib.generation import generate_melody_from_sequence
from .cocreate.lib.timbre_synthesize import generate_trio  
from .cocreate.lib.drum import generate_drum_motif
from .cocreate.lib.midi import write_from_midi

MEL_CONFIG = {0.3, 0.2, 20, "C3", "C6", -50 ,"mel"}
ACC_CONFIG = {0.25, 0.25, 50, 'C2', 'C4', -50, 'acc'}
BASS_CONFIG = {0.3, 0.95, 50, 'C1', 'C3', -50, 'bass'}

def id_to_pth(id, track, music_motif):
    if music_motif == 'mtf':
        if track == 'mel':
            return settings.MOTIF_MEL_MID.joinpath(f'mel_{id}.mid')
        elif track == 'acc':
            return settings.MOTIF_ACC_MID.joinpath(f'acc_{id}.mid')
        elif track == 'bass':
            return settings.MOTIF_BASS_MID.joinpath(f'bass_{id}.mid')
        elif track == 'drum':
            return settings.MOTIF_DRUM_MID.joinpath(f'drum_{id}.mid')
    elif music_motif == 'mid':
        if track == 'mel':
            return settings.TRACK_MEL_MID.joinpath(f'mel_{id}.mid')
        elif track == 'acc':
            return settings.TRACK_ACC_MID.joinpath(f'acc_{id}.mid')     
        elif track == 'bass':
            return settings.TRACK_BASS_MID.joinpath(f'bass_{id}.mid')
        elif track == 'drum':
            return settings.TRACK_DRUM_MID.joinpath(f'drum_{id}.mid')
    elif music_motif == 'wav':
        if track == 'mel':
            return settings.TRACK_MEL_WAV.joinpath(f'mel_{id}.wav')
        elif track == 'acc':
            return settings.TRACK_ACC_WAV.joinpath(f'acc_{id}.wav')
        elif track == 'bass':
            return settings.TRACK_BASS_WAV.joinpath(f'bass_{id}.wav')
        elif track == 'drum':
            return settings.TRACK_DRUM_WAV.joinpath(f'drum_{id}.wav')
    else:
        return settings.TRACK_TRIO_WAV.joinpath(f'trio_{id}.wav')


def cough2midi(id):
    COUGH_PATH = settings.PUBLIC_COUGH.joinpath(f'{id}.wav')
    mel_mtf = id_to_pth(id, 'mel', 'mtf')
    acc_mtf = id_to_pth(id, 'acc', 'mtf')
    bass_mtf = id_to_pth(id, 'bass', 'mtf')
    cough2mid.cough2midi(COUGH_PATH, mel_mtf, MEL_CONFIG)
    cough2mid.correct_key(mel_mtf,mel_mtf)
    cough2mid.cough2midi(COUGH_PATH, acc_mtf, ACC_CONFIG)
    cough2mid.correct_key(acc_mtf,acc_mtf)
    cough2mid.cough2midi(COUGH_PATH, bass_mtf, BASS_CONFIG)
    cough2mid.correct_key(bass_mtf,bass_mtf)
    print("Cough to mid Execution")

def generate_trio_mid(id):
    tracks = ['mel', 'acc', 'bass']
    mel_mtf = id_to_pth(id, 'mel', 'mtf')

    sequence = generate_midi_sequence(mel_mtf, settings.MOTIF_MEL_MID)
    print(f"MIDI sequence: {sequence}")
    for trk in tracks:
        sequence_pth =[id_to_pth(id, trk, 'mtf') for id in sequence]
        intrp_mid_pth = id_to_pth(id, trk, 'mid')
        generate_melody_from_sequence(sequence_pth, intrp_mid_pth)
    print("Generate Trio Execution")

def generate_trio_trk(id, inst, sample_rate=16000):
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
    generate_trio(inst, midi_paths, wav_paths, merged_output_path, sample_rate=sample_rate)