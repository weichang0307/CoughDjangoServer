from __future__ import annotations

from pathlib import Path

from .contracts import CoCreateRequest
from .storage import get_cough_table_path, resolve_pub_cough_id
from .trio_adapters import (
    build_manual_trio_motif,
    generate_manual_trio_sequence,
    generate_public_trio_motif,
    generate_trio_midi_sequence,
    render_manual_trio_tracks,
    render_public_trio_tracks,
)
from .workflow_common import create_result, ensure_temp_folder


def run_trio(request: CoCreateRequest):
    user_tmp_folder = ensure_temp_folder(request.user_id, "trio")
    pub_cough_id = resolve_pub_cough_id(request.user_id, request.coughlist[0], get_cough_table_path(request.user_id))
    trio_motif_path = generate_public_trio_motif(pub_cough_id, request.user_id, request.job_uuid)
    used_cough_paths, used_motif_paths = generate_trio_midi_sequence(pub_cough_id)
    generated_music = render_public_trio_tracks(pub_cough_id, request.user_id, request.job_uuid, user_tmp_folder)
    return create_result(
        generated_music=generated_music,
        cough_paths=request.cough_paths,
        cough_motifs=[trio_motif_path],
        used_public_paths=used_cough_paths,
        used_motif_paths=used_motif_paths,
    )


def run_trio_manual(request: CoCreateRequest):
    user_tmp_folder = ensure_temp_folder(request.user_id, "trio_manual")
    mid_dic = {"mel": [], "acc": [], "bass": []}
    merged_trio_motif_wavs: list[Path] = []

    for cough_path in request.coughlist:
        merged_trio_motif_wavs.append(build_manual_trio_motif(cough_path, user_tmp_folder, mid_dic))

    generate_manual_trio_sequence(user_tmp_folder, mid_dic, request.job_uuid)
    generated_manual_trio = render_manual_trio_tracks(user_tmp_folder, request.job_uuid)
    return create_result(
        generated_music=generated_manual_trio,
        cough_paths=request.cough_paths,
        cough_motifs=merged_trio_motif_wavs,
    )
