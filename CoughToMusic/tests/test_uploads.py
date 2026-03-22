import json
import os
import types
from unittest.mock import patch

import numpy as np

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

    def _log_test_phase(self, message):
        print(f"[test_uploads] {message}", flush=True)

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

        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.util.run_cli", side_effect=run_cli_hook
        ), patch(
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

        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.util.run_cli", side_effect=run_cli_hook
        ), patch(
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

    def test_blank_upload_short_circuits_before_worker_and_csv_write(self):
        with patch("CoughToMusic.services.uploads.is_blank", return_value=True), patch(
            "CoughToMusic.services.uploads.filter_coughs"
        ) as filter_mock, patch("CoughToMusic.services.uploads.classify_cough_event") as classify_mock, patch(
            "CoughToMusic.services.uploads.clustering"
        ) as clustering_mock, patch(
            "CoughToMusic.services.uploads._save_public_cough_copy"
        ) as public_copy_mock, patch(
            "CoughToMusic.services.uploads.update_cough_table"
        ) as update_table_mock:
            response = self._upload_audio("blank")

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload["isBlank"])
        self.assertEqual(payload["IsSaving"], "false")
        self.assertFalse(os.path.exists(self._wav_path("blank")))
        self.assertEqual(self._read_cough_rows(), [])
        filter_mock.assert_not_called()
        classify_mock.assert_not_called()
        clustering_mock.assert_not_called()
        public_copy_mock.assert_not_called()
        update_table_mock.assert_not_called()

    def test_public_cough_ids_do_not_reuse_archived_ids(self):
        archive_public_dir = os.path.join(self._temp_media_path, "archive", "public_cough")
        os.makedirs(archive_public_dir, exist_ok=True)
        self.write_wav(os.path.join(self._temp_media_path, "public_cough", "1.wav"))
        self.write_wav(os.path.join(archive_public_dir, "2.wav"))

        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.services.uploads.filter_coughs"
        ), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=4):
            response = self._upload_audio("next-public-id")

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assert_file_exists(os.path.join(self._temp_media_path, "public_cough", "3.wav"))
        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pubCoughID"], "3")

    def test_is_blank_returns_true_when_onset_is_missing(self):
        self._log_test_phase("start onset-missing is_blank test")
        fake_freq = types.ModuleType("fake_freq")
        fake_onset = types.ModuleType("fake_onset")
        fake_audio_loader = lambda *args, **kwargs: (np.ones(1600, dtype=np.float32), 16000)
        test_configs = [
            {
                "threshold": 0.25,
                "energy_th": -1000,
                "min_target": "C3",
                "max_target": "C6",
                "freq_range_th": 0.15,
                "note_interval_th": 20,
            }
        ]
        fake_onset.detect = lambda audio_data, sample_rate: np.array([])
        fake_freq.get_by_crepe = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("crepe should not run"))
        fake_freq.log_scale_frequencies = lambda frequencies, min_target, max_target: frequencies
        fake_freq.to_note_msg = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("midi should not run"))

        self._log_test_phase("importing util.is_blank for onset-missing case")
        from CoughToMusic.util import is_blank

        self._log_test_phase("calling util.is_blank for onset-missing case")
        self.assertTrue(
            is_blank(
                "dummy.wav",
                audio_loader=fake_audio_loader,
                onset_module=fake_onset,
                freq_module=fake_freq,
                configs=test_configs,
            )
        )
        self._log_test_phase("finished onset-missing is_blank test")

    def test_is_blank_returns_false_when_midi_viability_exists(self):
        self._log_test_phase("start midi-viable is_blank test")
        fake_freq = types.ModuleType("fake_freq")
        fake_onset = types.ModuleType("fake_onset")
        fake_audio_loader = lambda *args, **kwargs: (np.linspace(-1.0, 1.0, 1600, dtype=np.float32), 16000)
        test_configs = [
            {
                "threshold": 0.25,
                "energy_th": -1000,
                "min_target": "C3",
                "max_target": "C6",
                "freq_range_th": 0.15,
                "note_interval_th": 20,
            }
        ]
        fake_onset.detect = lambda audio_data, sample_rate: np.array([0.1, 0.4])
        fake_freq.get_by_crepe = lambda *args, **kwargs: (np.array([0.1, 0.2]), np.array([220.0, 330.0]))
        fake_freq.log_scale_frequencies = lambda frequencies, min_target, max_target: np.asarray(frequencies)
        fake_freq.to_note_msg = lambda *args, **kwargs: (np.array([220.0]), np.array([1]), np.array([2]))

        self._log_test_phase("importing util.is_blank for midi-viable case")
        from CoughToMusic.util import is_blank

        self._log_test_phase("calling util.is_blank for midi-viable case")
        self.assertFalse(
            is_blank(
                "dummy.wav",
                audio_loader=fake_audio_loader,
                onset_module=fake_onset,
                freq_module=fake_freq,
                configs=test_configs,
            )
        )
        self._log_test_phase("finished midi-viable is_blank test")

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
