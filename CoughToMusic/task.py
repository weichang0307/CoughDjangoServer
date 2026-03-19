import time

from .services.generation_modes import execute_generation_mode

task_progress = {}


class GenerateJob:
    def __init__(self, mode, data, uuid, user_id, coughlist):
        self.user_id = user_id
        self.mode = mode
        self.data = data
        self.uuid = uuid
        self.time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        self.duration = None
        self.status = "queued"
        self.result = None
        self.coughlist = coughlist
        self.file_path = str(coughlist[0]) if coughlist else None
        print(f"self_file_path: {self.file_path}")

    def run(self):
        try:
            self.status = "processing"
            task_progress[self.uuid] = self
            start_time = time.time()
            self.result = execute_generation_mode(self)
            self.duration = round(time.time() - start_time, 2)
            self.status = "completed"
        except Exception as exc:
            self.status = "failed"
            self.result = {"error": str(exc)}
        finally:
            task_progress[self.uuid] = self
