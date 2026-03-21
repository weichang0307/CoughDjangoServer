import csv
import json
import os
import shutil
import types
import uuid
import wave

from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

COUGH_TABLE_FIELDS = [
    "filename",
    "timestamp",
    "pubCoughID",
    "time",
    "latitude",
    "longitude",
    "clusterID",
    "people",
]

MUSIC_TABLE_FIELDS = ["filename", "timestamp", "time", "mood"]
MUSIC_STATS_FIELDS = ["filename", "timestamp", "time"]
PUB_COUGH_FIELDS = ["filename", "pubCoughID"]


def stub_task_module():
    module = types.ModuleType("CoughToMusic.task")
    module.task_progress = {}
    return module


class TempMediaMixin:
    @staticmethod
    def make_sign_up_payload(user_id, *, email="", is_publish=False, overrides=None):
        payload = {
            "userId": user_id,
            "name": "Jay",
            "age": 60,
            "gender": "male",
            "education": "doctorate",
            "musicProficiency": 6,
            "isCoughPublish": is_publish,
            "userEmail": email,
            "bestSong1": "",
            "bestSong2": "",
            "bestSong3": "",
            "isSmoker": "no",
        }
        if overrides:
            payload.update(overrides)
        return payload

    @staticmethod
    def make_cough_row(
        filename="listed.wav",
        *,
        timestamp="2026-03-20 12:00:00",
        pub_cough_id="-1",
        time="listed",
        latitude="0",
        longitude="0",
        cluster_id="1",
        people="False",
        overrides=None,
    ):
        row = {
            "filename": filename,
            "timestamp": timestamp,
            "pubCoughID": pub_cough_id,
            "time": time,
            "latitude": latitude,
            "longitude": longitude,
            "clusterID": cluster_id,
            "people": people,
        }
        if overrides:
            row.update(overrides)
        return row

    @staticmethod
    def make_music_row(filename="song", *, timestamp="1710986400", time=None, mood="calm", overrides=None):
        row = {
            "filename": filename,
            "timestamp": timestamp,
            "time": filename if time is None else time,
            "mood": mood,
        }
        if overrides:
            row.update(overrides)
        return row

    @staticmethod
    def make_music_stats_row(filename, *, timestamp, time=None, overrides=None):
        row = {
            "filename": filename,
            "timestamp": str(timestamp),
            "time": filename if time is None else time,
        }
        if overrides:
            row.update(overrides)
        return row

    @staticmethod
    def make_survey_payload(user_id, *, file_name="song-a", overrides=None):
        payload = {
            "userId": user_id,
            "fileName": file_name,
            "source_type": "generated",
            "source_detail": {"kind": "normal"},
            "selected_mode": "normal",
            "satisfaction": "5",
            "perception_of_others": "4",
            "thoughts": "ok",
        }
        if overrides:
            payload.update(overrides)
        return payload

    def create_temp_media_root(
        self,
        *,
        public_cough=False,
        public_motif=False,
        import_cough=False,
        public_music=False,
        enforce_csrf=False,
    ):
        self._temp_media_path = os.path.join(
            settings.BASE_DIR,
            "media",
            f"test_media_{uuid.uuid4().hex}",
        )
        os.makedirs(self._temp_media_path, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(self._temp_media_path, ignore_errors=True))

        override_kwargs = {"MEDIA_ROOT": self._temp_media_path}

        if public_cough:
            os.makedirs(os.path.join(self._temp_media_path, "public_cough"), exist_ok=True)
        if public_motif:
            os.makedirs(os.path.join(self._temp_media_path, "public_motif", "mel_mid"), exist_ok=True)
        if import_cough:
            self.import_cough_folder = os.path.join(self._temp_media_path, "import_cough")
            os.makedirs(self.import_cough_folder, exist_ok=True)
            override_kwargs["IMPORT_COUGH_FOLDER"] = self.import_cough_folder
        if public_music:
            self.public_music_folder = os.path.join(self._temp_media_path, "public_music")
            os.makedirs(self.public_music_folder, exist_ok=True)
            override_kwargs["PUBLIC_MUSIC"] = self.public_music_folder

        self._override = override_settings(**override_kwargs)
        self._override.enable()
        self.addCleanup(self._override.disable)

        if enforce_csrf:
            self.client = Client(enforce_csrf_checks=True)

    def sign_up_user(self, user_id, *, email="", is_publish=False):
        response = self.client.post(
            reverse("sign_up"),
            data=json.dumps(self.make_sign_up_payload(user_id, email=email, is_publish=is_publish)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())

    @staticmethod
    def pcm16_bytes(sample_count=1600):
        return b"\x00\x00" * sample_count

    def write_wav(self, path, sample_count=1600):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(self.pcm16_bytes(sample_count))

    def write_csv(self, path, fieldnames, rows):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def read_csv_rows(self, path):
        if not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def assert_file_exists(self, path):
        self.assertTrue(os.path.exists(path), path)

    def assert_csv_has_rows(self, path, expected_rows):
        self.assertEqual(self.read_csv_rows(path), expected_rows)

    def assert_music_assets_aligned(self, user_id, expected_name):
        wav_path = os.path.join(
            self._temp_media_path,
            user_id,
            "generated_music",
            expected_name,
            f"{expected_name}.wav",
        )
        midi_path = os.path.join(
            self._temp_media_path,
            user_id,
            "generated_midi",
            expected_name,
            f"{expected_name}.mid",
        )
        self.assert_file_exists(wav_path)
        self.assert_file_exists(midi_path)
