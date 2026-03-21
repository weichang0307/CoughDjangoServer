from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass
class DrumAutofillResult:
    generated_music: str
    used_public_paths: list[str]
    motif_paths: list[Path]


def _drum_temp_file(user_folder: str, name: str) -> str:
    return str(Path(user_folder) / name)


def generate_manual_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> tuple[str, list[Path]]:
    from .lib import midi
    from .lib.drum import process_manual_coughs, write_midi_pretty_manual
    from .lib.generation import concatenate_sequences, concate_interpolation, interpolated_groove, path_to_note_seq

    assert len(cough_path_list) == 7, "Expecting exactly 7 cough files"
    drum_trk = os.path.join(user_folder, f"{job_uuid}_drum.wav")
    selected_coughs, df = process_manual_coughs([str(path) for path in cough_path_list])

    tmp_first = _drum_temp_file(user_folder, f"{job_uuid}_first.mid")
    tmp_sec = _drum_temp_file(user_folder, f"{job_uuid}_sec.mid")
    tmp_third = _drum_temp_file(user_folder, f"{job_uuid}_third.mid")
    tmp_last = _drum_temp_file(user_folder, f"{job_uuid}_last.mid")
    tmp_last2 = _drum_temp_file(user_folder, f"{job_uuid}_last2.mid")

    cough_seq = list(selected_coughs.items())
    motif_list: list[Path] = []

    def save_midi(seq_slice: slice, out_path: str) -> str:
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, [str(path) for path in cough_path_list], out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path

    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i + 1), _drum_temp_file(user_folder, f"{job_uuid}_drum_motif{i}.mid"))
        wav_path = Path(mid_path).with_suffix(".wav")
        midi.write_from_midi(mid_path, str(wav_path))
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

    return drum_trk, motif_list


def generate_autofill_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> DrumAutofillResult:
    from .lib import midi
    from .lib.drum import process_autofill_coughs, write_midi_pretty_manual
    from .lib.generation import concatenate_sequences, concate_interpolation, interpolated_groove, path_to_note_seq

    selected_coughs, df, id_to_path, used_public_paths = process_autofill_coughs(
        [str(path) for path in cough_path_list],
        settings.PUBLIC_COUGH,
    )

    tmp_first = _drum_temp_file(user_folder, f"{job_uuid}_first.mid")
    tmp_sec = _drum_temp_file(user_folder, f"{job_uuid}_sec.mid")
    tmp_third = _drum_temp_file(user_folder, f"{job_uuid}_third.mid")
    tmp_last = _drum_temp_file(user_folder, f"{job_uuid}_last.mid")
    tmp_last2 = _drum_temp_file(user_folder, f"{job_uuid}_last2.mid")
    drum_trk = os.path.join(user_folder, f"{job_uuid}_drum.wav")

    cough_seq = list(selected_coughs.items())
    motif_list: list[Path] = []

    def save_midi(seq_slice: slice, out_path: str) -> str:
        subset = dict(cough_seq[seq_slice])
        write_midi_pretty_manual(subset, df, list(id_to_path.values()), out_path)
        midi.adjust_to_2bars(out_path, out_path)
        return out_path

    for i in range(len(cough_seq)):
        mid_path = save_midi(slice(i, i + 1), _drum_temp_file(user_folder, f"{job_uuid}_drum_motif{i}.mid"))
        wav_path = Path(mid_path).with_suffix(".wav")
        midi.write_from_midi(mid_path, str(wav_path))
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

    return DrumAutofillResult(
        generated_music=drum_trk,
        used_public_paths=list(used_public_paths),
        motif_paths=motif_list,
    )
