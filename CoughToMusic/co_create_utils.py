import sys
from pathlib import Path
import os
import shutil
import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Only setup Django if NOT running in worker mode
if not os.environ.get("COUGH_WORKER"):
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoughToMusicDjango.settings")
    django.setup()
    from django.conf import settings
else:
    settings = None  # placeholder, so imports below don't break

# Now import your project libs
from .cocreate.lib import cough2mid
from .cocreate.lib.calculate_similarity.generate_order import generate_midi_sequence
from .cocreate.lib.generation import (
    generate_melody_from_sequence,
    generate_humanize_groove,
    interpolated_groove,
    path_to_note_seq,
    concatenate_sequences,
    concate_interpolation,
)
from .cocreate.lib.drum import *
from .cocreate.lib import midi
import soundfile as sf


# from cocreate.lib.audio import pedalboard_process
MEL_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.15,
    "note_interval_th": 20,
    "min_target": "C3",
    "max_target": "C6",
    "energy_th": -1000 #-70,
}

ACC_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.45,
    "note_interval_th": 40,
    "min_target": "C2",
    "max_target": "C4",
    "energy_th":-1000 # -60,
}

BASS_CONFIG = {
    "threshold": 0.4,
    "freq_range_th": 0.95,
    "note_interval_th": 40,
    "min_target": "C1",
    "max_target": "C3",
    "energy_th": -1000 #-50,
}
instruments = {'mel': 40, 'acc': 41, 'bass': 43}

# def sound_synthesis(Db, Room_size, Damping, Wet_level, synthesized_audio, sample_rate):
#     board = Pedalboard([
#         Gain(gain_db=Db),
#         Reverb(room_size=Room_size, damping=Damping, wet_level=Wet_level),
#     ])
#     processed_audio = board(synthesized_audio, sample_rate)
#     return processed_audio

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
        
    elif music_motif == 'mtf_wav':
        if track == 'mel':
            return os.path.join(settings.MOTIF_MEL_WAV, f'mel_{id}.wav')
        elif track == 'acc':
            return os.path.join(settings.MOTIF_ACC_WAV, f'acc_{id}.wav')
        elif track == 'bass':
            return os.path.join(settings.MOTIF_BASS_WAV, f'bass_{id}.wav')
        elif track == 'drum':
            return os.path.join(settings.MOTIF_DRUM_WAV, f'drum_{id}.wav')
        elif track == 'trio':
            return os.path.join(settings.MOTIF_TRIO_WAV, f'trio_{id}.wav')

    # fallback: raise an exception if no match
    raise ValueError(f"No path matched for track='{track}', music_motif='{music_motif}'")


def cough2midi(id, inst, user_folder, uuid, sample_rate=16000):
    COUGH_PATH = os.path.join(settings.PUBLIC_COUGH, f'{id}.wav')
    wav_paths, audio = {}, {}
    mel_mtf = id_to_pth(id, 'mel', 'mtf')
    acc_mtf = id_to_pth(id, 'acc', 'mtf')
    bass_mtf = id_to_pth(id, 'bass', 'mtf')
    cough2mid.cough2midi(COUGH_PATH, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf,mel_mtf)
    cough2mid.cough2midi(COUGH_PATH, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf,acc_mtf)
    cough2mid.cough2midi(COUGH_PATH, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf,bass_mtf)
    midi_paths = {
        'mel': mel_mtf,
        'acc': acc_mtf,
        'bass': bass_mtf
    }
    wav_paths_mp = {
        'mel': id_to_pth(id, 'mel', 'mtf_wav'),
        'acc': id_to_pth(id, 'acc', 'mtf_wav'),
        'bass': id_to_pth(id, 'bass', 'mtf_wav')
    }
    # merged_output_path = os.path.join(user_folder,  f'{uuid}_short_trio.wav')
    merged_output_path = os.path.join(settings.MOTIF_TRIO_WAV, f'trio_{id}.wav')
    for trk, program in instruments.items():
        midi_path = midi_paths[trk]
        wav_path = wav_paths_mp[trk]
        tmp_mid_pth =  os.path.join(user_folder, f'{uuid}_{trk}_short_trio.mid')
        midi.update_midi_program(midi_path, tmp_mid_pth, program_number=program)
        midi.write_from_midi(tmp_mid_pth, wav_path, 'violin')
        wav_paths[trk] = wav_path
        wav, sr = librosa.load(wav_path, sr=sample_rate)
        # setting= get_instrument_settings(trk, inst)
        # processed_audio = sound_synthesis(  *setting, wav, sr)
        # audio[trk] = processed_audio
        audio[trk] = wav
    max_length = max(len(a) for a in audio.values())
    merged_audio = sum(np.pad(a, (0, max_length - len(a)), 'constant') for a in audio.values())
    sf.write(merged_output_path, merged_audio, sample_rate)
    print(f'Saved output path: {merged_output_path}')
    return merged_output_path
    # generate_trio(inst, midi_paths, wav_paths, merged_output_path, sample_rate)
    # print("Cough to mid Execution")
    # return merged_output_path

