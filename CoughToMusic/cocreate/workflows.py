from __future__ import annotations

import os
import random
from pathlib import Path

from django.conf import settings

from .contracts import CoCreateRequest, CoCreateResult
from .storage import (
    get_cough_table_path,
    get_mode_temp_folder,
    get_public_cough_path,
    get_public_motif_mid_path,
    get_public_motif_wav_path,
    get_public_track_mid_path,
    get_public_track_wav_path,
    list_public_motif_mid_names,
    resolve_pub_cough_id,
)

MEL_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.15,
    "note_interval_th": 20,
    "min_target": "C3",
    "max_target": "C6",
    "energy_th": -1000,
}

ACC_CONFIG = {
    "threshold": 0.25,
    "freq_range_th": 0.45,
    "note_interval_th": 40,
    "min_target": "C2",
    "max_target": "C4",
    "energy_th": -1000,
}

BASS_CONFIG = {
    "threshold": 0.4,
    "freq_range_th": 0.95,
    "note_interval_th": 40,
    "min_target": "C1",
    "max_target": "C3",
    "energy_th": -1000,
}

TRACKS = ("mel", "acc", "bass")
INSTRUMENT_PROGRAMS = {"mel": 40, "acc": 41, "bass": 43}


def run_trio(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = _ensure_temp_folder(request.user_id, "trio")
    pub_cough_id = resolve_pub_cough_id(request.user_id, request.coughlist[0], get_cough_table_path(request.user_id))
    trio_motif_path = _generate_public_trio_motif(pub_cough_id, request.user_id, request.job_uuid)
    used_cough_paths, used_motif_paths = _generate_trio_midi_sequence(pub_cough_id)
    generated_music = _render_trio_tracks(pub_cough_id, request.user_id, request.job_uuid, user_tmp_folder)
    return CoCreateResult(
        generated_music=generated_music,
        cough_paths=request.cough_paths,
        cough_motifs=[trio_motif_path],
        used_public_paths=used_cough_paths,
        used_motif_paths=used_motif_paths,
    )


def run_trio_manual(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = _ensure_temp_folder(request.user_id, "trio_manual")
    mid_dic = {"mel": [], "acc": [], "bass": []}
    merged_trio_motif_wavs: list[str] = []

    for cough_path in request.coughlist:
        merged_trio_motif_wavs.append(_cough2mid_manual(cough_path, user_tmp_folder, mid_dic))

    _generate_trio_manual(user_tmp_folder, mid_dic, request.job_uuid)
    generated_manual_trio = _render_trio_manual_tracks(user_tmp_folder, request.job_uuid)
    return CoCreateResult(
        generated_music=generated_manual_trio,
        cough_paths=request.cough_paths,
        cough_motifs=merged_trio_motif_wavs,
    )


def run_drum_manual(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = _ensure_temp_folder(request.user_id, "drum_manual")
    generated_manual_drum, drum_motif_wavs = _generate_manual_drum(request.coughlist, user_tmp_folder, request.job_uuid)
    return CoCreateResult(
        generated_music=generated_manual_drum,
        cough_paths=request.cough_paths,
        cough_motifs=[os.path.join(settings.BASE_DIR, str(path)) for path in drum_motif_wavs],
    )


def run_drum_autofill(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = _ensure_temp_folder(request.user_id, "drum")
    generated_path, used_public_paths, drum_motif_wavs = _generate_autofill_drum(
        request.coughlist,
        user_tmp_folder,
        request.job_uuid,
    )
    public_base = os.path.abspath(settings.PUBLIC_COUGH)
    return CoCreateResult(
        generated_music=generated_path,
        cough_paths=request.cough_paths,
        cough_motifs=[str(path) for path in drum_motif_wavs[: len(request.coughlist)]],
        used_public_paths=[str(path) for path in used_public_paths if os.path.abspath(path).startswith(public_base)],
        used_motif_paths=[os.path.join(settings.BASE_DIR, str(path)) for path in drum_motif_wavs[len(request.coughlist) :]],
    )


def _ensure_temp_folder(user_id: str, mode: str) -> str:
    temp_folder = get_mode_temp_folder(user_id, mode)
    temp_folder.mkdir(parents=True, exist_ok=True)
    return str(temp_folder)


def _generate_public_trio_motif(pub_cough_id: int, user_id: str, job_uuid: str) -> str:
    from .lib import cough2mid, midi
    import librosa
    import numpy as np
    import soundfile as sf

    public_cough_path = str(get_public_cough_path(pub_cough_id))
    mel_mtf = str(get_public_motif_mid_path("mel", pub_cough_id))
    acc_mtf = str(get_public_motif_mid_path("acc", pub_cough_id))
    bass_mtf = str(get_public_motif_mid_path("bass", pub_cough_id))

    cough2mid.cough2midi(public_cough_path, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf, mel_mtf)
    cough2mid.cough2midi(public_cough_path, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf, acc_mtf)
    cough2mid.cough2midi(public_cough_path, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf, bass_mtf)

    midi_paths = {"mel": mel_mtf, "acc": acc_mtf, "bass": bass_mtf}
    wav_paths = {track: str(get_public_motif_wav_path(track, pub_cough_id)) for track in TRACKS}
    merged_output_path = str(Path(settings.MOTIF_TRIO_WAV) / f"trio_{pub_cough_id}.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = midi_paths[track]
        wav_path = wav_paths[track]
        tmp_mid_pth = os.path.join(settings.MEDIA_ROOT, user_id, f"{job_uuid}_{track}_short_trio.mid")
        midi.update_midi_program(midi_path, tmp_mid_pth, program_number=program)
        midi.write_from_midi(tmp_mid_pth, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path


def _generate_trio_midi_sequence(pub_cough_id: int) -> tuple[list[str], list[str]]:
    from .lib.generation import generate_melody_from_sequence

    midi_files = [filename for filename in list_public_motif_mid_names("mel") if filename != f"mel_{pub_cough_id}.mid"]
    selected = random.sample(midi_files, 2)

    def extract_id(filename: str) -> int:
        return int(filename.replace("mel_", "").replace(".mid", ""))

    sequence = [pub_cough_id] + [extract_id(filename) for filename in selected]
    print(f"MIDI sequence: {sequence}")

    for track in TRACKS:
        sequence_paths = [str(get_public_motif_mid_path(track, item_id)) for item_id in sequence]
        output_mid = str(get_public_track_mid_path(track, pub_cough_id))
        generate_melody_from_sequence(sequence_paths, output_mid)

    used_cough_paths = [str(get_public_cough_path(item_id)) for item_id in sequence if str(item_id) != str(pub_cough_id)]
    used_motif_paths = [
        str(Path(settings.MOTIF_TRIO_WAV) / f"trio_{item_id}.wav")
        for item_id in sequence
        if str(item_id) != str(pub_cough_id)
    ]
    return used_cough_paths, used_motif_paths


def _render_trio_tracks(pub_cough_id: int, user_id: str, job_uuid: str, user_tmp_folder: str) -> str:
    from .lib import midi
    import librosa
    import numpy as np
    import soundfile as sf

    merged_output_path = os.path.join(user_tmp_folder, f"{job_uuid}_trio.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = str(get_public_track_mid_path(track, pub_cough_id))
        wav_path = str(get_public_track_wav_path(track, pub_cough_id))
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path


def _cough2mid_manual(cough_path: Path, user_folder: str, mid_dic: dict[str, list[str]]) -> str:
    from .lib import cough2mid, midi
    import librosa
    import numpy as np
    import soundfile as sf

    cough_name = cough_path.stem
    mel_mtf = os.path.join(user_folder, f"{cough_name}_mel_mtf.mid")
    acc_mtf = os.path.join(user_folder, f"{cough_name}_acc_mtf.mid")
    bass_mtf = os.path.join(user_folder, f"{cough_name}_bass_mtf.mid")
    cough_str = str(cough_path)

    cough2mid.cough2midi(cough_str, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf, mel_mtf)
    mid_dic["mel"].append(mel_mtf)
    cough2mid.cough2midi(cough_str, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf, acc_mtf)
    mid_dic["acc"].append(acc_mtf)
    cough2mid.cough2midi(cough_str, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf, bass_mtf)
    mid_dic["bass"].append(bass_mtf)

    midi.update_midi_program(mel_mtf, os.path.join(user_folder, f"{cough_name}_mel_motif.mid"), program_number=INSTRUMENT_PROGRAMS["mel"])
    midi.update_midi_program(acc_mtf, os.path.join(user_folder, f"{cough_name}_acc_motif.mid"), program_number=INSTRUMENT_PROGRAMS["acc"])
    midi.update_midi_program(bass_mtf, os.path.join(user_folder, f"{cough_name}_bass_motif.mid"), program_number=INSTRUMENT_PROGRAMS["bass"])

    mel_wav = os.path.join(user_folder, f"{cough_name}_mel_mtf.wav")
    acc_wav = os.path.join(user_folder, f"{cough_name}_acc_mtf.wav")
    bass_wav = os.path.join(user_folder, f"{cough_name}_bass_mtf.wav")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_mel_motif.mid"), mel_wav, "violin")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_acc_motif.mid"), acc_wav, "violin")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_bass_motif.mid"), bass_wav, "violin")

    mel, _ = librosa.load(mel_wav, sr=16000)
    acc, _ = librosa.load(acc_wav, sr=16000)
    bass, _ = librosa.load(bass_wav, sr=16000)
    max_length = max(len(mel), len(acc), len(bass))
    mel = np.pad(mel, (0, max_length - len(mel)), "constant")
    acc = np.pad(acc, (0, max_length - len(acc)), "constant")
    bass = np.pad(bass, (0, max_length - len(bass)), "constant")
    merged = mel + acc + bass
    trio_wav = os.path.join(user_folder, f"{cough_name}_trio_mtf.wav")
    sf.write(trio_wav, merged, 16000)
    return trio_wav


def _generate_trio_manual(user_folder: str, mid_dic: dict[str, list[str]], job_uuid: str) -> None:
    from .lib.generation import generate_melody_from_sequence

    for track in TRACKS:
        intrp_mid_pth = os.path.join(user_folder, f"{job_uuid}_{track}_trio.mid")
        generate_melody_from_sequence(mid_dic[track], intrp_mid_pth)


def _render_trio_manual_tracks(user_folder: str, job_uuid: str) -> str:
    from .lib import midi
    import librosa
    import numpy as np
    import soundfile as sf

    merged_output_path = os.path.join(user_folder, f"{job_uuid}_trio.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = os.path.join(user_folder, f"{job_uuid}_{track}_trio.mid")
        wav_path = os.path.join(user_folder, f"{job_uuid}_{track}_trio.wav")
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path


def _generate_manual_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> tuple[str, list[str]]:
    from .lib import midi
    from .lib.drum import process_manual_coughs, write_midi_pretty_manual
    from .lib.generation import concatenate_sequences, concate_interpolation, interpolated_groove, path_to_note_seq

    assert len(cough_path_list) == 7, "Expecting exactly 7 cough files"
    drum_trk = os.path.join(user_folder, f"{job_uuid}_drum.wav")
    selected_coughs, df = process_manual_coughs([str(path) for path in cough_path_list])
    print(f"Selected coughs: {selected_coughs}")

    tmp_first = "tmp/first.mid"
    tmp_sec = "tmp/sec.mid"
    tmp_third = "tmp/third.mid"
    tmp_last = "tmp/last.mid"
    tmp_last2 = "tmp/last2.mid"

    cough_seq = list(selected_coughs.items())
    motif_list: list[str] = []

    def save_midi(seq_slice: slice, out_path: str) -> str:
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, [str(path) for path in cough_path_list], out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path

    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i + 1), f"tmp/drum_motif{i}.mid")
        wav_path = str(Path(mid_path).with_suffix(".wav"))
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


def _generate_autofill_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> tuple[str, list[str], list[str]]:
    from .lib import midi
    from .lib.drum import process_autofill_coughs, write_midi_pretty_manual
    from .lib.generation import concatenate_sequences, concate_interpolation, interpolated_groove, path_to_note_seq

    selected_coughs, df, id_to_path, used_public_paths = process_autofill_coughs(
        [str(path) for path in cough_path_list],
        settings.PUBLIC_COUGH,
    )

    tmp_first = "tmp/first.mid"
    tmp_sec = "tmp/sec.mid"
    tmp_third = "tmp/third.mid"
    tmp_last = "tmp/last.mid"
    tmp_last2 = "tmp/last2.mid"
    drum_trk = os.path.join(user_folder, f"{job_uuid}_drum.wav")

    cough_seq = list(selected_coughs.items())
    motif_list: list[str] = []

    def save_midi(seq_slice: slice, out_path: str) -> str:
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, list(id_to_path.values()), out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path

    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i + 1), f"tmp/drum_motif{i}.mid")
        wav_path = str(Path(mid_path).with_suffix(".wav"))
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

    selected_paths = [id_to_path[cid] for cid in selected_coughs.values() if cid in df["name"].values]
    return drum_trk, selected_paths, motif_list
