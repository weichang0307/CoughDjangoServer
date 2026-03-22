import datetime
import json
import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from CoughToMusic.services.library import archive_blank_cough_payload

from .support import COUGH_TABLE_FIELDS, MUSIC_STATS_FIELDS, MUSIC_TABLE_FIELDS, TempMediaMixin


class LegacyLibraryCsrfRegressionTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(enforce_csrf=True)
        self.user_id = "csrf-user"

        cough_dir = os.path.join(self._temp_media_path, self.user_id, "cough_audio")
        os.makedirs(cough_dir, exist_ok=True)
        self.write_csv(
            os.path.join(cough_dir, "cough_table.csv"),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row()],
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


class LibraryViewsTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root(import_cough=True, public_music=True)
        self.user_id = "migrated-user"
        self.sign_up_user(self.user_id, email="jay@example.com")

    def _cough_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, "cough_audio", "cough_table.csv")

    def _music_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, "generated_music", "music_table.csv")

    def _cough_archive_folder(self):
        return os.path.join(self._temp_media_path, self.user_id, "cough_audio", "archive")

    def _cough_archive_table_path(self):
        return os.path.join(self._cough_archive_folder(), "cough_table.csv")

    def _archived_cough_path(self, filename):
        return os.path.join(self._cough_archive_folder(), filename)

    def _archived_public_cough_path(self, pub_cough_id):
        return os.path.join(self._temp_media_path, "archive", "public_cough", f"{pub_cough_id}.wav")

    def _public_cough_path(self, pub_cough_id):
        return os.path.join(self._temp_media_path, "public_cough", f"{pub_cough_id}.wav")

    def test_get_music_returns_records_from_all_generated_folders(self):
        cases = [
            ("generated_music", "normal", "normal-song", "normal-song.wav"),
            ("generated_trio", "trio", "trio-song", "trio-song_trio.wav"),
            ("generated_autofill_drum", "drum", "drum-song", "drum-song_drum.wav"),
            ("generated_manual_drum", "drum_manual", "manual-drum", "manual-drum_drum.wav"),
            ("generated_manual_trio", "trio_manual", "manual-trio", "manual-trio_trio.wav"),
        ]
        for folder, _, subdir, filename in cases:
            self.write_wav(os.path.join(self._temp_media_path, self.user_id, folder, subdir, filename))

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
        self.write_csv(
            self._cough_table_path(),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row()],
        )
        self.write_csv(
            self._music_table_path(),
            MUSIC_TABLE_FIELDS,
            [self.make_music_row()],
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
        self.write_csv(
            self._music_table_path(),
            MUSIC_STATS_FIELDS,
            [
                self.make_music_stats_row("song-a", timestamp=now),
                self.make_music_stats_row("song-b", timestamp=now - 3600),
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
        self.write_csv(
            self._cough_table_path(),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row()],
        )

        response = self.client.post(
            reverse("set_cough_info"),
            data=json.dumps({"userId": self.user_id, "filename": "listed.wav", "clusterID": "9", "latitude": "25"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

        rows = self.read_csv_rows(self._cough_table_path())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["clusterID"], "9")
        self.assertEqual(rows[0]["latitude"], "25")

    def test_set_music_info_updates_matching_row_only(self):
        self.write_csv(
            self._music_table_path(),
            MUSIC_TABLE_FIELDS,
            [self.make_music_row()],
        )

        response = self.client.post(
            reverse("set_music_info"),
            data=json.dumps({"userId": self.user_id, "filename": "song", "mood": "bright"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

        rows = self.read_csv_rows(self._music_table_path())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mood"], "bright")

    def test_delete_music_removes_file_and_music_table_row(self):
        target_path = os.path.join(self._temp_media_path, self.user_id, "generated_music", "song-a", "song-a.wav")
        self.write_wav(target_path)
        self.write_csv(
            self._music_table_path(),
            MUSIC_STATS_FIELDS,
            [self.make_music_stats_row("song-a", timestamp="1710986400")],
        )

        response = self.client.post(
            reverse("delete_music"),
            data=json.dumps({"userId": self.user_id, "targetList": [target_path]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertFalse(os.path.exists(target_path))
        self.assert_csv_has_rows(self._music_table_path(), [])

    def test_rename_music_keeps_files_and_music_table_aligned(self):
        wav_path = os.path.join(self._temp_media_path, self.user_id, "generated_music", "song-a", "song-a.wav")
        midi_path = os.path.join(self._temp_media_path, self.user_id, "generated_midi", "song-a", "song-a.mid")
        self.write_wav(wav_path)
        os.makedirs(os.path.dirname(midi_path), exist_ok=True)
        with open(midi_path, "wb") as handle:
            handle.write(b"midi")
        self.write_csv(
            self._music_table_path(),
            MUSIC_STATS_FIELDS,
            [self.make_music_stats_row("song-a", timestamp="1710986400")],
        )

        response = self.client.post(
            reverse("rename_music"),
            data=json.dumps({"userId": self.user_id, "oldName": "song-a", "name": "song-b"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assert_music_assets_aligned(self.user_id, "song-b")
        rows = self.read_csv_rows(self._music_table_path())
        self.assertEqual(rows[0]["filename"], "song-b")

    def test_public_upload_endpoints_write_to_expected_shared_folders(self):
        cough_upload = SimpleUploadedFile("public.wav", self.pcm16_bytes(), content_type="audio/wav")
        cough_response = self.client.post(
            reverse("upload_to_public_cough"),
            data={"metadata": json.dumps({"fileName": "imported"}), "file": cough_upload},
        )
        self.assertEqual(cough_response.status_code, 200, cough_response.content.decode())
        self.assert_file_exists(os.path.join(self.import_cough_folder, "imported.wav"))

        music_upload = SimpleUploadedFile("music.wav", self.pcm16_bytes(), content_type="audio/wav")
        music_response = self.client.post(
            reverse("upload_to_public_music"),
            data={"metadata": json.dumps({"fileName": "public-song"}), "file": music_upload},
        )
        self.assertEqual(music_response.status_code, 200, music_response.content.decode())
        self.assert_file_exists(os.path.join(self.public_music_folder, "public-song.wav"))

    def test_archive_blank_cough_moves_active_files_and_preserves_row_in_archive_csv(self):
        active_cough_path = os.path.join(self._temp_media_path, self.user_id, "cough_audio", "listed.wav")
        public_cough_path = self._public_cough_path("2")
        self.write_wav(active_cough_path)
        self.write_wav(public_cough_path)
        self.write_csv(
            self._cough_table_path(),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row(filename="listed.wav", pub_cough_id="2")],
        )

        with patch.object(settings, "PUBLIC_COUGH", os.path.join(self._temp_media_path, "public_cough")), patch(
            "CoughToMusic.services.library._is_blank_cough_audio",
            return_value=True,
        ):
            response = archive_blank_cough_payload({"userId": self.user_id, "filename": "listed.wav"})

        self.assertTrue(response["archived"])
        self.assertTrue(response["isBlank"])
        self.assertFalse(os.path.exists(active_cough_path))
        self.assertFalse(os.path.exists(public_cough_path))
        self.assert_file_exists(self._archived_cough_path("listed.wav"))
        self.assert_file_exists(self._archived_public_cough_path("2"))
        self.assert_csv_has_rows(self._cough_table_path(), [])
        self.assert_csv_has_rows(
            self._cough_archive_table_path(),
            [self.make_cough_row(filename="listed.wav", pub_cough_id="2")],
        )

    def test_archive_blank_cough_noops_when_audio_is_not_blank(self):
        active_cough_path = os.path.join(self._temp_media_path, self.user_id, "cough_audio", "listed.wav")
        public_cough_path = self._public_cough_path("2")
        self.write_wav(active_cough_path)
        self.write_wav(public_cough_path)
        self.write_csv(
            self._cough_table_path(),
            COUGH_TABLE_FIELDS,
            [self.make_cough_row(filename="listed.wav", pub_cough_id="2")],
        )

        with patch.object(settings, "PUBLIC_COUGH", os.path.join(self._temp_media_path, "public_cough")), patch(
            "CoughToMusic.services.library._is_blank_cough_audio",
            return_value=False,
        ):
            response = archive_blank_cough_payload({"userId": self.user_id, "filename": "listed.wav"})

        self.assertFalse(response["archived"])
        self.assertFalse(response["isBlank"])
        self.assert_file_exists(active_cough_path)
        self.assert_file_exists(public_cough_path)
        self.assert_csv_has_rows(
            self._cough_table_path(),
            [self.make_cough_row(filename="listed.wav", pub_cough_id="2")],
        )
        self.assertFalse(os.path.exists(self._cough_archive_table_path()))
