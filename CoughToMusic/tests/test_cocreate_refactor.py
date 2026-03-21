import csv
import sys
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

        request = CoCreateRequest(
            mode="drum",
            user_id="refactor-user",
            job_uuid="drum-uuid",
            coughlist=[Path(self._temp_media_path) / "refactor-user" / "cough_audio" / "listed.wav"],
        )

        with patch("CoughToMusic.cocreate.drum_workflows.ensure_temp_folder", return_value="temp_drum"), patch(
            "CoughToMusic.cocreate.drum_workflows.generate_autofill_drum",
            return_value=("generated.wav", ["public.wav"], ["motif0.wav", "motif1.wav"]),
        ):
            result = drum_workflows.run_drum_autofill(request)

        payload = result.to_payload()
        self.assertEqual(payload["generated_music"], "generated.wav")
        self.assertEqual(payload["cough_motifs"], ["motif0.wav"])
        self.assertEqual(payload["used_public_paths"], ["public.wav"])
        self.assertEqual(payload["used_motif_paths"], ["motif1.wav"])

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
