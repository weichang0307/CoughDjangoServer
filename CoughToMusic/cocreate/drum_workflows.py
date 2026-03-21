from __future__ import annotations

import os

from django.conf import settings

from .contracts import CoCreateRequest, CoCreateResult
from .drum_adapters import generate_autofill_drum, generate_manual_drum
from .workflow_common import ensure_temp_folder


def run_drum_manual(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = ensure_temp_folder(request.user_id, "drum_manual")
    generated_manual_drum, drum_motif_wavs = generate_manual_drum(request.coughlist, user_tmp_folder, request.job_uuid)
    return CoCreateResult(
        generated_music=generated_manual_drum,
        cough_paths=request.cough_paths,
        cough_motifs=[os.path.join(settings.BASE_DIR, str(path)) for path in drum_motif_wavs],
    )


def run_drum_autofill(request: CoCreateRequest) -> CoCreateResult:
    user_tmp_folder = ensure_temp_folder(request.user_id, "drum")
    generated_path, used_public_paths, drum_motif_wavs = generate_autofill_drum(
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
