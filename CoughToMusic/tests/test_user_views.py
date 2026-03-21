import csv
import json
import os

from django.test import TestCase
from django.urls import reverse

from .support import TempMediaMixin


class UserViewsTests(TempMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.create_temp_media_root()
        self.user_id = "migrated-user"
        self.sign_up_user(self.user_id, email="jay@example.com")

    def _user_table_path(self):
        return os.path.join(self._temp_media_path, self.user_id, f"{self.user_id}.csv")

    def test_get_and_set_user_info_round_trip(self):
        get_response = self.client.post(
            reverse("get_user_info"),
            data=json.dumps({"userId": self.user_id}),
            content_type="application/json",
        )
        self.assertEqual(get_response.status_code, 200, get_response.content.decode())
        self.assertEqual(get_response.json()["name"], "Jay")

        set_response = self.client.post(
            reverse("set_user_info"),
            data=json.dumps({"userId": self.user_id, "name": "Robin", "age": 61}),
            content_type="application/json",
        )
        self.assertEqual(set_response.status_code, 200, set_response.content.decode())

        with open(self._user_table_path(), newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["name"], "Robin")
        self.assertEqual(row["age"], "61.0")

    def test_start_stop_record_refresh_best_song_and_submit_survey(self):
        start_response = self.client.post(
            reverse("start_record"),
            data=json.dumps({"userId": self.user_id, "isPublish": True}),
            content_type="application/json",
        )
        self.assertEqual(start_response.status_code, 200, start_response.content.decode())

        with open(self._user_table_path(), newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["isCoughPublish"], "True")

        stop_response = self.client.post(
            reverse("stop_record"),
            data=json.dumps({"userId": self.user_id, "detectTime": "10"}),
            content_type="application/json",
        )
        self.assertEqual(stop_response.status_code, 200, stop_response.content.decode())
        self.assertEqual(stop_response.json()["message"], "start audio.")

        set_best_response = self.client.post(
            reverse("refresh_best_song"),
            data=json.dumps({"userId": self.user_id, "target": "song-a"}),
            content_type="application/json",
        )
        self.assertEqual(set_best_response.status_code, 200, set_best_response.content.decode())
        self.assertEqual(set_best_response.json()["bestSong1"], "song-a")

        get_best_response = self.client.post(
            reverse("refresh_best_song"),
            data=json.dumps({"userId": self.user_id, "target": ""}),
            content_type="application/json",
        )
        self.assertEqual(get_best_response.status_code, 200, get_best_response.content.decode())
        self.assertEqual(get_best_response.json()["bestSong1"], "song-a")

        survey_response = self.client.post(
            reverse("submit_survey"),
            data=json.dumps(self.make_survey_payload(self.user_id)),
            content_type="application/json",
        )
        self.assertEqual(survey_response.status_code, 200, survey_response.content.decode())

        survey_table_path = os.path.join(self._temp_media_path, self.user_id, "survey_table.csv")
        with open(survey_table_path, newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["filename"], "song-a")
        self.assertEqual(row["source_detail"], '{"kind": "normal"}')
        self.assertEqual(row["satisfaction"], "5")
