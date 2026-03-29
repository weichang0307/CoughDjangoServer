from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class DrumAutofillResult:
    generated_music: str
    used_public_paths: list[str]
    motif_paths: list[Path]


def _drum_temp_file(user_folder: str, name: str) -> str:
    return str(Path(user_folder) / name)


def _concatenate_drum_stage_midis(stage_paths: list[str], output_path: str) -> str:
    import magenta.music as mm
    import note_seq

    sequences = [note_seq.midi_io.midi_file_to_note_sequence(path) for path in stage_paths]
    final_seq = mm.sequences_lib.concatenate_sequences(sequences, [4.0] * len(sequences))
    mm.sequence_proto_to_midi_file(final_seq, output_path)
    return output_path


def _concatenate_drum_stage_sequences(stage_sequences: list) -> object:
    import magenta.music as mm

    return mm.sequences_lib.concatenate_sequences(stage_sequences, [4.0] * len(stage_sequences))


def _build_staged_drum_sequence(source_midi: str, quantization_level: int, target_duration: float = 4.0):
    import note_seq
    from note_seq.protobuf import music_pb2

    original = note_seq.midi_io.midi_file_to_note_sequence(source_midi)
    staged = music_pb2.NoteSequence()
    staged.ticks_per_quarter = original.ticks_per_quarter or 220

    if original.tempos:
        tempo = staged.tempos.add()
        tempo.CopyFrom(original.tempos[0])
    else:
        staged.tempos.add(qpm=120.0)

    if original.time_signatures:
        time_signature = staged.time_signatures.add()
        time_signature.CopyFrom(original.time_signatures[0])
    else:
        staged.time_signatures.add(numerator=4, denominator=4, time=0.0)

    qpm = staged.tempos[0].qpm or 120.0
    grid_interval = (60.0 / qpm) / (quantization_level / 4)
    staged_notes = []
    max_end = 0.0

    for note in original.notes:
        new_start = round(note.start_time / grid_interval) * grid_interval
        if new_start >= target_duration:
            continue

        new_end = min(target_duration, new_start + 0.125)
        staged_notes.append((note, max(0.0, new_start), new_end))
        max_end = max(max_end, new_end)

    time_scale = (target_duration / max_end) if max_end else 1.0

    for note, new_start, new_end in staged_notes:
        new_note = staged.notes.add()
        new_note.CopyFrom(note)
        new_note.start_time = min(target_duration, new_start * time_scale)
        new_note.end_time = min(target_duration, new_end * time_scale)

    staged.total_time = target_duration
    return staged


def _write_note_sequence_midi(sequence, output_path: str) -> str:
    import note_seq

    note_seq.sequence_proto_to_midi_file(sequence, output_path)
    return output_path


def _load_note_sequence_midi(midi_path: str):
    import note_seq

    return note_seq.midi_io.midi_file_to_note_sequence(midi_path)


def _run_drum_interpolation_with_candidates(
    interpolated_groove_note_sequences,
    concate_interpolation,
    concatenate_note_sequence_objects,
    tmp_last: str,
    stage_sequences: dict[str, object],
    job_uuid: str,
) -> str:
    candidate_specs = [
        ("primary", ["sec", "third"], ["last", "last"]),
        ("alt_last_third", ["sec", "third"], ["last", "third"]),
        ("alt_third_last", ["sec", "third"], ["third", "last"]),
        ("alt_third_third", ["sec", "third"], ["third", "third"]),
    ]
    last_error: Exception | None = None

    for suffix, start_names, end_names in candidate_specs:
        start_sequence = _concatenate_drum_stage_sequences([stage_sequences[name] for name in start_names])
        end_sequence = _concatenate_drum_stage_sequences([stage_sequences[name] for name in end_names])
        try:
            interpolated_seq = interpolated_groove_note_sequences(start_sequence, end_sequence)
            concate_interpolation(start_sequence, stage_sequences["last"], interpolated_seq, tmp_last, target_duration=8.0)
            interpolated_block = _load_note_sequence_midi(tmp_last)
            concatenate_note_sequence_objects(stage_sequences["first"], interpolated_block, tmp_last)
            return tmp_last
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Drum interpolation candidate %s failed for job %s: %s",
                suffix,
                job_uuid,
                exc,
            )

    if last_error is not None:
        raise last_error
    raise ValueError("No drum interpolation candidates were available.")


def _write_cumulative_drum_fallback(
    cough_seq: list[tuple[str, str]],
    df,
    cough_paths: list[str],
    user_folder: str,
    job_uuid: str,
    save_midi,
) -> str:
    stage_paths: list[str] = []
    for i in range(len(cough_seq)):
        stage_path = _drum_temp_file(user_folder, f"{job_uuid}_fallback_stage{i}.mid")
        stage_path = save_midi(slice(0, i + 1), stage_path)
        stage_paths.append(stage_path)

    final_stage = _drum_temp_file(user_folder, f"{job_uuid}_fallback_last2.mid")
    shutil.copyfile(stage_paths[-1], final_stage)
    stage_paths.append(final_stage)

    output_path = _drum_temp_file(user_folder, f"{job_uuid}_fallback_concat.mid")
    logger.warning(
        "Falling back to cumulative drum concatenation with %d stages for job %s.",
        len(stage_paths),
        job_uuid,
    )
    return _concatenate_drum_stage_midis(stage_paths, output_path)