def cough2mid_manual(cough_pth, usr_folder, mid_dic, sample_rate=16000):
    cough_name = os.path.splitext(os.path.basename(cough_pth))[0]
    mel_mtf = os.path.join(usr_folder, f'{cough_name}_mel_mtf.mid')
    acc_mtf = os.path.join(usr_folder, f'{cough_name}_acc_mtf.mid')
    bass_mtf = os.path.join(usr_folder, f'{cough_name}_bass_mtf.mid')
    cough2mid.cough2midi(cough_pth, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf, mel_mtf)
    mid_dic['mel'].append(mel_mtf)
    cough2mid.cough2midi(cough_pth, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf, acc_mtf)
    mid_dic['acc'].append(acc_mtf)
    cough2mid.cough2midi(cough_pth, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf, bass_mtf)
    mid_dic['bass'].append(bass_mtf)
    print('start generating motif wavs ')

    # === 更新 MIDI program number ===
    midi.update_midi_program(mel_mtf, os.path.join(usr_folder, f'{cough_name}_mel_motif.mid'), program_number=instruments['mel'])
    midi.update_midi_program(acc_mtf, os.path.join(usr_folder, f'{cough_name}_acc_motif.mid'), program_number=instruments['acc'])
    midi.update_midi_program(bass_mtf, os.path.join(usr_folder, f'{cough_name}_bass_motif.mid'), program_number=instruments['bass'])

    # 產生三軌 wav
    mel_wav = os.path.join(usr_folder, f'{cough_name}_mel_mtf.wav')
    acc_wav = os.path.join(usr_folder, f'{cough_name}_acc_mtf.wav')
    bass_wav = os.path.join(usr_folder, f'{cough_name}_bass_mtf.wav')

    midi.write_from_midi(os.path.join(usr_folder, f'{cough_name}_mel_motif.mid'), mel_wav, 'violin')
    midi.write_from_midi(os.path.join(usr_folder, f'{cough_name}_acc_motif.mid'), acc_wav, 'violin')
    midi.write_from_midi(os.path.join(usr_folder, f'{cough_name}_bass_motif.mid'), bass_wav, 'violin')
    print('start merging motif wavs ')
    # 合併三軌
    mel, _ = librosa.load(mel_wav, sr=sample_rate)
    acc, _ = librosa.load(acc_wav, sr=sample_rate)
    bass, _ = librosa.load(bass_wav, sr=sample_rate)
    max_length = max(len(mel), len(acc), len(bass))
    mel = np.pad(mel, (0, max_length - len(mel)), 'constant')
    acc = np.pad(acc, (0, max_length - len(acc)), 'constant')
    bass = np.pad(bass, (0, max_length - len(bass)), 'constant')
    merged = mel + acc + bass
    trio_wav = os.path.join(usr_folder, f'{cough_name}_trio_mtf.wav')
    sf.write(trio_wav, merged, sample_rate)
    return trio_wav



