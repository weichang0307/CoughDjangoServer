from __future__ import annotations

from dataclasses import dataclass, field
from os import fspath
from pathlib import Path
from typing import Any


def _coerce_path(value: Any) -> str:
    return fspath(value)


def _coerce_paths(values: list[Any]) -> list[str]:
    return [_coerce_path(value) for value in values]


@dataclass
class CoCreateRequest:
    mode: str
    user_id: str
    job_uuid: str
    coughlist: list[Path]
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def cough_paths(self) -> list[str]:
        return _coerce_paths(self.coughlist)


@dataclass
class CoCreateResult:
    generated_music: str | Path
    cough_paths: list[str | Path]
    cough_motifs: list[str | Path] = field(default_factory=list)
    used_public_paths: list[str | Path] = field(default_factory=list)
    used_motif_paths: list[str | Path] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.generated_music = _coerce_path(self.generated_music)
        self.cough_paths = _coerce_paths(self.cough_paths)
        self.cough_motifs = _coerce_paths(self.cough_motifs)
        self.used_public_paths = _coerce_paths(self.used_public_paths)
        self.used_motif_paths = _coerce_paths(self.used_motif_paths)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generated_music": self.generated_music,
            "cough_paths": list(self.cough_paths),
        }
        if self.cough_motifs:
            payload["cough_motifs"] = list(self.cough_motifs)
        if self.used_public_paths:
            payload["used_public_paths"] = list(self.used_public_paths)
        if self.used_motif_paths:
            payload["used_motif_paths"] = list(self.used_motif_paths)
        payload.update(self.extra)
        return payload
