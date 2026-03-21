import csv
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import shutil
import uuid
import wave
import types
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from CoughToMusic.cocreate import storage as cocreate_storage
from CoughToMusic.cocreate.contracts import CoCreateResult


def _stub_task_module():
    module = types.ModuleType("CoughToMusic.task")
    module.task_progress = {}
    return module


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
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_cocreate_workflows_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate.workflows",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_views_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.views",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )


class CoCreateRefactorTests(TestCase):
    def setUp(self):
        super().setUp()
        self._temp_media_path = os.path.join(
            settings.BASE_DIR,
            "media",
            f"test_media_{uuid.uuid4().hex}",
        )
        os.makedirs(self._temp_media_path, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self._temp_media_path, ignore_errors=True))

        self._override = override_settings(MEDIA_ROOT=self._temp_media_path)
        self._override.enable()
        self.addCleanup(self._override.disable)

        os.makedirs(os.path.join(self._temp_media_path, "public_cough"), exist_ok=True)
        os.makedirs(os.path.join(self._temp_media_path, "public_motif", "mel_mid"), exist_ok=True)

    def _make_job(self, mode, cough_names, user_id="refactor-user"):
        return type(
            "Job",
            (),
            {
                "mode": mode,
                "uuid": f"{mode}-uuid",
                "user_id": user_id,
                "data": {
                    "user_id": user_id,
                    "bass": "Tuba",
                    "alto": "Clarinet",
                    "high": "Flute",
                    "cough_path": "^".join(cough_names),
                },
                "coughlist": [
                    Path(self._temp_media_path) / user_id / "cough_audio" / f"{name}.wav"
                    for name in cough_names
                ],
                "file_path": str(
                    Path(self._temp_media_path) / user_id / "cough_audio" / f"{cough_names[0]}.wav"
                ),
            },
        )()

    def test_generation_mode_normalization_for_co_create(self):
        with patch.dict(sys.modules, {"CoughToMusic.task": _stub_task_module()}):
            from CoughToMusic.services import generation as generation_service

            self.assertEqual(generation_service._normalize_generation_mode("co_create_trio", 1), "trio")
            self.assertEqual(generation_service._normalize_generation_mode("co_create_trio", 4), "trio_manual")
            self.assertEqual(generation_service._normalize_generation_mode("co_create_drum", 6), "drum")
            self.assertEqual(generation_service._normalize_generation_mode("co_create_drum", 7), "drum_manual")
            with self.assertRaises(ValueError):
                generation_service._normalize_generation_mode("co_create_trio", 5)

    def test_generation_modes_delegate_to_workflows(self):
        cases = [
            ("trio", "run_trio"),
            ("trio_manual", "run_trio_manual"),
            ("drum_manual", "run_drum_manual"),
            ("drum", "run_drum_autofill"),
        ]
        with patch.dict(sys.modules, {"CoughToMusic.task": _stub_task_module()}):
            from CoughToMusic.services import generation_modes

            for mode, patch_name in cases:
                job = self._make_job(mode, ["listed"])
                captured = {}

                def fake_runner(request):
                    captured["request"] = request
                    return CoCreateResult(
                        generated_music=f"{mode}.wav",
                        cough_paths=request.cough_paths,
                        cough_motifs=["m1.wav"],
                        used_public_paths=["public.wav"],
                        used_motif_paths=["motif.wav"],
                    )

                with patch(f"CoughToMusic.services.generation_modes.{patch_name}", side_effect=fake_runner):
                    payload = generation_modes.execute_generation_mode(job)

                self.assertEqual(payload["generated_music"], f"{mode}.wav")
                self.assertEqual(payload["cough_paths"], [str(job.coughlist[0])])
                self.assertEqual(captured["request"].mode, mode)
                self.assertEqual(captured["request"].user_id, job.user_id)
                self.assertIsInstance(captured["request"].coughlist[0], Path)

    def test_resolve_pub_cough_id_reads_cough_table(self):
        user_id = "refactor-user"
        cough_dir = Path(self._temp_media_path) / user_id / "cough_audio"
        cough_dir.mkdir(parents=True, exist_ok=True)
        table_path = cough_dir / "cough_table.csv"
        with table_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["filename", "pubCoughID"])
            writer.writeheader()
            writer.writerow({"filename": "listed.wav", "pubCoughID": "42"})

        resolved = cocreate_storage.resolve_pub_cough_id(user_id, cough_dir / "listed.wav")
        self.assertEqual(resolved, 42)

    def test_resolve_pub_cough_id_raises_when_row_is_missing(self):
        user_id = "refactor-user"
        cough_dir = Path(self._temp_media_path) / user_id / "cough_audio"
        cough_dir.mkdir(parents=True, exist_ok=True)
        table_path = cough_dir / "cough_table.csv"
        with table_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["filename", "pubCoughID"])
            writer.writeheader()
            writer.writerow({"filename": "other.wav", "pubCoughID": "42"})

        with self.assertRaises(ValueError):
            cocreate_storage.resolve_pub_cough_id(user_id, cough_dir / "listed.wav")

    def test_save_music_move_preserves_cocreate_folder_mapping(self):
        from CoughToMusic.util import save_music_move

        user_id = "refactor-user"
        cases = [
            ("trio", "temp_trio", "generated_trio", "_trio.wav"),
            ("trio_manual", "temp_manual_trio", "generated_manual_trio", "_trio.wav"),
            ("drum_manual", "temp_manual_drum", "generated_manual_drum", "_drum.wav"),
            ("drum", "temp_autofill_drum", "generated_autofill_drum", "_drum.wav"),
        ]

        with patch("builtins.print"), patch("CoughToMusic.util.update_music_table") as update_table:
            for output_type, temp_folder_name, final_folder_name, suffix in cases:
                temp_folder = Path(self._temp_media_path) / user_id / temp_folder_name
                temp_folder.mkdir(parents=True, exist_ok=True)
                source_file = temp_folder / f"job-1{suffix}"
                source_file.write_bytes(b"wave")

                save_music_move(user_id, "job-1", "song", output_type)

                expected_file = Path(self._temp_media_path) / user_id / final_folder_name / "song" / f"song{suffix}"
                self.assertTrue(expected_file.exists(), expected_file)
                self.assertFalse(source_file.exists())

        self.assertEqual(update_table.call_count, len(cases))