def gen_trio_mid(id):
    tracks = ['mel', 'acc', 'bass']
    mel_mtf = id_to_pth(id, 'mel', 'mtf')
    # sequence = generate_midi_sequence(mel_mtf, settings.MOTIF_MEL_MID)
    # --- Start Randomly select two other IDs from the motif folder ---
    motif_folder = settings.MOTIF_MEL_MID
    midi_files = [f for f in os.listdir(motif_folder) if f.endswith('.mid')]
    target_filename = os.path.basename(mel_mtf)
    midi_files = [f for f in midi_files if f != target_filename]
    selected = random.sample(midi_files, 2)
    def extract_id(filename):
        return int(filename.replace("mel_", "").replace(".mid", ""))
    sequence = [id] + [extract_id(f) for f in selected]
   # --- End Randomly select two other IDs from the motif folder --- 
    print(f"MIDI sequence: {sequence}")
    for trk in tracks:
        sequence_pth =[id_to_pth(id, trk, 'mtf') for id in sequence]
        intrp_mid_pth = id_to_pth(id, trk, 'mid')
        generate_melody_from_sequence(sequence_pth, intrp_mid_pth)
    used_cough_paths = [
        os.path.join(settings.PUBLIC_COUGH, f"{i}.wav")
        for i in sequence if str(i) != str(id)
    ]
    used_motif_paths = [
        os.path.join(settings.MOTIF_TRIO_WAV, f"trio_{i}.wav")
        for i in sequence if str(i) != str(id)
    ]
    return used_cough_paths, used_motif_paths
        # if trk != 'mel':
            # ref_pth = id_to_pth(id, 'mel', 'mid')
            # print(f"Correcting key for {ref_pth, intrp_mid_pth}")
            # cough2mid.correct_key(ref_pth,intrp_mid_pth)
    print("Generate Trio Execution")

def gen_trio_manual(user_folder, mid_dic, uuid):
    print(f"MIDI sequence: {mid_dic}")
    tracks = ['mel', 'acc', 'bass']
    for trk in tracks:
        mid_list = mid_dic[trk]
        intrp_mid_pth = os.path.join(user_folder, f'{uuid}_{trk}_trio.mid')
        generate_melody_from_sequence(mid_list, intrp_mid_pth)

def gen_trio_trk_manual(user_folder, uuid, sample_rate=16000):
    print(f"Generating trio track with UUID: {uuid}")
    merged_output_path = os.path.join(user_folder, f'{uuid}_trio.wav')
    wav_paths, audio = {}, {}

    for trk, program in instruments.items():
        midi_path = os.path.join(user_folder, f'{uuid}_{trk}_trio.mid')
        wav_path = os.path.join(user_folder, f'{uuid}_{trk}_trio.wav')
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, 'violin')
        wav_paths[trk] = wav_path
        audio[trk], _ = librosa.load(wav_path, sr=sample_rate)

    max_length = max(len(a) for a in audio.values())
    merged_audio = sum(np.pad(a, (0, max_length - len(a)), 'constant') for a in audio.values())

    print(f"Saving merged audio to {merged_output_path}")
    sf.write(merged_output_path, merged_audio, sample_rate)
    print(f'Saved output path: {merged_output_path}')
    return merged_output_path

       
def gen_trio_trk(id, inst, user_folder,uuid, sample_rate=16000):
    merged_output_path = os.path.join(user_folder,  f'{uuid}_trio.wav')
    wav_paths, audio = {}, {}
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
    for trk, program in instruments.items():
        midi_path = midi_paths[trk]
        wav_path = wav_paths[trk]
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, 'violin')
        wav_paths[trk] = wav_path
        audio[trk], _ = librosa.load(wav_path, sr=sample_rate)

    max_length = max(len(a) for a in audio.values())
    merged_audio = sum(np.pad(a, (0, max_length - len(a)), 'constant') for a in audio.values())

    print(f"Saving merged audio to {merged_output_path}")
    sf.write(merged_output_path, merged_audio, sample_rate)
    print(f'Saved output path: {merged_output_path}')
    return merged_output_path
    # merged_output_path = id_to_pth(id, 'trio', 'wav')
    # merged_output_path = os.path.join(user_folder, f'cocreate_{id}_trio.wav')
    # generate_trio(inst, midi_paths, wav_paths, merged_output_path, sample_rate)
    # return merged_output_path

