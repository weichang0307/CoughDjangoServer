from __future__ import annotations

from pathlib import Path

from .contracts import CoCreateRequest
from .drum_adapters import generate_autofill_drum, generate_manual_drum
from .workflow_common import create_result, ensure_temp_folder


def run_drum_manual(request: CoCreateRequest):
    user_tmp_folder = ensure_temp_folder(request.user_id, "drum_manual")
    generated_manual_drum, drum_motif_wavs = generate_manual_drum(request.coughlist, user_tmp_folder, request.job_uuid)
    return create_result(
        generated_music=generated_manual_drum,
        cough_paths=request.cough_paths,
        cough_motifs=drum_motif_wavs,
    )


def run_drum_autofill(request: CoCreateRequest):
    user_tmp_folder = ensure_temp_folder(request.user_id, "drum")
    generated_path, used_public_paths, drum_motif_wavs = generate_autofill_drum(
        request.coughlist,
        user_tmp_folder,
        request.job_uuid,
    )
    return create_result(
        generated_music=generated_path,
        cough_paths=request.cough_paths,
        cough_motifs=list(drum_motif_wavs[: len(request.coughlist)]),
        used_public_paths=[Path(path) for path in used_public_paths],
        used_motif_paths=list(drum_motif_wavs[len(request.coughlist) :]),
    )