class UploadFilterIsolationTests(TestCase):
    def setUp(self):
        super().setUp()
        self._temp_media_path = os.path.join(
            settings.BASE_DIR,
            "media",
            f"test_media_{uuid.uuid4().hex}",
        )
        os.makedirs(self._temp_media_path, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self._temp_media_path, ignore_errors=True))

        self._override = override_settings(MEDIA_ROOT=self._temp_media_path)
        self._override.enable()
        self.addCleanup(self._override.disable)

        os.makedirs(os.path.join(self._temp_media_path, "public_cough"), exist_ok=True)

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
            self._temp_media_path,
            self.user_id,
            "cough_audio",
            "cough_table.csv",
        )

    def _wav_path(self, stem):
        return os.path.join(
            self._temp_media_path,
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
            self.assertIn("forced filter worker failure", failed_response.content.decode().lower())
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
            self.assertIn("forced public filter worker failure", failed_response.content.decode().lower())
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

    def test_get_coughs_returns_rows_when_people_column_is_false_string(self):
        cough_dir = os.path.join(self._temp_media_path, self.user_id, "cough_audio")
        wav_path = os.path.join(cough_dir, "listed.wav")
        with wave.open(wav_path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(self._pcm16_bytes())

        with open(self._cough_table_path(), "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "filename",
                    "timestamp",
                    "pubCoughID",
                    "time",
                    "latitude",
                    "longitude",
                    "clusterID",
                    "people",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "listed.wav",
                    "timestamp": "2026-03-20 00:00:00",
                    "pubCoughID": "-1",
                    "time": "listed",
                    "latitude": "0",
                    "longitude": "0",
                    "clusterID": "3",
                    "people": "False",
                }
            )

        response = self.client.post(
            reverse("get_coughs"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["filename"], "listed")
        self.assertEqual(payload[0]["clusterID"], "3")


class LegacyLibraryCsrfRegressionTests(TestCase):
    def setUp(self):
        super().setUp()
        self._temp_media_path = os.path.join(
            settings.BASE_DIR,
            "media",
            f"test_media_{uuid.uuid4().hex}",
        )
        os.makedirs(self._temp_media_path, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self._temp_media_path, ignore_errors=True))

        self._override = override_settings(MEDIA_ROOT=self._temp_media_path)
        self._override.enable()
        self.addCleanup(self._override.disable)

        self.client = Client(enforce_csrf_checks=True)
        self.user_id = "csrf-user"

        cough_dir = os.path.join(self._temp_media_path, self.user_id, "cough_audio")
        os.makedirs(cough_dir, exist_ok=True)
        with open(os.path.join(cough_dir, "cough_table.csv"), "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "filename",
                    "timestamp",
                    "pubCoughID",
                    "time",
                    "latitude",
                    "longitude",
                    "clusterID",
                    "people",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "listed.wav",
                    "timestamp": "2026-03-20 12:00:00",
                    "pubCoughID": "-1",
                    "time": "listed",
                    "latitude": "0",
                    "longitude": "0",
                    "clusterID": "1",
                    "people": "False",
                }
            )

    def test_get_cough_statistics_post_is_not_blocked_by_csrf(self):
        response = self.client.post(
            reverse("get_cough_statistics"),
            data=json.dumps(
                {
                    "userId": self.user_id,
                    "startDate": "2026-03-19 00:00:00",
                    "endDate": "2026-03-21 00:00:00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["allTime"], ["listed"])


class MigratedViewsTests(TestCase):
    def setUp(self):
        super().setUp()
        self._temp_media_path = os.path.join(
            settings.BASE_DIR,
            "media",
            f"test_media_{uuid.uuid4().hex}",
        )
        os.makedirs(self._temp_media_path, exist_ok=False)
        self.import_cough_folder = os.path.join(self._temp_media_path, "import_cough")
        self.public_music_folder = os.path.join(self._temp_media_path, "public_music")
        os.makedirs(self.import_cough_folder, exist_ok=True)
        os.makedirs(self.public_music_folder, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self._temp_media_path, ignore_errors=True))

        self._override = override_settings(
            MEDIA_ROOT=self._temp_media_path,
            IMPORT_COUGH_FOLDER=self.import_cough_folder,
            PUBLIC_MUSIC=self.public_music_folder,
        )
        self._override.enable()
        self.addCleanup(self._override.disable)

        self.user_id = "migrated-user"
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
            "userEmail": "jay@example.com",
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

    def _user_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, f"{self.user_id}.csv")

    def _cough_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, "cough_audio", "cough_table.csv")

    def _music_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, "generated_music", "music_table.csv")

    @staticmethod
    def _pcm16_bytes(sample_count=1600):
        return b"\x00\x00" * sample_count

    def _write_wav(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(self._pcm16_bytes())

    def _write_csv(self, path, fieldnames, rows):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_get_and_set_user_info_round_trip(self):
        get_response = self.client.post(
            reverse("get_user_info"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(get_response.status_code, 200, get_response.content.decode())
        self.assertEqual(get_response.json()["name"], "Jay")

        set_response = self.client.post(
            reverse("set_user_info"),
            data=json.dumps({"userId": self.user_id, "name": "Robin", "age": 61}),
            content_type="application/json",
        )
        self.assertEqual(set_response.status_code, 200, set_response.content.decode())

        with open(self._user_table_path(), newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["name"], "Robin")
        self.assertEqual(row["age"], "61.0")

    def test_start_stop_record_refresh_best_song_and_submit_survey(self):
        start_response = self.client.post(
            reverse("start_record"),
            data=json.dumps({"userId": self.user_id, "isPublish": True}),
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 200, start_response.content.decode())

        with open(self._user_table_path(), newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["isCoughPublish"], "True")

        stop_response = self.client.post(
            reverse("stop_record"),
            data=json.dumps({"userId": self.user_id, "detectTime": "10"}),
            content_type="application/json",
        )
        self.assertEqual(stop_response.status_code, 200, stop_response.content.decode())
        self.assertEqual(stop_response.json()["message"], "start audio.")

        set_best_response = self.client.post(
            reverse("refresh_best_song"),
            data=json.dumps({"userId": self.user_id, "target": "song-a"}),
            content_type="application/json",
        )
        self.assertEqual(set_best_response.status_code, 200, set_best_response.content.decode())
        self.assertEqual(set_best_response.json()["bestSong1"], "song-a")

        get_best_response = self.client.post(
            reverse("refresh_best_song"),
            data=json.dumps({"userId": self.user_id, "target": ""}),
            content_type="application/json",
        )
        self.assertEqual(get_best_response.status_code, 200, get_best_response.content.decode())
        self.assertEqual(get_best_response.json()["bestSong1"], "song-a")

        survey_response = self.client.post(
            reverse("submit_survey"),
            data=json.dumps(
                {
                    "userId": self.user_id,
                    "fileName": "song-a",
                    "source_type": "generated",
                    "source_detail": {"kind": "normal"},
                    "selected_mode": "normal",
                    "satisfaction": "5",
                    "perception_of_others": "4",
                    "thoughts": "ok",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(survey_response.status_code, 200, survey_response.content.decode())

        survey_table_path = os.path.join(self._temp_media_path, self.user_id, "survey_table.csv")
        with open(survey_table_path, newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["filename"], "song-a")
        self.assertEqual(row["source_detail"], '{"kind": "normal"}')
        self.assertEqual(row["satisfaction"], "5")

    def test_get_music_returns_records_from_all_generated_folders(self):
        cases = [
            ("generated_music", "normal", "normal-song", "normal-song.wav"),
            ("generated_trio", "trio", "trio-song", "trio-song_trio.wav"),
            ("generated_autofill_drum", "drum", "drum-song", "drum-song_drum.wav"),
            ("generated_manual_drum", "drum_manual", "manual-drum", "manual-drum_drum.wav"),
            ("generated_manual_trio", "trio_manual", "manual-trio", "manual-trio_trio.wav"),
        ]
        for folder, _, subdir, filename in cases:
            self._write_wav(os.path.join(self._temp_media_path, self.user_id, folder, subdir, filename))

        response = self.client.post(
            reverse("get_music"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(len(payload), 5)
        self.assertEqual({item["type"] for item in payload}, {case[1] for case in cases})

    def test_get_uploads_file_supports_full_and_range_requests(self):
        file_path = os.path.join(self._temp_media_path, self.user_id, "generated_music", "clip.wav")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as handle:
            handle.write(b"abcdefghij")

        encoded_path = file_path.replace("\\", "^").replace("/", "^")
        full_response = self.client.get(reverse("get_uploads_file", args=[encoded_path]))
        self.assertEqual(full_response.status_code, 200)
        self.assertEqual(b"".join(full_response.streaming_content), b"abcdefghij")

        partial_response = self.client.get(
            reverse("get_uploads_file", args=[encoded_path]),
            HTTP_RANGE="bytes=2-5",
        )
        self.assertEqual(partial_response.status_code, 206)
        self.assertEqual(partial_response["Content-Range"], "bytes 2-5/10")
        self.assertEqual(b"".join(partial_response.streaming_content)[:4], b"cdef")

    def test_cough_and_music_info_endpoints_return_rows(self):
        self._write_csv(
            self._cough_table_path(),
            ["filename", "timestamp", "pubCoughID", "time", "latitude", "longitude", "clusterID", "people"],
            [
                {
                    "filename": "listed.wav",
                    "timestamp": "2026-03-20 12:00:00",
                    "pubCoughID": "-1",
                    "time": "listed",
                    "latitude": "0",
                    "longitude": "0",
                    "clusterID": "1",
                    "people": "False",
                }
            ],
        )
        self._write_csv(
            self._music_table_path(),
            ["filename", "timestamp", "time", "mood"],
            [{"filename": "song", "timestamp": "1710986400", "time": "song", "mood": "calm"}],
        )

        cough_response = self.client.post(
            reverse("get_cough_info"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(cough_response.status_code, 200, cough_response.content.decode())
        self.assertEqual(cough_response.json()[0]["filename"], "listed.wav")

        music_response = self.client.post(
            reverse("get_music_info"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(music_response.status_code, 200, music_response.content.decode())
        self.assertEqual(music_response.json()[0]["mood"], "calm")

    def test_music_statistics_preserves_shape(self):
        now = int(datetime.datetime.now().timestamp())
        self._write_csv(
            self._music_table_path(),
            ["filename", "timestamp", "time"],
            [
                {"filename": "song-a", "timestamp": str(now), "time": "song-a"},
                {"filename": "song-b", "timestamp": str(now - 3600), "time": "song-b"},
            ],
        )

        response = self.client.post(
            reverse("get_music_statistics"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["allTime"], ["song-a", "song-b"])
        self.assertEqual(payload["day"], "2")

    def test_set_cough_info_updates_matching_row_only(self):
        self._write_csv(
            self._cough_table_path(),
            ["filename", "timestamp", "pubCoughID", "time", "latitude", "longitude", "clusterID", "people"],
            [
                {
                    "filename": "listed.wav",
                    "timestamp": "2026-03-20 12:00:00",
                    "pubCoughID": "-1",
                    "time": "listed",
                    "latitude": "0",
                    "longitude": "0",
                    "clusterID": "1",
                    "people": "False",
                }
            ],
        )

        response = self.client.post(
            reverse("set_cough_info"),
            data=json.dumps({"userId": self.user_id, "filename": "listed.wav", "clusterID": "9", "latitude": "25"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

        with open(self._cough_table_path(), newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["clusterID"], "9")
        self.assertEqual(rows[0]["latitude"], "25")

    def test_set_music_info_updates_matching_row_only(self):
        self._write_csv(
            self._music_table_path(),
            ["filename", "timestamp", "time", "mood"],
            [{"filename": "song", "timestamp": "1710986400", "time": "song", "mood": "calm"}],
        )

        response = self.client.post(
            reverse("set_music_info"),
            data=json.dumps({"userId": self.user_id, "filename": "song", "mood": "bright"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

        with open(self._music_table_path(), newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mood"], "bright")

    def test_delete_music_removes_file_and_music_table_row(self):
        target_path = os.path.join(
            self._temp_media_path,
            self.user_id,
            "generated_music",
            "song-a",
            "song-a.wav",
        )
        self._write_wav(target_path)
        self._write_csv(
            self._music_table_path(),
            ["filename", "timestamp", "time"],
            [{"filename": "song-a", "timestamp": "1710986400", "time": "song-a"}],
        )

        response = self.client.post(
            reverse("delete_music"),
            data=json.dumps({"userId": self.user_id, "targetList": [target_path]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertFalse(os.path.exists(target_path))

        with open(self._music_table_path(), newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows, [])

    def test_rename_music_keeps_files_and_music_table_aligned(self):
        wav_path = os.path.join(
            self._temp_media_path,
            self.user_id,
            "generated_music",
            "song-a",
            "song-a.wav",
        )
        midi_path = os.path.join(
            self._temp_media_path,
            self.user_id,
            "generated_midi",
            "song-a",
            "song-a.mid",
        )
        self._write_wav(wav_path)
        os.makedirs(os.path.dirname(midi_path), exist_ok=True)
        with open(midi_path, "wb") as handle:
            handle.write(b"midi")
        self._write_csv(
            self._music_table_path(),
            ["filename", "timestamp", "time"],
            [{"filename": "song-a", "timestamp": "1710986400", "time": "song-a"}],
        )

        response = self.client.post(
            reverse("rename_music"),
            data=json.dumps({"userId": self.user_id, "oldName": "song-a", "name": "song-b"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(
            os.path.exists(
                os.path.join(self._temp_media_path, self.user_id, "generated_music", "song-b", "song-b.wav")
            )
        )
        self.assertTrue(
            os.path.exists(
                os.path.join(self._temp_media_path, self.user_id, "generated_midi", "song-b", "song-b.mid")
            )
        )

        with open(self._music_table_path(), newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["filename"], "song-b")

    def test_public_upload_endpoints_write_to_expected_shared_folders(self):
        cough_upload = SimpleUploadedFile("public.wav", self._pcm16_bytes(), content_type="audio/wav")
        cough_response = self.client.post(
            reverse("upload_to_public_cough"),
            data={"metadata": json.dumps({"fileName": "imported"}), "file": cough_upload},
        )
        self.assertEqual(cough_response.status_code, 200, cough_response.content.decode())
        self.assertTrue(os.path.exists(os.path.join(self.import_cough_folder, "imported.wav")))

        music_upload = SimpleUploadedFile("music.wav", self._pcm16_bytes(), content_type="audio/wav")
        music_response = self.client.post(
            reverse("upload_to_public_music"),
            data={"metadata": json.dumps({"fileName": "public-song"}), "file": music_upload},
        )
        self.assertEqual(music_response.status_code, 200, music_response.content.decode())
        self.assertTrue(os.path.exists(os.path.join(self.public_music_folder, "public-song.wav")))


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
