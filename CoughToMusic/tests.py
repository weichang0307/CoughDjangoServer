import csv
import json
import os
import tempfile
import subprocess
import sys
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from CoughToMusic.runtime import generation_queue
from CoughToMusic.services import generation as generation_service


class RuntimeStartupTests(TestCase):
    def _assert_module_import_is_lazy(self, module_name, forbidden_modules):
        env = os.environ.copy()
        env.setdefault("DJANGO_SETTINGS_MODULE", "CoughToMusicDjango.settings")
        env["FORBIDDEN_MODULES"] = ",".join(forbidden_modules)

        code = (
            "import importlib, os, sys\n"
            "forbidden = [name for name in os.environ['FORBIDDEN_MODULES'].split(',') if name]\n"
            f"importlib.import_module({module_name!r})\n"
            "raise SystemExit(1 if any(name in sys.modules for name in forbidden) else 0)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"{module_name} eagerly imported one of {forbidden_modules}: {result.stdout}{result.stderr}",
        )

    def test_util_import_keeps_heavy_audio_stack_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.util",
            ["librosa", "soundfile"],
        )

    def test_task_import_keeps_generation_helpers_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.task",
            ["CoughToMusic.co_create_utils", "librosa", "soundfile"],
        )


class UploadFilterIsolationTests(TestCase):
    def setUp(self):
        super().setUp()
        self._temp_media = tempfile.TemporaryDirectory(dir=settings.BASE_DIR)
        self.addCleanup(self._temp_media.cleanup)

        self._override = override_settings(MEDIA_ROOT=self._temp_media.name)
        self._override.enable()
        self.addCleanup(self._override.disable)

        os.makedirs(os.path.join(self._temp_media.name, "public_cough"), exist_ok=True)

        self.user_id = "jay"
        self._sign_up_user()

    def _sign_up_user(self):
        payload = {
            "userId": self.user_id,
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
        response = self.client.post(
            reverse("sign_up"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

    def _upload_audio(self, stem):
        metadata = {
            "userId": self.user_id,
            "fileName": stem,
            "latitude": "0",
            "longitude": "0",
            "mode": "normal",
        }
        upload = SimpleUploadedFile(
            f"{stem}.wav",
            self._pcm16_bytes(),
            content_type="audio/wav",
        )
        return self.client.post(
            reverse("upload_audio"),
            data={"metadata": json.dumps(metadata), "file": upload},
        )

    @staticmethod
    def _pcm16_bytes(sample_count=1600):
        return b"\x00\x00" * sample_count

    def _cough_table_path(self):
        return os.path.join(
            self._temp_media.name,
            self.user_id,
            "cough_audio",
            "cough_table.csv",
        )

    def _wav_path(self, stem):
        return os.path.join(
            self._temp_media.name,
            self.user_id,
            "cough_audio",
            f"{stem}.wav",
        )

    def _read_cough_rows(self):
        path = self._cough_table_path()
        if not os.path.exists(path):
            return []

        with open(path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_failed_upload_does_not_poison_next_upload_in_same_process(self):
        call_state = {"count": 0}

        def run_cli_hook(*args, **kwargs):
            payload = kwargs["payload"]
            if payload["mode"] != "filter":
                raise AssertionError(f"Unexpected worker mode in test: {payload['mode']}")

            call_state["count"] += 1
            if call_state["count"] == 1:
                return {
                    "ok": False,
                    "error": "Forced filter worker failure",
                    "stdout": "",
                    "stderr": "",
                }

            return {
                "ok": True,
                "json": {
                    "path": payload["audio_path"],
                    "sr": 16000,
                    "segments": [],
                    "mode": payload.get("write_mode", "mask"),
                    "energy_gate": payload.get("apply_energy_gate", True),
                },
                "stdout": "",
                "stderr": "",
            }

        with patch("CoughToMusic.util.run_cli", side_effect=run_cli_hook), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={
                "has_non_user_cough": False,
                "has_user_cough": True,
            },
        ), patch("CoughToMusic.services.uploads.clustering", return_value=7):
            failed_response = self._upload_audio("first")
            self.assertEqual(failed_response.status_code, 400)
            self.assertIn("forced worker failure", failed_response.content.decode())
            self.assertTrue(os.path.exists(self._wav_path("first")))
            self.assertEqual(self._read_cough_rows(), [])

            success_response = self._upload_audio("second")
            self.assertEqual(success_response.status_code, 200, success_response.content.decode())
            self.assertTrue(os.path.exists(self._wav_path("second")))

        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["filename"], "second.wav")
        self.assertEqual(rows[0]["clusterID"], "7")
        self.assertEqual(call_state["count"], 3)

    def test_public_copy_filter_failure_does_not_poison_next_upload_in_same_process(self):
        call_state = {"count": 0}

        def run_cli_hook(*args, **kwargs):
            payload = kwargs["payload"]
            if payload["mode"] != "filter":
                raise AssertionError(f"Unexpected worker mode in test: {payload['mode']}")

            call_state["count"] += 1
            if call_state["count"] == 2:
                return {
                    "ok": False,
                    "error": "Forced public filter worker failure",
                    "stdout": "",
                    "stderr": "",
                }

            return {
                "ok": True,
                "json": {
                    "path": payload["audio_path"],
                    "sr": 16000,
                    "segments": [],
                    "mode": payload.get("write_mode", "mask"),
                    "energy_gate": payload.get("apply_energy_gate", True),
                },
                "stdout": "",
                "stderr": "",
            }

        with patch("CoughToMusic.util.run_cli", side_effect=run_cli_hook), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={
                "has_non_user_cough": False,
                "has_user_cough": True,
            },
        ), patch("CoughToMusic.services.uploads.clustering", return_value=7):
            failed_response = self._upload_audio("public-first")
            self.assertEqual(failed_response.status_code, 400)
            self.assertIn("forced public filter worker failure", failed_response.content.decode())
            self.assertTrue(os.path.exists(self._wav_path("public-first")))
            self.assertEqual(self._read_cough_rows(), [])

            success_response = self._upload_audio("public-second")
            self.assertEqual(success_response.status_code, 200, success_response.content.decode())
            self.assertTrue(os.path.exists(self._wav_path("public-second")))

        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["filename"], "public-second.wav")
        self.assertEqual(rows[0]["clusterID"], "7")
        self.assertEqual(call_state["count"], 4)


class GenerationRuntimeTests(TestCase):
    def setUp(self):
        super().setUp()
        generation_queue._runtime = None

    def tearDown(self):
        generation_queue._runtime = None
        super().tearDown()

    def test_runtime_is_lazy_until_generate(self):
        self.assertIsNone(generation_queue._runtime)

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
        self.assertIsNone(generation_queue._runtime)

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
        self.assertIsNotNone(generation_queue._runtime)

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
        with patch("CoughToMusic.services.generation.remove_completed_job") as remove_job, patch(
            "CoughToMusic.services.generation.save_music_move"
        ) as save_move:
            generation_service.save_music_result("jay", "job-1", "song", "normal")

        remove_job.assert_called_once_with("job-1")
        save_move.assert_called_once_with("jay", "job-1", "song", "normal")
