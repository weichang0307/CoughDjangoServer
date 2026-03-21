import os
import json
import datetime

import pandas as pd
from django.conf import settings

from ..table import init_cough_table, init_music_table, init_user_table, update_user_table
from ..util import init_user_folder

USER_TABLE_COLUMNS = [
    "isSignUp",
    "name",
    "age",
    "gender",
    "education",
    "musicProficiency",
    "isCoughPublish",
    "userEmail",
    "bestSong1",
    "bestSong2",
    "bestSong3",
    "isSmoker",
]
COUGH_TABLE_COLUMNS = ["filename", "timestamp", "pubCoughID", "time", "latitude", "longitude", "clusterID", "people"]
MUSIC_TABLE_COLUMNS = ["filename", "timestamp", "time"]


def sign_up_user(metadata_dict):
    user_id = metadata_dict.get("userId")
    init_user_folder(user_id)
    init_user_table(user_id, USER_TABLE_COLUMNS)
    init_cough_table(user_id, COUGH_TABLE_COLUMNS)
    init_music_table(user_id, MUSIC_TABLE_COLUMNS)

    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    user_table_path = os.path.join(user_folder, f"{user_id}.csv")
    if not os.path.exists(user_table_path):
        raise ValueError(f"User table {user_table_path} does not exist.")

    data_to_update = {key: value for key, value in metadata_dict.items() if key != "userId"}
    data_to_update["isSignUp"] = True
    update_user_table(user_id, data_to_update)
    return {"message": "Audio data received successfully."}


def get_user_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    user_table_path = _get_user_table_path(user_id)
    if not os.path.exists(user_table_path):
        return {"isSignUp": False}

    df = pd.read_csv(user_table_path)
    return df.to_dict(orient="records")[0]


def set_user_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    user_table_path = _get_user_table_path(user_id)
    if not os.path.exists(user_table_path):
        raise ValueError(f"User table {user_table_path} does not exist.")

    data_to_update = {key: value for key, value in metadata_dict.items() if key != "userId"}
    update_user_table(user_id, data_to_update)
    return {"message": "User info updated successfully."}


def set_recording_publish_state(metadata_dict):
    user_id = metadata_dict.get("userId")
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    os.makedirs(user_folder, exist_ok=True)
    user_table_path = _get_user_table_path(user_id)
    df = pd.read_csv(user_table_path)
    df.loc[0, "isCoughPublish"] = metadata_dict.get("isPublish")
    df.to_csv(user_table_path, index=False)
    return {"message": "start audio."}


def stop_record_payload(metadata_dict):
    metadata_dict.get("userId")
    metadata_dict.get("detectTime")
    return {"message": "start audio."}


def refresh_best_song_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    target = metadata_dict.get("target", "")
    user_table_path = _get_user_table_path(user_id)
    if not os.path.exists(user_table_path):
        raise ValueError(f"User table {user_table_path} does not exist.")

    df = pd.read_csv(user_table_path)
    if target == "":
        return {
            "bestSong1": df.loc[0, "bestSong1"] if "bestSong1" in df.columns else "",
            "bestSong2": df.loc[0, "bestSong2"] if "bestSong2" in df.columns else "",
            "bestSong3": df.loc[0, "bestSong3"] if "bestSong3" in df.columns else "",
        }

    df.loc[0, "bestSong3"] = df.loc[0, "bestSong2"]
    df.loc[0, "bestSong2"] = df.loc[0, "bestSong1"]
    df.loc[0, "bestSong1"] = target
    df.to_csv(user_table_path, index=False)
    return {
        "bestSong1": df.loc[0, "bestSong1"],
        "bestSong2": df.loc[0, "bestSong2"],
        "bestSong3": df.loc[0, "bestSong3"],
    }


def submit_survey_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    filename = metadata_dict.get("fileName")
    if not user_id or not filename:
        raise ValueError("Missing userId or fileName")

    columns = [
        "timestamp",
        "filename",
        "source_type",
        "source_detail",
        "selected_mode",
        "satisfaction",
        "perception_of_others",
        "thoughts",
        "has_shared",
        "share_details",
        "original_process_mode",
    ]

    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    os.makedirs(user_folder, exist_ok=True)
    survey_table_path = os.path.join(user_folder, "survey_table.csv")

    source_detail = metadata_dict.get("source_detail", "")
    if isinstance(source_detail, (dict, list)):
        source_detail = json.dumps(source_detail, ensure_ascii=False)

    row_data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename,
        "source_type": metadata_dict.get("source_type", ""),
        "source_detail": source_detail,
        "selected_mode": metadata_dict.get("selected_mode", ""),
        "satisfaction": metadata_dict.get("satisfaction", ""),
        "perception_of_others": metadata_dict.get("perception_of_others", ""),
        "thoughts": metadata_dict.get("thoughts", ""),
        "has_shared": metadata_dict.get("has_shared", ""),
        "share_details": metadata_dict.get("share_details", ""),
        "original_process_mode": metadata_dict.get("original_process_mode", ""),
    }

    file_exists = os.path.exists(survey_table_path)
    df = pd.DataFrame([row_data])
    if not file_exists:
        df.to_csv(survey_table_path, index=False, columns=columns)
        return {"message": "Survey submitted successfully."}

    existing_df = pd.read_csv(survey_table_path, nrows=0)
    if "satisfaction" not in existing_df.columns:
        full_old_df = pd.read_csv(survey_table_path)
        full_old_df["satisfaction"] = ""
        full_old_df["perception_of_others"] = ""
        combined_df = pd.concat([full_old_df, df], ignore_index=True)
        combined_df.to_csv(survey_table_path, index=False, columns=columns)
    else:
        df.to_csv(survey_table_path, mode="a", header=False, index=False, columns=columns)
    return {"message": "Survey submitted successfully."}


def _get_user_table_path(user_id):
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    return os.path.join(user_folder, f"{user_id}.csv")
