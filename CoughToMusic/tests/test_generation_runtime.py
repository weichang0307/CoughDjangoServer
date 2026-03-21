import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class GenerationRuntimeTests(TestCase):
    def setUp(self):
        super().setUp()
        from CoughToMusic.runtime import generation_queue

        self.generation_queue = generation_queue
        generation_queue._runtime = None

    def tearDown(self):
        self.generation_queue._runtime = None
        super().tearDown()

    def test_runtime_is_lazy_until_generate(self):
        self.assertIsNone(self.generation_queue._runtime)

        sign_up_response = self.client.post(
            reverse("sign_up"),
            data=json.dumps(
                {
                    "userId": "queue-user",
                    "name": "Jay",
                    "age": 60,
                    "gender": "male",
                    "education": "doctorate",
                    "musicProficiency": 6,
                    "isCoughPublish": False,
                    "userEmail": "",
                    "bestSong1": "",
                    "bestSong2": "",
                    "bestSong3": "",
                    "isSmoker": "no",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(sign_up_response.status_code, 200, sign_up_response.content.decode())
        self.assertIsNone(self.generation_queue._runtime)

        def fast_run(job_self):
            job_self.status = "completed"
            job_self.result = {"generate_path": "stub"}
            job_self.duration = 0

        with patch("CoughToMusic.task.GenerateJob.run", new=fast_run):
            generate_response = self.client.post(
                reverse("generate"),
                data=json.dumps(
                    {
                        "mode": "normal",
                        "user_id": "queue-user",
                        "cough_path": "seed",
                        "bass": "tuba",
                        "alto": "clarinet",
                        "high": "flute",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(generate_response.status_code, 202, generate_response.content.decode())
        self.assertIsNotNone(self.generation_queue._runtime)

    def test_generation_status_payload_serializes_runtime_snapshot(self):
        class StubJob:
            def __init__(self, uuid, status, result=None):
                self.uuid = uuid
                self.mode = "normal"
                self.time = "2026-03-20 00:00:00"
                self.duration = 0.1
                self.status = status
                self.result = result
                self.data = {"cough_path": "seed"}

        payload = json.dumps({"userId": "queue-user"}).encode("utf-8")
        from CoughToMusic.services import generation as generation_service

        with patch(
            "CoughToMusic.services.generation.get_generation_jobs_snapshot",
            return_value={
                "queued": [StubJob("queued-1", "queued")],
                "processing": [StubJob("proc-1", "processing")],
                "completed": [StubJob("done-1", "completed", {"generate_path": "stub"})],
            },
        ):
            data, status_code = generation_service.get_generation_status_payload(payload)

        self.assertEqual(status_code, 200)
        self.assertEqual([job["uuid"] for job in data], ["queued-1", "proc-1", "done-1"])
        self.assertEqual(data[0]["cough_path"], "seed")
        self.assertEqual(data[2]["result"], {"generate_path": "stub"})

    def test_save_music_result_removes_completed_job_before_move(self):
        from CoughToMusic.services import generation as generation_service

        with patch("CoughToMusic.services.generation.remove_completed_job") as remove_job, patch(
            "CoughToMusic.services.generation.save_music_move"
        ) as save_move:
            generation_service.save_music_result("jay", "job-1", "song", "normal")

        remove_job.assert_called_once_with("job-1")
        save_move.assert_called_once_with("jay", "job-1", "song", "normal")
