from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional, Union

from django.conf import settings

MODE_TO_TEMP_FOLDER = {
    "trio": "temp_trio",
    "trio_manual": "temp_manual_trio",
    "drum_manual": "temp_manual_drum",
    "drum": "temp_autofill_drum",
}

MODE_TO_GENERATED_FOLDER = {
    "trio": "generated_trio",
    "trio_manual": "generated_manual_trio",
    "drum_manual": "generated_manual_drum",
    "drum": "generated_autofill_drum",
}

TRACK_SETTING_NAMES = {
    "mel": ("TRACK_MEL_MID", "TRACK_MEL_WAV", "MOTIF_MEL_MID", "MOTIF_MEL_WAV"),
    "acc": ("TRACK_ACC_MID", "TRACK_ACC_WAV", "MOTIF_ACC_MID", "MOTIF_ACC_WAV"),
    "bass": ("TRACK_BASS_MID", "TRACK_BASS_WAV", "MOTIF_BASS_MID", "MOTIF_BASS_WAV"),
    "drum": ("TRACK_DRUM_MID", "TRACK_DRUM_WAV", "MOTIF_DRUM_MID", "MOTIF_DRUM_WAV"),
}


def get_user_folder(user_id: str) -> Path:
    return Path(settings.MEDIA_ROOT) / user_id


def get_cough_audio_folder(user_id: str) -> Path:
    return get_user_folder(user_id) / "cough_audio"


def get_cough_table_path(user_id: str) -> Path:
    return get_cough_audio_folder(user_id) / "cough_table.csv"


def get_mode_temp_folder(user_id: str, mode: str) -> Path:
    return get_user_folder(user_id) / MODE_TO_TEMP_FOLDER[mode]


def get_mode_temp_path(user_id: str, mode: str, *parts: str) -> Path:
    return get_mode_temp_folder(user_id, mode).joinpath(*parts)


def get_mode_generated_folder(user_id: str, mode: str) -> Path:
    return get_user_folder(user_id) / MODE_TO_GENERATED_FOLDER[mode]


def get_public_cough_path(cough_id: Union[int, str]) -> Path:
    return Path(settings.PUBLIC_COUGH) / f"{cough_id}.wav"


def get_public_track_mid_path(track: str, item_id: Union[int, str]) -> Path:
    setting_name = TRACK_SETTING_NAMES[track][0]
    return Path(getattr(settings, setting_name)) / f"{track}_{item_id}.mid"


def get_public_track_wav_path(track: str, item_id: Union[int, str]) -> Path:
    setting_name = TRACK_SETTING_NAMES[track][1]
    return Path(getattr(settings, setting_name)) / f"{track}_{item_id}.wav"


def get_public_motif_mid_path(track: str, item_id: Union[int, str]) -> Path:
    setting_name = TRACK_SETTING_NAMES[track][2]
    return Path(getattr(settings, setting_name)) / f"{track}_{item_id}.mid"


def get_public_motif_wav_path(track: str, item_id: Union[int, str]) -> Path:
    setting_name = TRACK_SETTING_NAMES[track][3]
    return Path(getattr(settings, setting_name)) / f"{track}_{item_id}.wav"


def list_public_motif_mid_names(track: str) -> list[str]:
    motif_dir = Path(getattr(settings, TRACK_SETTING_NAMES[track][2]))
    return sorted(entry.name for entry in motif_dir.iterdir() if entry.name.endswith(".mid"))


def resolve_pub_cough_id(
    user_id: str,
    cough_path: Union[str, Path],
    cough_table_path: Optional[Union[str, Path]] = None,
) -> int:
    table_path = Path(cough_table_path) if cough_table_path else get_cough_table_path(user_id)
    cough_name = Path(str(cough_path)).name
    if not cough_name.endswith(".wav"):
        cough_name = f"{cough_name}.wav"

    if not table_path.exists():
        raise ValueError(f"Missing cough table: {table_path}")

    with table_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("filename") == cough_name:
                try:
                    return int(row["pubCoughID"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid pubCoughID for {cough_name} in {table_path}") from exc

    raise ValueError(f"Could not resolve pubCoughID for {cough_name} in {table_path}")