# def generate_groove_intp(folder_path, target_id, user_folder, uuid):
#     drum_mid = id_to_pth(target_id, 'drum', 'mid') 
#     # drum_trk = os.path.join(user_folder, f'cocreate_{uuid}_drum.wav')
#     drum_trk = os.path.join(user_folder, f'{uuid}_drum.wav')
#     drum_motif_trk =os.path.join(user_folder, f'{uuid}_drum.wav')
#     print(f"Generating drum motif for ID: {target_id} at {drum_mid}")

#     df = classify_coughs(normalize_and_rank(process_all_coughs(folder_path)))
#     print(f"Dataframe shape: {df.shape}")

#     cough7 = select_related_drums(df, target_id, 7)
#     tmp_first = 'tmp/first.mid'
#     tmp_sec = 'tmp/sec.mid'
#     tmp_third = 'tmp/third.mid'
#     tmp_last = 'tmp/last.mid'
#     tmp_last2 = 'tmp/last2.mid'
#     def save_midi(neg_offset, path):
#         subset = dict(list(cough7.items())[:neg_offset])
#         write_midi_pretty(subset, df, folder_path, path)
#         midi.adjust_to_2bars(path, path)
#         return path

#     tmp_first = save_midi(-6, tmp_first)
#     tmp_sec = save_midi(-5, tmp_sec)  
#     tmp_third = save_midi(-4, tmp_third)       
#     tmp_last = save_midi(None, tmp_last)  
#     midi.write_from_midi(tmp_first, drum_motif_trk)

#     midi.snap_on_grid_noteseq(tmp_first, tmp_first, 32)
#     midi.snap_on_grid_noteseq(tmp_sec, tmp_sec, 32)
#     midi.snap_on_grid_noteseq(tmp_third, tmp_third, 16)
#     midi.snap_on_grid_noteseq(tmp_last, tmp_last, 16)
#     midi.concatenate([tmp_sec, tmp_third], tmp_third, sec = 4.0)
#     midi.concatenate([tmp_last, tmp_last], tmp_last2, sec = 4.0)

#     interpolated_seq = interpolated_groove(tmp_third, tmp_last2, drum_mid)
    
#     start_note_seq, end_note_seq = path_to_note_seq(tmp_third, tmp_last)
#     concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, drum_mid,  target_duration=8.0)
#     concatenate_sequences(tmp_first, drum_mid, drum_mid)
#     midi.write_from_midi(drum_mid, drum_trk)
#     print(f"Drum motif generation to {drum_mid} completed.")
#     return drum_trk, [os.path.join(folder_path, f"{id}.wav") for id in list(cough7.keys()) if id != target_id]


def generate_groove_intp_manual(cough_path_list, user_folder, uuid):
    print(f'cough_path_list: {cough_path_list}')
    assert len(cough_path_list) == 7, "Expecting exactly 7 cough files"
    drum_trk = os.path.join(user_folder, f'{uuid}_drum.wav')
    selected_coughs, df = process_manual_coughs(cough_path_list)
    print(f"Selected coughs: {selected_coughs}")

    tmp_first = 'tmp/first.mid'
    tmp_sec = 'tmp/sec.mid'
    tmp_third = 'tmp/third.mid'
    tmp_last = 'tmp/last.mid'
    tmp_last2 = 'tmp/last2.mid'

    cough_seq = list(selected_coughs.items())
    motif_list = []
    def save_midi(seq_slice, out_path):
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, cough_path_list, out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path
    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i+1), f'tmp/drum_motif{i}.mid')
        wav_path = str(Path(mid_path).with_suffix('.wav'))
        midi.write_from_midi(mid_path, wav_path)
        print(f"Generated motif {i} at {wav_path}")
        motif_list.append(wav_path)

    tmp_first = save_midi(slice(0, 1), tmp_first)
    tmp_sec = save_midi(slice(0, 2), tmp_sec)
    tmp_third = save_midi(slice(0, 3), tmp_third)
    tmp_last = save_midi(slice(0, 7), tmp_last)

    midi.snap_on_grid_noteseq(tmp_first, tmp_first, 32)
    midi.snap_on_grid_noteseq(tmp_sec, tmp_sec, 32)
    midi.snap_on_grid_noteseq(tmp_third, tmp_third, 16)
    midi.snap_on_grid_noteseq(tmp_last, tmp_last, 16)
    midi.concatenate([tmp_sec, tmp_third], tmp_third, sec=4.0)
    midi.concatenate([tmp_last, tmp_last], tmp_last2, sec=4.0)

    interpolated_seq = interpolated_groove(tmp_third, tmp_last2, tmp_last)
    start_note_seq, end_note_seq = path_to_note_seq(tmp_third, tmp_last)
    concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, tmp_last, target_duration=8.0)
    concatenate_sequences(tmp_first, tmp_last, tmp_last)
    midi.write_from_midi(tmp_last, drum_trk)

    print(f"Manual drum groove generated at {drum_trk}")
    return drum_trk, motif_list


