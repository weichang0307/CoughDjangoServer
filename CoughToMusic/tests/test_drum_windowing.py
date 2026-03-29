import os
import types
from unittest.mock import patch

import numpy as np

from django.test import TestCase

from .support import TempMediaMixin


class DrumWindowingTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(public_cough=True)

    def test_manual_drum_analysis_and_render_use_selected_window(self):
        from CoughToMusic.cocreate.lib.drum import process_manual_coughs, write_midi_pretty_manual

        user_id = "drum-user"
        cough_dir = os.path.join(self._temp_media_path, user_id, "cough_audio")
        os.makedirs(cough_dir, exist_ok=True)
        cough_path = os.path.join(cough_dir, "late.wav")
        self.write_wav(cough_path)

        raw_audio = np.arange(16000 * 8, dtype=np.float32)
        window_audio = np.arange(16000 * 4, dtype=np.float32) + 100000.0
        selected_calls = {"window": 0, "detect": 0, "offsets": 0}

        def fake_load_from_file(path):
            self.assertEqual(path, cough_path)
            return raw_audio, 16000

        def fake_window_selector(audio_data, sample_rate, **kwargs):
            selected_calls["window"] += 1
            self.assertTrue(np.array_equal(audio_data, raw_audio))
            self.assertEqual(sample_rate, 16000)
            return window_audio, {
                "reason": "test",
                "trim_start_sample": 0,
                "window_start_sample": 0,
                "window_end_sample": len(window_audio),
                "target_samples": len(window_audio),
            }

        def fake_detect(audio_data, sample_rate):
            selected_calls["detect"] += 1
            self.assertTrue(np.array_equal(audio_data, window_audio))
            self.assertEqual(sample_rate, 16000)
            return np.array([0.5, 1.0], dtype=np.float32)

        def fake_detect_offsets(audio_data, sample_rate, onset_times):
            selected_calls["offsets"] += 1
            self.assertTrue(np.array_equal(audio_data, window_audio))
            self.assertEqual(sample_rate, 16000)
            self.assertTrue(np.array_equal(onset_times, np.array([0.5, 1.0], dtype=np.float32)))
            return onset_times, onset_times + 0.25

        fake_pretty_midi = types.SimpleNamespace()

        class FakeNote:
            def __init__(self, velocity, pitch, start, end):
                self.velocity = velocity
                self.pitch = pitch
                self.start = start
                self.end = end

        class FakeInstrument:
            def __init__(self, program=0, is_drum=False):
                self.program = program
                self.is_drum = is_drum
                self.notes = []

        class FakePrettyMIDI:
            def __init__(self, *args, **kwargs):
                self.instruments = []

            def write(self, output_path):
                with open(output_path, "wb") as handle:
                    handle.write(b"")

        fake_pretty_midi.PrettyMIDI = FakePrettyMIDI
        fake_pretty_midi.Instrument = FakeInstrument
        fake_pretty_midi.Note = FakeNote

        with patch("CoughToMusic.cocreate.lib.drum.audio.load_from_file", side_effect=fake_load_from_file), patch(
            "CoughToMusic.cocreate.lib.drum.select_analysis_window", side_effect=fake_window_selector
        ), patch("CoughToMusic.cocreate.lib.drum.detect", side_effect=fake_detect), patch(
            "CoughToMusic.cocreate.lib.drum.detect_offsets", side_effect=fake_detect_offsets
        ), patch(
            "CoughToMusic.cocreate.lib.drum.pretty_midi", fake_pretty_midi
        ), patch(
            "CoughToMusic.cocreate.lib.drum.merge_midi_tracks"
        ):
            selected_coughs, df = process_manual_coughs([cough_path])
            output_midi = os.path.join(cough_dir, "late.mid")
            write_midi_pretty_manual(selected_coughs, df, [cough_path], output_midi)

        self.assertEqual(selected_calls["window"], 2)
        self.assertEqual(selected_calls["detect"], 2)
        self.assertEqual(selected_calls["offsets"], 2)
        self.assertTrue(os.path.exists(output_midi))
