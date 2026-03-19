from queue import Queue
from threading import Lock, Thread

from ..task import task_progress


class _GenerationRuntime:
    def __init__(self):
        self.queue = Queue()
        self.processing_jobs = []
        self.completed_jobs = []
        self._thread = Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        while True:
            job = self.queue.get()
            print(f"[Worker] Running job {job.uuid} ({job.mode})")
            self.processing_jobs.append(job)
            try:
                job.run()
            finally:
                if job in self.processing_jobs:
                    self.processing_jobs.remove(job)
                self.completed_jobs.append(job)
                print(f"[Worker] Finished job {job.uuid}")
                self.queue.task_done()


_runtime = None
_runtime_lock = Lock()


def _get_runtime(start=False):
    global _runtime
    if _runtime is not None or not start:
        return _runtime

    with _runtime_lock:
        if _runtime is None:
            _runtime = _GenerationRuntime()
    return _runtime


def ensure_generation_runtime_started():
    return _get_runtime(start=True)


def enqueue_job(job):
    runtime = ensure_generation_runtime_started()
    task_progress[job.uuid] = job
    runtime.queue.put(job)


def get_generation_job(job_uuid):
    return task_progress.get(job_uuid)


def get_generation_jobs_snapshot(user_id=None):
    runtime = _get_runtime(start=False)
    if runtime is None:
        return {
            "queued": [],
            "processing": [],
            "completed": [],
        }

    def filter_by_user(jobs):
        if not user_id:
            return list(jobs)
        return [job for job in jobs if getattr(job, "user_id", None) == user_id]

    return {
        "queued": filter_by_user(list(runtime.queue.queue)),
        "processing": filter_by_user(runtime.processing_jobs),
        "completed": filter_by_user(runtime.completed_jobs),
    }


def remove_completed_job(job_uuid):
    runtime = _get_runtime(start=False)
    if runtime is None:
        return

    for job in list(runtime.completed_jobs):
        if job.uuid == job_uuid:
            runtime.completed_jobs.remove(job)
            break