def generate_groove_intp_autofill(user_paths, public_folder, user_folder, uuid):

    selected_coughs, df, id_to_path, used_public_paths = process_autofill_coughs(user_paths, public_folder)

    tmp_first = 'tmp/first.mid'
    tmp_sec = 'tmp/sec.mid'
    tmp_third = 'tmp/third.mid'
    tmp_last = 'tmp/last.mid'
    tmp_last2 = 'tmp/last2.mid'
    drum_trk = os.path.join(user_folder, f'{uuid}_drum.wav')
    drum_motif_trk = os.path.join(user_folder, f'{uuid}_short_drum.wav')

    cough_seq = list(selected_coughs.items())
    motif_list = []
    def save_midi(seq_slice, out_path):
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, list(id_to_path.values()), out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path
    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i+1), f'tmp/drum_motif{i}.mid')
        wav_path = str(Path(mid_path).with_suffix('.wav'))
        midi.write_from_midi(mid_path, wav_path)
        print(f"Generated motif {i} at {wav_path}")
        motif_list.append(wav_path)

    tmp_first = save_midi(slice(0, 1), tmp_first)
    tmp_sec = save_midi(slice(0, 2), tmp_sec)
    tmp_third = save_midi(slice(0, 3), tmp_third)
    tmp_last = save_midi(slice(0, 7), tmp_last)

    midi.snap_on_grid_noteseq(tmp_first, tmp_first, 32)
    midi.snap_on_grid_noteseq(tmp_sec, tmp_sec, 32)
    midi.snap_on_grid_noteseq(tmp_third, tmp_third, 16)
    midi.snap_on_grid_noteseq(tmp_last, tmp_last, 16)

    midi.concatenate([tmp_sec, tmp_third], tmp_third, sec=4.0)
    midi.concatenate([tmp_last, tmp_last], tmp_last2, sec=4.0)

    interpolated_seq = interpolated_groove(tmp_third, tmp_last2, tmp_last)
    start_note_seq, end_note_seq = path_to_note_seq(tmp_third, tmp_last)
    concate_interpolation(start_note_seq, end_note_seq, interpolated_seq, tmp_last, target_duration=8.0)
    concatenate_sequences(tmp_first, tmp_last, tmp_last)
    midi.write_from_midi(tmp_last, drum_trk)
    used_paths = [id_to_path[cid] for cid in selected_coughs.values() if cid in df["name"].values]

    return drum_trk, used_paths, motif_list


# def batch_update_midi_programs(directory, program_number, channel=0):
#     for filename in os.listdir(directory):
#         if filename.endswith('.mid'):
#             midi_path = os.path.join(directory, filename)
#             midi.update_midi_program(midi_path, midi_path, program_number=program_number, channel=channel)
#             print(f"Updated {midi_path} -> {midi_path}")
# batch_update_midi_programs('./media/public_motif/bass_mid/', program_number=0)
# 用法範例
# batch_update_midi_programs('your/midi/folder', program_number=40)

# generate_groove_intp(settings.PUBLIC_COUGH, ID)

