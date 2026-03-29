import csv
import sys
import types
import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from CoughToMusic.cocreate import storage as cocreate_storage
from CoughToMusic.cocreate.contracts import CoCreateResult

from .support import TempMediaMixin, stub_task_module


class CoCreateRefactorTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(public_cough=True, public_motif=True)

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
        with patch.dict(sys.modules, {"CoughToMusic.task": stub_task_module()}):
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
        with patch.dict(sys.modules, {"CoughToMusic.task": stub_task_module()}):
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

    def test_trio_workflows_delegate_to_trio_adapters(self):
        from CoughToMusic.cocreate import trio_workflows
        from CoughToMusic.cocreate.contracts import CoCreateRequest

        request = CoCreateRequest(
            mode="trio",
            user_id="refactor-user",
            job_uuid="trio-uuid",
            coughlist=[Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "listed.wav"],
        )

        with patch("CoughToMusic.cocreate.trio_workflows.ensure_temp_folder", return_value="temp_trio"), patch(
            "CoughToMusic.cocreate.trio_workflows.resolve_pub_cough_id", return_value=42
        ), patch("CoughToMusic.cocreate.trio_workflows.generate_public_trio_motif", return_value="motif.wav"), patch(
            "CoughToMusic.cocreate.trio_workflows.generate_trio_midi_sequence",
            return_value=(["public.wav"], ["used_motif.wav"]),
        ), patch("CoughToMusic.cocreate.trio_workflows.render_public_trio_tracks", return_value="generated.wav"):
            result = trio_workflows.run_trio(request)

        self.assertEqual(result.to_payload()["generated_music"], "generated.wav")
        self.assertEqual(result.to_payload()["cough_motifs"], ["motif.wav"])
        self.assertEqual(result.to_payload()["used_public_paths"], ["public.wav"])

    def test_drum_workflows_delegate_to_drum_adapters(self):
        from CoughToMusic.cocreate import drum_workflows
        from CoughToMusic.cocreate.contracts import CoCreateRequest
        from CoughToMusic.cocreate.drum_adapters import DrumAutofillResult

        request = CoCreateRequest(
            mode="drum",
            user_id="refactor-user",
            job_uuid="drum-uuid",
            coughlist=[Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "listed.wav"],
        )

        with patch("CoughToMusic.cocreate.drum_workflows.ensure_temp_folder", return_value="temp_drum"), patch(
            "CoughToMusic.cocreate.drum_workflows.generate_autofill_drum",
            return_value=DrumAutofillResult(
                generated_music="generated.wav",
                used_public_paths=[
                    "public-1.wav",
                    "public-2.wav",
                    "public-3.wav",
                    "public-4.wav",
                    "public-5.wav",
                    "public-6.wav",
                ],
                motif_paths=[
                    "motif0.wav",
                    "motif1.wav",
                    "motif2.wav",
                    "motif3.wav",
                    "motif4.wav",
                    "motif5.wav",
                    "motif6.wav",
                ],
            ),
        ):
            result = drum_workflows.run_drum_autofill(request)

        payload = result.to_payload()
        self.assertEqual(payload["generated_music"], "generated.wav")
        self.assertEqual(payload["cough_motifs"], ["motif0.wav"])
        self.assertEqual(
            payload["used_public_paths"],
            [
                "public-1.wav",
                "public-2.wav",
                "public-3.wav",
                "public-4.wav",
                "public-5.wav",
                "public-6.wav",
            ],
        )
        self.assertEqual(
            payload["used_motif_paths"],
            [
                "motif1.wav",
                "motif2.wav",
                "motif3.wav",
                "motif4.wav",
                "motif5.wav",
                "motif6.wav",
            ],
        )

    def test_drum_workflow_rejects_wrong_public_path_count(self):
        from CoughToMusic.cocreate import drum_workflows
        from CoughToMusic.cocreate.contracts import CoCreateRequest
        from CoughToMusic.cocreate.drum_adapters import DrumAutofillResult

        request = CoCreateRequest(
            mode="drum",
            user_id="refactor-user",
            job_uuid="drum-uuid",
            coughlist=[
                Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "cough-1.wav",
                Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "cough-2.wav",
                Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "cough-3.wav",
                Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "cough-4.wav",
            ],
        )

        with patch("CoughToMusic.cocreate.drum_workflows.ensure_temp_folder", return_value="temp_drum"), patch(
            "CoughToMusic.cocreate.drum_workflows.generate_autofill_drum",
            return_value=DrumAutofillResult(
                generated_music="generated.wav",
                used_public_paths=["public-1.wav", "public-2.wav", "public-3.wav", "public-4.wav"],
                motif_paths=["m0.wav", "m1.wav", "m2.wav", "m3.wav", "m4.wav", "m5.wav", "m6.wav"],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "expected 3 public cough paths but got 4"):
                drum_workflows.run_drum_autofill(request)

    def test_generate_autofill_drum_returns_only_sampled_public_paths(self):
        from CoughToMusic.cocreate import drum_adapters
        from CoughToMusic.cocreate.drum_adapters import DrumAutofillResult

        user_coughs = [
            Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "user-1.wav",
            Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "user-2.wav",
            Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "user-3.wav",
            Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "user-4.wav",
        ]
        used_public_paths = ["public-1.wav", "public-2.wav", "public-3.wav"]
        selected_coughs = {
            "kick": "user-1",
            "snare": "user-2",
            "closed_hihat": "user-3",
            "open_hihat": "user-4",
            "mid_tom": "public-1",
            "low_tom": "public-2",
            "crash": "public-3",
        }

        midi_module = types.SimpleNamespace(
            adjust_to_2bars=lambda *args, **kwargs: None,
            write_from_midi=lambda *args, **kwargs: None,
            snap_on_grid_noteseq=lambda *args, **kwargs: None,
            concatenate=lambda *args, **kwargs: None,
        )
        drum_module = types.ModuleType("CoughToMusic.cocreate.lib.drum")
        drum_module.process_autofill_coughs = lambda *args, **kwargs: (
            selected_coughs,
            object(),
            {name: f"path-for-{name}.wav" for name in selected_coughs.values()},
            used_public_paths,
        )
        drum_module.write_midi_pretty_manual = lambda *args, **kwargs: None
        generation_module = types.ModuleType("CoughToMusic.cocreate.lib.generation")
        generation_module.concatenate_sequences = lambda *args, **kwargs: None
        generation_module.concate_interpolation = lambda *args, **kwargs: None
        generation_module.interpolated_groove = lambda *args, **kwargs: "interp.mid"
        generation_module.path_to_note_seq = lambda *args, **kwargs: ("start", "end")
        lib_module = types.ModuleType("CoughToMusic.cocreate.lib")
        lib_module.midi = midi_module

        with patch.dict(
            sys.modules,
            {
                "CoughToMusic.cocreate.lib": lib_module,
                "CoughToMusic.cocreate.lib.drum": drum_module,
                "CoughToMusic.cocreate.lib.generation": generation_module,
            },
        ):
            result = drum_adapters.generate_autofill_drum(user_coughs, "temp_drum", "job-1")

        self.assertIsInstance(result, DrumAutofillResult)
        self.assertEqual(result.used_public_paths, used_public_paths)
        self.assertEqual(result.generated_music, str(Path("temp_drum") / "job-1_drum.wav"))

    def test_generate_manual_drum_falls_back_to_cumulative_stage_concatenation(self):
        from CoughToMusic.cocreate import drum_adapters

        cough_paths = [Path(f"cough-{index}.wav") for index in range(7)]
        Path("temp_drum").mkdir(parents=True, exist_ok=True)
        selected_coughs = {
            "kick": "cough-0",
            "snare": "cough-1",
            "closed_hihat": "cough-2",
            "open_hihat": "cough-3",
            "mid_tom": "cough-4",
            "low_tom": "cough-5",
            "crash": "cough-6",
        }
        midi_calls = {"render": None}
        fallback_calls = {}

        def fake_write_midi_pretty_manual(selected_subset, df, cough_path_list, output_midi):
            Path(output_midi).write_bytes(b"mid")

        def fake_adjust_to_2bars(source, dest):
            Path(dest).write_bytes(b"mid")

        def fake_snap_on_grid_noteseq(source, dest, quantization_level):
            Path(dest).write_bytes(b"mid")

        def fake_concatenate(midi_files, output_file_path, sec=4.0):
            Path(output_file_path).write_bytes(b"mid")

        def fake_write_from_midi(midi_file, output_file, sf="drum"):
            midi_calls["render"] = midi_file

        def fake_interpolated_groove(*args, **kwargs):
            raise ValueError("cannot tensorize")

        def fake_fallback(stage_paths, output_path):
            fallback_calls["stage_paths"] = list(stage_paths)
            fallback_calls["output_path"] = output_path
            Path(output_path).write_bytes(b"mid")
            return output_path

        midi_module = types.SimpleNamespace(
            adjust_to_2bars=fake_adjust_to_2bars,
            write_from_midi=fake_write_from_midi,
            snap_on_grid_noteseq=fake_snap_on_grid_noteseq,
            concatenate=fake_concatenate,
        )
        drum_module = types.ModuleType("CoughToMusic.cocreate.lib.drum")
        drum_module.process_manual_coughs = lambda *args, **kwargs: (selected_coughs, object())
        drum_module.write_midi_pretty_manual = fake_write_midi_pretty_manual
        generation_module = types.ModuleType("CoughToMusic.cocreate.lib.generation")
        generation_module.concatenate_sequences = lambda *args, **kwargs: None
        generation_module.concate_interpolation = lambda *args, **kwargs: None
        generation_module.interpolated_groove = fake_interpolated_groove
        generation_module.path_to_note_seq = lambda *args, **kwargs: ("start", "end")
        lib_module = types.ModuleType("CoughToMusic.cocreate.lib")
        lib_module.midi = midi_module

        with patch.object(
            drum_adapters,
            "_concatenate_drum_stage_midis",
            side_effect=fake_fallback,
        ), patch.dict(
            sys.modules,
            {
                "CoughToMusic.cocreate.lib": lib_module,
                "CoughToMusic.cocreate.lib.drum": drum_module,
                "CoughToMusic.cocreate.lib.generation": generation_module,
            },
        ):
            generated_music, motif_paths = drum_adapters.generate_manual_drum(cough_paths, "temp_drum", "job-1")

        self.assertEqual(generated_music, str(Path("temp_drum") / "job-1_drum.wav"))
        self.assertEqual(len(motif_paths), 7)
        self.assertEqual(len(fallback_calls["stage_paths"]), 8)
        self.assertTrue(fallback_calls["stage_paths"][-1].endswith("job-1_fallback_last2.mid"))
        self.assertEqual(midi_calls["render"], str(Path("temp_drum") / "job-1_fallback_concat.mid"))

    def test_write_from_midi_raises_when_fluidsynth_produces_no_output(self):
        from CoughToMusic.cocreate.lib import midi as midi_lib

        fake_root = Path(self._temp_media_path) / "render-root"
        soundfont_path = fake_root / "CoughToMusic" / "cocreate" / "soundfonts" / "alex_gm.sf2"
        fluidsynth_path = fake_root / "Library" / "bin" / "fluidsynth.exe"
        midi_path = fake_root / "input.mid"
        output_path = fake_root / "output.wav"
        soundfont_path.parent.mkdir(parents=True, exist_ok=True)
        fluidsynth_path.parent.mkdir(parents=True, exist_ok=True)
        midi_path.parent.mkdir(parents=True, exist_ok=True)
        soundfont_path.write_bytes(b"sf2")
        fluidsynth_path.write_bytes(b"exe")
        midi_path.write_bytes(b"mid")

        def fake_run(*args, **kwargs):
            return types.SimpleNamespace(returncode=0, stderr="")

        with patch.dict(os.environ, {"CONDA_PREFIX": str(fake_root)}), patch(
            "CoughToMusic.cocreate.lib.midi.os.getcwd", return_value=str(fake_root)
        ), patch("CoughToMusic.cocreate.lib.midi.shutil.which", return_value=None), patch(
            "CoughToMusic.cocreate.lib.midi.subprocess.run", side_effect=fake_run
        ), patch(
            "CoughToMusic.cocreate.lib.midi.audio.gain_db_from_wav"
        ) as gain_mock:
            with self.assertRaisesRegex(RuntimeError, "did not produce output WAV"):
                midi_lib.write_from_midi(str(midi_path), str(output_path), "drum")

        gain_mock.assert_not_called()

    def test_write_from_midi_honors_valid_render_output(self):
        from CoughToMusic.cocreate.lib import midi as midi_lib

        fake_root = Path(self._temp_media_path) / "render-root-ok"
        soundfont_path = fake_root / "CoughToMusic" / "cocreate" / "soundfonts" / "alex_gm.sf2"
        fluidsynth_path = fake_root / "Library" / "bin" / "fluidsynth.exe"
        midi_path = fake_root / "input.mid"
        output_path = fake_root / "output.wav"
        soundfont_path.parent.mkdir(parents=True, exist_ok=True)
        fluidsynth_path.parent.mkdir(parents=True, exist_ok=True)
        midi_path.parent.mkdir(parents=True, exist_ok=True)
        soundfont_path.write_bytes(b"sf2")
        fluidsynth_path.write_bytes(b"exe")
        midi_path.write_bytes(b"mid")

        def fake_run(*args, **kwargs):
            output_path.write_bytes(b"wav")
            return types.SimpleNamespace(returncode=0, stderr="")

        with patch.dict(os.environ, {"CONDA_PREFIX": str(fake_root)}), patch(
            "CoughToMusic.cocreate.lib.midi.os.getcwd", return_value=str(fake_root)
        ), patch("CoughToMusic.cocreate.lib.midi.shutil.which", return_value=None), patch(
            "CoughToMusic.cocreate.lib.midi.subprocess.run", side_effect=fake_run
        ), patch(
            "CoughToMusic.cocreate.lib.midi.audio.gain_db_from_wav"
        ) as gain_mock:
            midi_lib.write_from_midi(str(midi_path), str(output_path), "drum")

        gain_mock.assert_called_once_with(str(output_path), 5)
        self.assert_file_exists(str(output_path))

    def test_cocreate_package_exports_contracts_only(self):
        from CoughToMusic import cocreate

        self.assertEqual(cocreate.__all__, ["CoCreateRequest", "CoCreateResult"])
        self.assertTrue(hasattr(cocreate, "CoCreateRequest"))
        self.assertTrue(hasattr(cocreate, "CoCreateResult"))
        self.assertFalse(hasattr(cocreate, "run_trio"))
        self.assertFalse(hasattr(cocreate, "run_drum_manual"))

    def test_cocreate_result_payload_preserves_contract(self):
        result = CoCreateResult(
            generated_music="generated.wav",
            cough_paths=["cough-a.wav", "cough-b.wav"],
            cough_motifs=["motif-a.wav"],
            used_public_paths=["public-a.wav"],
            used_motif_paths=["used-motif-a.wav"],
            extra={"mode": "trio"},
        )

        self.assertEqual(
            result.to_payload(),
            {
                "generated_music": "generated.wav",
                "cough_paths": ["cough-a.wav", "cough-b.wav"],
                "cough_motifs": ["motif-a.wav"],
                "used_public_paths": ["public-a.wav"],
                "used_motif_paths": ["used-motif-a.wav"],
                "mode": "trio",
            },
        )

    def test_cocreate_result_payload_omits_empty_optional_fields(self):
        result = CoCreateResult(generated_music="generated.wav", cough_paths=["cough-a.wav"])

        self.assertEqual(
            result.to_payload(),
            {
                "generated_music": "generated.wav",
                "cough_paths": ["cough-a.wav"],
            },
        )

    def test_cocreate_result_normalizes_path_objects(self):
        result = CoCreateResult(
            generated_music=Path("generated.wav"),
            cough_paths=[Path("cough-a.wav")],
            cough_motifs=[Path("motif-a.wav")],
        )

        self.assertEqual(
            result.to_payload(),
            {
                "generated_music": "generated.wav",
                "cough_paths": ["cough-a.wav"],
                "cough_motifs": ["motif-a.wav"],
            },
        )

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

    def test_save_music_move_accepts_legacy_drum_autofill_type(self):
        from CoughToMusic.util import save_music_move

        user_id = "refactor-user"
        temp_folder = Path(self._temp_media_path) / user_id / "temp_autofill_drum"
        temp_folder.mkdir(parents=True, exist_ok=True)
        source_file = temp_folder / "job-1_drum.wav"
        source_file.write_bytes(b"wave")

        with patch("builtins.print"), patch("CoughToMusic.util.update_music_table"):
            save_music_move(user_id, "job-1", "song", "drum_autofill")

        expected_file = Path(self._temp_media_path) / user_id / "generated_autofill_drum" / "song" / "song_drum.wav"
        self.assertTrue(expected_file.exists(), expected_file)
        self.assertFalse(source_file.exists())
