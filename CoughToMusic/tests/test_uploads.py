import json
import os
import sys
import types
from unittest.mock import patch

import numpy as np

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from CoughToMusic.windowing import select_analysis_window

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

    def test_blank_upload_short_circuits_before_csv_write(self):
        with patch("CoughToMusic.services.uploads.is_blank", return_value=True), patch(
            "CoughToMusic.services.uploads.classify_cough_event"
        ) as classify_mock, patch("CoughToMusic.services.uploads.clustering") as clustering_mock, patch(
            "CoughToMusic.services.uploads._save_public_cough_copy"
        ) as public_copy_mock, patch("CoughToMusic.services.uploads.update_cough_table") as update_table_mock:
            response = self._upload_audio("blank")

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload["isBlank"])
        self.assertEqual(payload["IsSaving"], "false")
        self.assertFalse(os.path.exists(self._wav_path("blank")))
        self.assertEqual(self._read_cough_rows(), [])
        classify_mock.assert_not_called()
        clustering_mock.assert_not_called()
        public_copy_mock.assert_not_called()
        update_table_mock.assert_not_called()

    def test_blank_split_output_is_deleted_and_skips_csv_row(self):
        is_blank_results = iter([False, True, False])

        with patch(
            "CoughToMusic.services.uploads.is_blank", side_effect=lambda *_args, **_kwargs: next(is_blank_results)
        ), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={
                "has_non_user_cough": True,
                "has_user_cough": True,
                "user_output": np.zeros(1600, dtype=np.float32),
                "non_user_output": np.linspace(-0.2, 0.2, 1600, dtype=np.float32),
                "sample_rate": 16000,
            },
        ), patch("CoughToMusic.services.uploads.clustering", return_value=5):
            response = self._upload_audio("split-blank")

        self.assertEqual(response.status_code, 200, response.content.decode())
        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["filename"], "split-blank.wav")
        self.assertEqual(rows[1]["filename"], "split-blank_2.wav")
        self.assertFalse(os.path.exists(self._wav_path("split-blank_1")))
        self.assertTrue(os.path.exists(self._wav_path("split-blank_2")))
        self.assert_file_exists(os.path.join(self._temp_media_path, "public_cough", "1.wav"))
        self.assertFalse(os.path.exists(os.path.join(self._temp_media_path, "public_cough", "2.wav")))

    def test_upload_does_not_create_debug_copies(self):
        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=9):
            response = self._upload_audio("debug-artifact")

        self.assertEqual(response.status_code, 200, response.content.decode())
        debug_dir = os.path.join(self._temp_media_path, self.user_id, "cough_audio", "debug")
        self.assertFalse(os.path.exists(debug_dir))

    def test_upload_copies_public_audio_from_saved_user_file(self):
        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=9):
            response = self._upload_audio("public-copy")

        self.assertEqual(response.status_code, 200, response.content.decode())
        user_path = self._wav_path("public-copy")
        public_path = os.path.join(self._temp_media_path, "public_cough", "1.wav")
        self.assert_file_exists(user_path)
        self.assert_file_exists(public_path)
        with open(user_path, "rb") as user_file, open(public_path, "rb") as public_file:
            self.assertEqual(user_file.read(), public_file.read())
        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pubCoughID"], "1")

    def test_public_cough_ids_do_not_reuse_archived_ids(self):
        archive_public_dir = os.path.join(self._temp_media_path, "archive", "public_cough")
        os.makedirs(archive_public_dir, exist_ok=True)
        self.write_wav(os.path.join(self._temp_media_path, "public_cough", "1.wav"))
        self.write_wav(os.path.join(archive_public_dir, "2.wav"))

        with patch("CoughToMusic.services.uploads.is_blank", return_value=False), patch(
            "CoughToMusic.services.uploads.classify_cough_event",
            return_value={"has_non_user_cough": False, "has_user_cough": True},
        ), patch("CoughToMusic.services.uploads.clustering", return_value=4):
            response = self._upload_audio("next-public-id")

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assert_file_exists(os.path.join(self._temp_media_path, "public_cough", "3.wav"))
        rows = self._read_cough_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pubCoughID"], "3")

    def test_select_analysis_window_prefers_onset_anchored_late_content(self):
        audio = np.arange(16000 * 10, dtype=np.float32)
        window, info = select_analysis_window(
            audio,
            16000,
            onset_detector=lambda *_args, **_kwargs: np.array([6.0]),
            target_seconds=4.0,
            pre_roll_seconds=0.5,
            silence_ratio=0.0,
        )

        self.assertEqual(info["reason"], "onset")
        self.assertEqual(info["window_start_sample"], 88000)
        self.assertEqual(len(window), 16000 * 4)
        self.assertEqual(window[0], 88000.0)

    def test_select_analysis_window_falls_back_to_highest_energy_window(self):
        audio = np.arange(16000 * 10, dtype=np.float32)
        window, info = select_analysis_window(
            audio,
            16000,
            onset_detector=lambda *_args, **_kwargs: np.array([]),
            target_seconds=4.0,
            silence_ratio=0.0,
        )

        self.assertEqual(info["reason"], "energy")
        self.assertEqual(info["window_start_sample"], len(audio) - (16000 * 4))
        self.assertEqual(len(window), 16000 * 4)
        self.assertEqual(window[0], float(len(audio) - (16000 * 4)))

    def test_cough2midi_uses_shared_analysis_window_selector(self):
        fake_window = np.linspace(-0.25, 0.25, 16000 * 4, dtype=np.float32)
        called = {"window": False, "freq": False}

        def fake_window_selector(audio_data, sample_rate, **kwargs):
            called["window"] = True
            self.assertEqual(sample_rate, 16000)
            self.assertEqual(audio_data.size, 16000 * 8)
            return fake_window, {
                "reason": "test",
                "trim_start_sample": 0,
                "window_start_sample": 16000 * 4,
                "window_end_sample": 16000 * 8,
                "target_samples": 16000 * 4,
            }

        def fake_get_by_crepe(audio_data, sample_rate, threshold, energy_threshold, energy_filter=True):
            called["freq"] = True
            self.assertTrue(np.array_equal(audio_data, fake_window))
            return np.array([0.0]), np.array([220.0])

        fake_audio = types.ModuleType("audio")
        fake_audio.load_from_file = lambda *_args, **_kwargs: (np.zeros(16000 * 8, dtype=np.float32), 16000)
        fake_midi = types.ModuleType("midi")
        fake_midi.to_2bars = lambda *_args, **_kwargs: types.SimpleNamespace(save=lambda *_a, **_k: None)
        fake_midi.correct_midi_to_ref_key = lambda *_args, **_kwargs: None
        fake_midi.write_from_midi = lambda *_args, **_kwargs: None
        fake_freq = types.ModuleType("freq")
        fake_freq.get_by_crepe = fake_get_by_crepe
        fake_freq.write_midi = lambda *_args, **_kwargs: True
        fake_cough_to_midi = types.ModuleType("cough_to_midi")
        fake_cough_to_midi.__path__ = []
        fake_cough_to_midi.freq = fake_freq
        fake_cough_to_midi.onset = types.ModuleType("onset")

        with patch.dict(
            sys.modules,
            {
                "audio": fake_audio,
                "midi": fake_midi,
                "cough_to_midi": fake_cough_to_midi,
                "cough_to_midi.freq": fake_freq,
            },
        ):
            from CoughToMusic.cocreate.lib.cough2mid import cough2midi
            with patch("CoughToMusic.cocreate.lib.cough2mid.select_analysis_window", side_effect=fake_window_selector):
                result = cough2midi(
                    "fake.wav",
                    "fake.mid",
                    threshold=0.25,
                    freq_range_th=0.15,
                    note_interval_th=20,
                    min_target="C3",
                    max_target="C6",
                    energy_th=-1000,
                )

        self.assertTrue(result)
        self.assertTrue(called["window"])
        self.assertTrue(called["freq"])

    def test_is_blank_uses_shared_analysis_window_selector(self):
        called = {"window": False}
        fake_window = np.linspace(-1.0, 1.0, 16000 * 4, dtype=np.float32)

        def fake_window_selector(audio_data, sample_rate, **kwargs):
            called["window"] = True
            self.assertEqual(sample_rate, 16000)
            self.assertEqual(audio_data.size, 16000 * 8)
            return fake_window, {
                "reason": "test",
                "trim_start_sample": 0,
                "window_start_sample": 16000 * 4,
                "window_end_sample": 16000 * 8,
                "target_samples": 16000 * 4,
            }

        fake_freq = types.ModuleType("fake_freq")
        fake_onset = types.ModuleType("fake_onset")
        fake_audio_loader = lambda *args, **kwargs: (np.zeros(16000 * 8, dtype=np.float32), 16000)
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
        fake_onset.detect = lambda audio_data, sample_rate: np.array([0.2])
        fake_freq.get_by_crepe = lambda *args, **kwargs: (np.array([0.1, 0.2]), np.array([220.0, 330.0]))
        fake_freq.log_scale_frequencies = lambda frequencies, min_target, max_target: np.asarray(frequencies)
        fake_freq.to_note_msg = lambda *args, **kwargs: (np.array([220.0]), np.array([1]), np.array([2]))

        with patch("CoughToMusic.util.select_analysis_window", side_effect=fake_window_selector):
            from CoughToMusic.util import is_blank

            self.assertFalse(
                is_blank(
                    "dummy.wav",
                    audio_loader=fake_audio_loader,
                    onset_module=fake_onset,
                    freq_module=fake_freq,
                    configs=test_configs,
                )
            )

        self.assertTrue(called["window"])

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