# def cough_to_drum_trk(id):
#     drum_mid = id_to_pth(id, 'drum', 'mid')
#     drum_trk = id_to_pth(id, 'drum', 'wav')
    
#     generate_drum_motif(settings.PUBLIC_COUGH, id, drum_mtf)
#     generate_humanize_groove(drum_mtf, drum_mid)
#     midi.write_from_midi(drum_mid, drum_trk)
   
#     print("Cough to Drum Execution")

def update_music_table(user_id, data):
    music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music_cocreate')
    os.makedirs(music_folder, exist_ok=True)
    music_table_path = os.path.join(music_folder, 'cocreate_table.csv')

    if not os.path.exists(music_table_path):
        print(f"User table {music_table_path} does not exist.")
        return

    df = pd.read_csv(music_table_path)
    new_row = pd.Series(data)
    df = pd.concat([df, new_row.to_frame().T], ignore_index=True)
    df.to_csv(music_table_path, index=False)

def save_final_cocreate(user_id, uuid, filename_display):
    """
    修正後的 save_music_move 確保最內層的檔案名稱是 filename 而不是 uuid。
    """
    print(f"save_music_move: {user_id}, {uuid}, {filename_display}")

    if not uuid or not filename_display:
        print("Error: filename or filename_display is empty.")
        return
    
    if not settings.MEDIA_ROOT:
        raise ValueError("settings.MEDIA_ROOT is not set")
    if not user_id:
        raise ValueError("user_id is not provided")
    
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)

    ### 處理 generated_music 資料夾 ###
    music_folder = os.path.join(user_folder, 'generated_music_cocreate')
    os.makedirs(music_folder, exist_ok=True)
    tmp_dir = os.path.join(user_folder, 'temp_cocreate')
    new_music_folder = os.path.join(music_folder, filename_display)
    os.makedirs(new_music_folder, exist_ok=True)

    if os.path.exists(tmp_dir):
        for file in os.listdir(tmp_dir):
            if file.endswith("_drum_auto.wav"):
                drum_file_path = os.path.join(tmp_dir, file)
                print(f"Drum file path: {drum_file_path}")
                new_drum_file_path = os.path.join(new_music_folder, f"{filename_display}_drum_auto.wav")
                shutil.move(drum_file_path, new_drum_file_path)
            elif file.endswith("_short_drum.wav"):
                drum_file_path = os.path.join(tmp_dir, file)
                print(f"Drum motif file path: {drum_file_path}")
                new_drum_file_path = os.path.join(new_music_folder, f"{filename_display}_short_drum.wav")
            elif file.endswith("_trio.wav"):
                trio_file_path = os.path.join(tmp_dir, file)
                print(f"Trio file path: {trio_file_path}")
                new_trio_file_path = os.path.join(new_music_folder, f"{filename_display}_trio.wav")
                shutil.move(trio_file_path, new_trio_file_path)
            
        shutil.rmtree(tmp_dir)  
    else:
        print(f"Error: {tmp_dir} does not exist.")

    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    music_table_data = {"filename": filename_display, "timestamp": datetime.datetime.now().timestamp(), 'time' : current_datetime}
    update_music_table(user_id, music_table_data)
    print(f"✅ Successfully moved music & midi files for {filename_display}")


# def cough2midi_test(id, inst, sample_rate=16000):
#     COUGH_PATH = os.path.join(settings.PUBLIC_COUGH, f'{id}.wav')
#     mel_mtf = id_to_pth(id, 'mel', 'mtf')
#     acc_mtf = id_to_pth(id, 'acc', 'mtf')
#     bass_mtf = id_to_pth(id, 'bass', 'mtf')

#     cough2mid.cough2midi(COUGH_PATH, mel_mtf, **MEL_CONFIG)
#     cough2mid.correct_key(mel_mtf,mel_mtf)
#     cough2mid.cough2midi(COUGH_PATH, acc_mtf, **ACC_CONFIG)
#     cough2mid.correct_key(acc_mtf,acc_mtf)
#     cough2mid.cough2midi(COUGH_PATH, bass_mtf, **BASS_CONFIG)
#     cough2mid.correct_key(bass_mtf,bass_mtf)

