import json
import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .support import COUGH_TABLE_FIELDS, TempMediaMixin


class UploadFilterIsolationTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(public_cough=True)
        self.user_id = "jay"
        self.sign_up_user(self.user_id)

    def _upload_audio(self, stem):
        metadata = {
            "userId": self.user_id,
            "fileName": stem,
            "latitude": "0",
            "longitude": "0",
            "mode": "normal",
        }
        upload = SimpleUploadedFile(f"{stem}.wav", self.pcm16_bytes(), content_type="audio/wav")
        return self.client.post(
            reverse("upload_audio"),
            data={"metadata": json.dumps(metadata), "file": upload},
        )

    def _cough_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, "cough_audio", "cough_table.csv")

    def _wav_path(self, stem):
        return os.path.join(self._temp_media_path, self.user_id, "cough_audio", f"{stem}.wav")

    def _read_cough_rows(self):
        return self.read_csv_rows(self._cough_table_path())

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
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=7):
            failed_response = self._upload_audio("first")
            self.assertEqual(failed_response.status_code, 400)
            self.assertIn("forced filter worker failure", failed_response.content.decode().lower())
            self.assert_file_exists(self._wav_path("first"))
            self.assertEqual(self._read_cough_rows(), [])

            success_response = self._upload_audio("second")
            self.assertEqual(success_response.status_code, 200, success_response.content.decode())
            self.assert_file_exists(self._wav_path("second"))

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
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=7):
            failed_response = self._upload_audio("public-first")
            self.assertEqual(failed_response.status_code, 400)
            self.assertIn("forced public filter worker failure", failed_response.content.decode().lower())
            self.assert_file_exists(self._wav_path("public-first"))
            self.assertEqual(self._read_cough_rows(), [])

            success_response = self._upload_audio("public-second")
            self.assertEqual(success_response.status_code, 200, success_response.content.decode())
            self.assert_file_exists(self._wav_path("public-second"))

        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["filename"], "public-second.wav")
        self.assertEqual(rows[0]["clusterID"], "7")
        self.assertEqual(call_state["count"], 4)

    def test_get_coughs_returns_rows_when_people_column_is_false_string(self):
        cough_dir = os.path.join(self._temp_media_path, self.user_id, "cough_audio")
        wav_path = os.path.join(cough_dir, "listed.wav")
        self.write_wav(wav_path)

        self.write_csv(
            self._cough_table_path(),
            COUGH_TABLE_FIELDS,
            [
                self.make_cough_row(
                    timestamp="2026-03-20 00:00:00",
                    cluster_id="3",
                )
            ],
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
