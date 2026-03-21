from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CoCreateRequest:
    mode: str
    user_id: str
    job_uuid: str
    coughlist: list[Path]
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def cough_paths(self) -> list[str]:
        return [str(path) for path in self.coughlist]


@dataclass
class CoCreateResult:
    generated_music: str
    cough_paths: list[str]
    cough_motifs: list[str] = field(default_factory=list)
    used_public_paths: list[str] = field(default_factory=list)
    used_motif_paths: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

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
