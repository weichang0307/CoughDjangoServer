from __future__ import annotations

from pathlib import Path

from ..cocreate.contracts import CoCreateRequest
from ..cocreate.workflows import run_drum_autofill, run_drum_manual, run_trio, run_trio_manual


def execute_generation_mode(job):
    if job.mode == "normal":
        return _run_normal(job)
    if job.mode == "trio":
        return _run_trio(job)
    if job.mode == "trio_manual":
        return _run_trio_manual(job)
    if job.mode == "drum_manual":
        return _run_drum_manual(job)
    if job.mode == "drum":
        return _run_drum(job)
    raise ValueError(f"Unsupported mode: {job.mode}")


def _run_normal(job):
    from ..util import generate_music

    generate_path = generate_music(
        job.data["user_id"],
        job.file_path,
        job.uuid,
        job.data["bass"].lower(),
        job.data["alto"].lower(),
        job.data["high"].lower(),
    )
    return {
        "generate_path": generate_path,
        "cough_paths": [str(path) for path in job.coughlist],
    }


def _build_cocreate_request(job):
    return CoCreateRequest(
        mode=job.mode,
        user_id=job.data["user_id"],
        job_uuid=job.uuid,
        coughlist=[Path(path) for path in job.coughlist],
        data=dict(job.data),
    )


def _run_trio(job):
    return run_trio(_build_cocreate_request(job)).to_payload()


def _run_trio_manual(job):
    return run_trio_manual(_build_cocreate_request(job)).to_payload()


def _run_drum_manual(job):
    return run_drum_manual(_build_cocreate_request(job)).to_payload()


def _run_drum(job):
    return run_drum_autofill(_build_cocreate_request(job)).to_payload()
