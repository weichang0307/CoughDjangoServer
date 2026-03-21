from __future__ import annotations

from pathlib import Path

from .contracts import CoCreateResult
from .storage import get_mode_temp_folder

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


def ensure_temp_folder(user_id: str, mode: str) -> str:
    temp_folder = get_mode_temp_folder(user_id, mode)
    temp_folder.mkdir(parents=True, exist_ok=True)
    return str(temp_folder)


def create_result(
    *,
    generated_music: str | Path,
    cough_paths: list[str | Path],
    cough_motifs: list[str | Path] | None = None,
    used_public_paths: list[str | Path] | None = None,
    used_motif_paths: list[str | Path] | None = None,
    extra: dict | None = None,
) -> CoCreateResult:
    return CoCreateResult(
        generated_music=generated_music,
        cough_paths=cough_paths,
        cough_motifs=list(cough_motifs or []),
        used_public_paths=list(used_public_paths or []),
        used_motif_paths=list(used_motif_paths or []),
        extra=dict(extra or {}),
    )