def generate_manual_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> tuple[str, list[Path]]:
    from .lib import midi
    from .lib.drum import process_manual_coughs, write_midi_pretty_manual
    from .lib.generation import (
        concatenate_note_sequence_objects,
        concate_interpolation,
        interpolated_groove_note_sequences,
    )

    assert len(cough_path_list) == 7, "Expecting exactly 7 cough files"
    drum_trk = os.path.join(user_folder, f"{job_uuid}_drum.wav")
    selected_coughs, df = process_manual_coughs([str(path) for path in cough_path_list])

    tmp_first = _drum_temp_file(user_folder, f"{job_uuid}_first.mid")
    tmp_sec = _drum_temp_file(user_folder, f"{job_uuid}_sec.mid")
    tmp_third = _drum_temp_file(user_folder, f"{job_uuid}_third.mid")
    tmp_last = _drum_temp_file(user_folder, f"{job_uuid}_last.mid")

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

    raw_first = save_midi(slice(0, 1), _drum_temp_file(user_folder, f"{job_uuid}_first_raw.mid"))
    raw_sec = save_midi(slice(0, 2), _drum_temp_file(user_folder, f"{job_uuid}_sec_raw.mid"))
    raw_third = save_midi(slice(0, 3), _drum_temp_file(user_folder, f"{job_uuid}_third_raw.mid"))
    raw_last = save_midi(slice(0, 7), _drum_temp_file(user_folder, f"{job_uuid}_last_raw.mid"))

    stage_sequences = {
        "first": _build_staged_drum_sequence(raw_first, 32),
        "sec": _build_staged_drum_sequence(raw_sec, 32),
        "third": _build_staged_drum_sequence(raw_third, 16),
        "last": _build_staged_drum_sequence(raw_last, 16),
    }
    tmp_first = _write_note_sequence_midi(stage_sequences["first"], tmp_first)
    tmp_sec = _write_note_sequence_midi(stage_sequences["sec"], tmp_sec)
    tmp_third = _write_note_sequence_midi(stage_sequences["third"], tmp_third)
    tmp_last = _write_note_sequence_midi(stage_sequences["last"], tmp_last)

    final_midi = tmp_last
    try:
        final_midi = _run_drum_interpolation_with_candidates(
            interpolated_groove_note_sequences,
            concate_interpolation,
            concatenate_note_sequence_objects,
            tmp_last,
            stage_sequences,
            job_uuid,
        )
    except Exception as exc:
        logger.warning(
            "Drum interpolation failed for job %s: %s. Using cumulative motif fallback.",
            job_uuid,
            exc,
        )
        final_midi = _write_cumulative_drum_fallback(
            cough_seq,
            df,
            [str(path) for path in cough_path_list],
            user_folder,
            job_uuid,
            save_midi,
        )
    midi.write_from_midi(final_midi, drum_trk)

    return drum_trk, motif_list


def generate_autofill_drum(cough_path_list: list[Path], user_folder: str, job_uuid: str) -> DrumAutofillResult:
    from .lib import midi
    from .lib.drum import process_autofill_coughs, write_midi_pretty_manual
    from .lib.generation import (
        concatenate_note_sequence_objects,
        concate_interpolation,
        interpolated_groove_note_sequences,
    )

    selected_coughs, df, id_to_path, used_public_paths = process_autofill_coughs(
        [str(path) for path in cough_path_list],
        settings.PUBLIC_COUGH,
    )

    tmp_first = _drum_temp_file(user_folder, f"{job_uuid}_first.mid")
    tmp_sec = _drum_temp_file(user_folder, f"{job_uuid}_sec.mid")
    tmp_third = _drum_temp_file(user_folder, f"{job_uuid}_third.mid")
    tmp_last = _drum_temp_file(user_folder, f"{job_uuid}_last.mid")
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

    raw_first = save_midi(slice(0, 1), _drum_temp_file(user_folder, f"{job_uuid}_first_raw.mid"))
    raw_sec = save_midi(slice(0, 2), _drum_temp_file(user_folder, f"{job_uuid}_sec_raw.mid"))
    raw_third = save_midi(slice(0, 3), _drum_temp_file(user_folder, f"{job_uuid}_third_raw.mid"))
    raw_last = save_midi(slice(0, 7), _drum_temp_file(user_folder, f"{job_uuid}_last_raw.mid"))

    stage_sequences = {
        "first": _build_staged_drum_sequence(raw_first, 32),
        "sec": _build_staged_drum_sequence(raw_sec, 32),
        "third": _build_staged_drum_sequence(raw_third, 16),
        "last": _build_staged_drum_sequence(raw_last, 16),
    }
    tmp_first = _write_note_sequence_midi(stage_sequences["first"], tmp_first)
    tmp_sec = _write_note_sequence_midi(stage_sequences["sec"], tmp_sec)
    tmp_third = _write_note_sequence_midi(stage_sequences["third"], tmp_third)
    tmp_last = _write_note_sequence_midi(stage_sequences["last"], tmp_last)

    final_midi = tmp_last
    try:
        final_midi = _run_drum_interpolation_with_candidates(
            interpolated_groove_note_sequences,
            concate_interpolation,
            concatenate_note_sequence_objects,
            tmp_last,
            stage_sequences,
            job_uuid,
        )
    except Exception as exc:
        logger.warning(
            "Autofill drum interpolation failed for job %s: %s. Using cumulative motif fallback.",
            job_uuid,
            exc,
        )
        final_midi = _write_cumulative_drum_fallback(
            cough_seq,
            df,
            list(id_to_path.values()),
            user_folder,
            job_uuid,
            save_midi,
        )
    midi.write_from_midi(final_midi, drum_trk)

    return DrumAutofillResult(
        generated_music=drum_trk,
        used_public_paths=list(used_public_paths),
        motif_paths=motif_list,
    )
