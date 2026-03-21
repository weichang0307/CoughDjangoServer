import os
import subprocess
import sys

from django.conf import settings
from django.test import TestCase


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
        self._assert_module_import_is_lazy("CoughToMusic.util", ["librosa", "soundfile"])

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

    def test_cocreate_package_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_cocreate_trio_workflows_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate.trio_workflows",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_cocreate_drum_workflows_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate.drum_workflows",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_cocreate_trio_adapters_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate.trio_adapters",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_cocreate_drum_adapters_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.cocreate.drum_adapters",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )

    def test_views_import_keeps_heavy_modules_lazy(self):
        self._assert_module_import_is_lazy(
            "CoughToMusic.views",
            ["librosa", "soundfile", "magenta", "note_seq", "pretty_midi", "tensorflow"],
        )
