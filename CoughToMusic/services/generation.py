import json
import os
import uuid
from pathlib import Path

from django.conf import settings

from ..runtime.generation_queue import enqueue_job, get_generation_job, get_generation_jobs_snapshot, remove_completed_job
from ..task import GenerateJob
from ..util import save_music_move


def enqueue_generation_request(data):
    mode = data.get("mode", "normal")
    user_id = data.get("user_id")
    coughlist_str = data.get("cough_path", None)
    coughlist_path = [path for path in (coughlist_str.split("^") if coughlist_str else []) if path]
    coughlist = [
        Path(os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", f"{path}.wav"))
        for path in coughlist_path
    ]

    normalized_mode = _normalize_generation_mode(mode, len(coughlist_path))
    job_uuid = str(uuid.uuid4())
    job = GenerateJob(normalized_mode, data, job_uuid, user_id, coughlist)
    enqueue_job(job)
    return job_uuid


def enqueue_realtime_generation(user_id, cough_path):
    data = {"user_id": user_id, "bass": "tuba", "alto": "clarinet", "high": "flute"}
    job_uuid = str(uuid.uuid4())
    job = GenerateJob("normal", data, job_uuid, user_id, [Path(cough_path)])
    enqueue_job(job)
    return job_uuid


def get_generation_status_payload(raw_body):
    data = json.loads(raw_body.decode("utf-8"))
    job_uuid = data.get("uuid")
    user_id = data.get("userId")

    if job_uuid:
        job = get_generation_job(job_uuid)
        if not job:
            return {"error": "UUID not found"}, 404
        return {
            "uuid": job.uuid,
            "mode": job.mode,
            "time": job.time,
            "duration": job.duration,
            "status": job.status,
            "result": job.result if job.status == "completed" else None,
        }, 200

    snapshot = get_generation_jobs_snapshot(user_id=user_id)
    all_jobs = [_serialize_queued_job(job) for job in snapshot["queued"]]
    all_jobs.extend(_serialize_job(job) for job in snapshot["processing"])
    all_jobs.extend(_serialize_job(job) for job in snapshot["completed"])
    return all_jobs, 200


def save_music_result(user_id, job_uuid, file_name, output_type):
    remove_completed_job(job_uuid)
    save_music_move(user_id, job_uuid, file_name, output_type)


def save_cocreate_result(user_id, job_uuid, file_name):
    from ..co_create_utils import save_final_cocreate

    save_final_cocreate(user_id, job_uuid, file_name)


def _normalize_generation_mode(mode, cough_length):
    if mode == "co_create_trio":
        if cough_length == 1:
            return "trio"
        if 2 <= cough_length <= 4:
            return "trio_manual"
        raise ValueError("Trio mode supports 2-4 cough inputs.")

    if mode == "co_create_drum":
        if 1 <= cough_length <= 6:
            return "drum"
        if cough_length == 7:
            return "drum_manual"
        raise ValueError("Drum mode supports 1-7 cough inputs.")

    return mode


def _serialize_job(job):
    return {
        "uuid": job.uuid,
        "mode": job.mode,
        "time": job.time,
        "duration": job.duration,
        "status": job.status,
        "result": job.result,
    }


def _serialize_queued_job(job):
    payload = _serialize_job(job)
    payload["cough_path"] = job.data.get("cough_path")
    return payload
