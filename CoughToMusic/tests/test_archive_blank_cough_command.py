import io
import os
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from .support import COUGH_TABLE_FIELDS, TempMediaMixin


class ArchiveBlankCoughCommandTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(public_cough=True)

    def _cough_table_path(self, user_id):
        return os.path.join(self._temp_media_path, user_id, "cough_audio", "cough_table.csv")

    def _cough_path(self, user_id, filename):
        return os.path.join(self._temp_media_path, user_id, "cough_audio", filename)

    def _archive_cough_path(self, user_id, filename):
        return os.path.join(self._temp_media_path, user_id, "cough_audio", "archive", filename)

    def _archive_table_path(self, user_id):
        return os.path.join(self._temp_media_path, user_id, "cough_audio", "archive", "cough_table.csv")

    def _public_cough_path(self, pub_cough_id):
        return os.path.join(self._temp_media_path, "public_cough", f"{pub_cough_id}.wav")

    def _archive_public_cough_path(self, pub_cough_id):
        return os.path.join(self._temp_media_path, "archive", "public_cough", f"{pub_cough_id}.wav")

    def test_command_archives_blank_coughs_with_current_helper_behavior(self):
        self.write_wav(self._cough_path("alice", "blank.wav"))
        self.write_wav(self._cough_path("bob", "listed.wav"))
        self.write_wav(self._public_cough_path("2"))
        self.write_csv(
            self._cough_table_path("alice"),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row(filename="blank.wav", pub_cough_id="2")],
        )
        self.write_csv(
            self._cough_table_path("bob"),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row(filename="listed.wav", pub_cough_id="-1")],
        )

        def blank_detector(path):
            return path.endswith("blank.wav")

        stdout = io.StringIO()
        with patch.object(settings, "PUBLIC_COUGH", os.path.join(self._temp_media_path, "public_cough")), patch(
            "CoughToMusic.services.library._is_blank_cough_audio", side_effect=blank_detector
        ):
            call_command("archive_blank_coughs", stdout=stdout)

        output = stdout.getvalue()
        self.assertIn("alice: archived 1", output)
        self.assertIn("bob: archived 0", output)
        self.assertIn("Completed blank cough cleanup for 2 user folders; archived 1 blank coughs.", output)

        self.assertFalse(os.path.exists(self._cough_path("alice", "blank.wav")))
        self.assert_file_exists(self._archive_cough_path("alice", "blank.wav"))
        self.assertFalse(os.path.exists(self._public_cough_path("2")))
        self.assert_file_exists(self._archive_public_cough_path("2"))
        self.assert_csv_has_rows(self._cough_table_path("alice"), [])
        self.assert_csv_has_rows(
            self._archive_table_path("alice"),
            [self.make_cough_row(filename="blank.wav", pub_cough_id="2")],
        )
        self.assert_csv_has_rows(
            self._cough_table_path("bob"),
            [self.make_cough_row(filename="listed.wav", pub_cough_id="-1")],
        )

    def test_command_skips_shared_directories(self):
        for shared_name in ("public_cough", "public_music", "public_motif", "import_cough", "archive"):
            os.makedirs(os.path.join(self._temp_media_path, shared_name), exist_ok=True)

        os.makedirs(os.path.join(self._temp_media_path, "alice", "cough_audio"), exist_ok=True)
        self.write_csv(
            self._cough_table_path("alice"),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row(filename="blank.wav", pub_cough_id="-1")],
        )

        calls = []

        def helper(user_id):
            calls.append(user_id)
            return {"archivedCount": 0, "results": []}

        stdout = io.StringIO()
        with patch(
            "CoughToMusic.management.commands.archive_blank_coughs.Command._archive_user_coughs",
            side_effect=helper,
        ):
            call_command("archive_blank_coughs", stdout=stdout)

        self.assertEqual(calls, ["alice"])
        self.assertIn("alice: archived 0", stdout.getvalue())

    def test_command_continues_when_one_user_cleanup_fails(self):
        os.makedirs(os.path.join(self._temp_media_path, "alice", "cough_audio"), exist_ok=True)
        os.makedirs(os.path.join(self._temp_media_path, "bob", "cough_audio"), exist_ok=True)

        def helper(user_id):
            if user_id == "alice":
                raise ValueError("missing public cough")
            return {"archivedCount": 2, "results": []}

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch(
            "CoughToMusic.management.commands.archive_blank_coughs.Command._archive_user_coughs",
            side_effect=helper,
        ):
            call_command("archive_blank_coughs", stdout=stdout, stderr=stderr)

        self.assertIn("alice: error missing public cough", stderr.getvalue())
        self.assertIn("bob: archived 2", stdout.getvalue())
        self.assertIn("Failures: 1.", stdout.getvalue())
        self.assertIn("FAILED alice: missing public cough", stdout.getvalue())

    def test_command_user_filter_limits_processing(self):
        os.makedirs(os.path.join(self._temp_media_path, "alice", "cough_audio"), exist_ok=True)
        os.makedirs(os.path.join(self._temp_media_path, "bob", "cough_audio"), exist_ok=True)

        calls = []

        def helper(user_id):
            calls.append(user_id)
            return {"archivedCount": 0, "results": []}

        with patch(
            "CoughToMusic.management.commands.archive_blank_coughs.Command._archive_user_coughs",
            side_effect=helper,
        ):
            call_command("archive_blank_coughs", "--user", "bob")

        self.assertEqual(calls, ["bob"])
