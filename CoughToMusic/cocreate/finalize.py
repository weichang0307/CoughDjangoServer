from ..runtime.generation_queue import get_generation_job
from ..util import save_music_move


def finalize_cocreate_result(user_id: str, job_uuid: str, file_name: str) -> None:
    job = get_generation_job(job_uuid)
    if job is None:
        raise ValueError(f"Unknown generation job: {job_uuid}")
    save_music_move(user_id, job_uuid, file_name, job.mode)