#     midi_paths = {
#         'mel': mel_mtf,
#         'acc': acc_mtf,
#         'bass': bass_mtf
#     }
#     wav_paths = {
#         'mel': id_to_pth(id, 'mel', 'mtf_wav'),
#         'acc': id_to_pth(id, 'acc', 'mtf_wav'),
#         'bass': id_to_pth(id, 'bass', 'mtf_wav')
#     }
#     print("Cough to mid Execution")

# ID =25
# cough2midi_test(ID, 'string', sample_rate=16000)
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



# # pth = Path(r
# "C:\Users\JYWang\Desktop\CoughDjangoServer\media\public_music\mel_wav\mel_15.wav")
# # pedalboard_process(pth, 7, 0.5, 0.3, 0.3 )

# generate_path_triomotif = cough2midi(15, 'string', './media/jag22325477@gapp.nthu.edu.tw/temp_trio', 'u256uid', sample_rate=16000)
# gen_trio_mid(15)
# generate_path_trio = gen_trio_trk(15, 'string', './media/jag22325477@gapp.nthu.edu.tw/temp_trio', 'u256uid', sample_rate=16000)


# def merge_mtf_wav_to_trio():
#     mel_mid_dir = settings.MOTIF_MEL_MID
#     acc_mid_dir = settings.MOTIF_ACC_MID
#     bass_mid_dir = settings.MOTIF_BASS_MID
#     public_cough_dir = settings.PUBLIC_COUGH    
#     mel_wav_dir = settings.MOTIF_MEL_WAV
#     acc_wav_dir = settings.MOTIF_ACC_WAV
#     bass_wav_dir = settings.MOTIF_BASS_WAV

#     trio_wav_dir = settings.MOTIF_TRIO_WAV
#     sample_rate = 16000  # 根據你的專案設定

    # 遍歷 mel_wav 目錄下所有 mel_*.wav
    # for  i, cough  in enumerate(os.listdir(public_cough_dir)):
        # if  cough.endswith(".wav"):
        #     id = os.path.splitext(cough)[0]  # 提取 ID
# for i in range (361, 368):
#             # print(f"Processing ID: {id}")
#             print(f'i', i)
#             cough2midi(i, 'string', './tmp', 'u256uid', sample_rate=16000)
#             print(f"Generated MIDI for ID: {i}")
            # midi.update_midi_program(os.path.join(acc_mid_dir, file), os.path.join(acc_mid_dir, f"acc_{id}.mid"), program_number=41)
            # midi.write_from_midi(os.path.join(acc_mid_dir, file), os.path.join(acc_wav_dir, f"acc_{id}.wav"), 'violin')
            # # acc_path = os.path.join(acc_wav_dir, f"acc_{id}.wav")
            # midi.update_midi_program(os.path.join(acc_mid_dir, f"acc_{id}.mid"), os.path.join(acc_mid_dir, f"acc_{id}.mid"), program_number=0)
            # acc_path = os.path.join(acc_wav_dir, f"acc_{id}.wav")
            # bass_path = os.path.join(bass_wav_dir, f"bass_{id}.wav")
            # trio_path = os.path.join(trio_wav_dir, f"trio_{id}.wav")

            # # 檢查三軌都存在才合併
            # if not (os.path.exists(mel_path) and os.path.exists(acc_path) and os.path.exists(bass_path)):
            #     print(f"Skip id {id}: some track missing.")
            #     continue

            # mel, _ = librosa.load(mel_path, sr=sample_rate)
            # acc, _ = librosa.load(acc_path, sr=sample_rate)
            # bass, _ = librosa.load(bass_path, sr=sample_rate)

            # max_length = max(len(mel), len(acc), len(bass))
            # mel = np.pad(mel, (0, max_length - len(mel)), 'constant')
            # acc = np.pad(acc, (0, max_length - len(acc)), 'constant')
            # bass = np.pad(bass, (0, max_length - len(bass)), 'constant')

            # merged = mel + acc + bass
            # sf.write(trio_path, merged, sample_rate)
            # print(f"Saved trio wav: {trio_path}")

# merge_mtf_wav_to_trio()