import datetime
import os
import wave
from wsgiref.util import FileWrapper

import pandas as pd
from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse

from ..table import update_cough_table, update_music_table
from ..util import save_pcm16_to_wav

MUSIC_FOLDERS = [
    ("generated_music", "normal"),
    ("generated_trio", "trio"),
    ("generated_autofill_drum", "drum"),
    ("generated_manual_drum", "drum_manual"),
    ("generated_manual_trio", "trio_manual"),
]


def get_music_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    audio_records = []
    for folder_name, music_type in MUSIC_FOLDERS:
        upload_folder = os.path.join(settings.MEDIA_ROOT, user_id, folder_name)
        os.makedirs(upload_folder, exist_ok=True)
        audio_records.extend(_collect_music_records(upload_folder, music_type))
    return audio_records


def get_uploads_file_response(request, filename):
    filename = filename.replace("^", "/")
    file_path = filename
    if not os.path.exists(file_path):
        raise Http404("File not found")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("Range", "")
    content_type = "application/octet-stream"
    if range_header:
        try:
            range_val = range_header.strip().split("=")[1]
            byte1, byte2 = range_val.split("-")
            byte1 = int(byte1)
            byte2 = int(byte2) if byte2 else file_size - 1
        except Exception:
            return HttpResponse(status=400)

        length = byte2 - byte1 + 1
        handle = open(file_path, "rb")
        handle.seek(byte1)
        response = StreamingHttpResponse(FileWrapper(handle, blksize=8192), status=206, content_type=content_type)
        response["Content-Length"] = str(length)
        response["Content-Range"] = f"bytes {byte1}-{byte2}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

    handle = open(file_path, "rb")
    response = StreamingHttpResponse(FileWrapper(handle, blksize=8192), content_type=content_type)
    response["Content-Length"] = str(file_size)
    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
    return response


def get_cough_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
    if not os.path.exists(cough_table_path):
        raise ValueError(f"Cough table {cough_table_path} does not exist.")
    return pd.read_csv(cough_table_path).to_dict(orient="records")


def set_cough_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
    if not os.path.exists(cough_table_path):
        raise ValueError(f"Cough table {cough_table_path} does not exist.")

    data_to_update = {key: value for key, value in metadata_dict.items() if key != "userId"}
    if not _update_table_row(
        table_path=cough_table_path,
        match_keys=("filename", "time"),
        row_data=data_to_update,
    ):
        update_cough_table(user_id, data_to_update)
    return {"message": "Cough info updated successfully."}


def get_music_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "generated_music", "music_table.csv")
    if not os.path.exists(music_table_path):
        raise ValueError(f"Music table {music_table_path} does not exist.")
    return pd.read_csv(music_table_path).to_dict(orient="records")


def set_music_info_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "generated_music", "music_table.csv")
    if not os.path.exists(music_table_path):
        raise ValueError(f"Music table {music_table_path} does not exist.")

    data_to_update = {
        key: value for key, value in metadata_dict.items() if key != "userId" and value is not None
    }
    if not _update_table_row(table_path=music_table_path, match_keys=("filename",), row_data=data_to_update):
        update_music_table(user_id, data_to_update)
    return {"message": "Music info updated successfully."}


def get_cough_statistics_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    start_date = metadata_dict.get("startDate")
    end_date = metadata_dict.get("endDate")
    cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
    if not os.path.exists(cough_table_path):
        raise ValueError("Cough CSV file not found.")

    cough_df = pd.read_csv(cough_table_path)
    cough_df["timestamp"] = pd.to_datetime(cough_df["timestamp"])

    now = datetime.datetime.now()
    one_day_ago = now - datetime.timedelta(days=1)
    one_week_ago = now - datetime.timedelta(weeks=1)
    one_month_ago = now - datetime.timedelta(days=30)

    filtered_df = cough_df[
        (cough_df["timestamp"] >= pd.to_datetime(start_date))
        & (cough_df["timestamp"] <= pd.to_datetime(end_date))
    ]
    return {
        "day": str(cough_df[cough_df["timestamp"] >= one_day_ago].shape[0]),
        "week": str(cough_df[cough_df["timestamp"] >= one_week_ago].shape[0]),
        "month": str(cough_df[cough_df["timestamp"] >= one_month_ago].shape[0]),
        "allTime": filtered_df["time"].tolist(),
    }


def get_music_statistics_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "generated_music", "music_table.csv")
    if not os.path.exists(music_table_path):
        raise ValueError("Music CSV file not found.")

    music_df = pd.read_csv(music_table_path)
    music_df["timestamp"] = pd.to_datetime(music_df["timestamp"], unit="s")

    now = datetime.datetime.now()
    one_day_ago = now - datetime.timedelta(days=1)
    one_week_ago = now - datetime.timedelta(weeks=1)
    one_month_ago = now - datetime.timedelta(days=30)
    return {
        "day": str(music_df[music_df["timestamp"] >= one_day_ago].shape[0]),
        "week": str(music_df[music_df["timestamp"] >= one_week_ago].shape[0]),
        "month": str(music_df[music_df["timestamp"] >= one_month_ago].shape[0]),
        "allTime": music_df["time"].tolist(),
    }


def upload_public_cough_payload(metadata_dict, audio_data, sample_rate=16000):
    filename = _build_wav_name(metadata_dict.get("fileName"))
    file_path = os.path.join(settings.IMPORT_COUGH_FOLDER, filename)
    save_pcm16_to_wav(file_path, audio_data, sample_rate)
    return {"message": "Audio data received successfully."}


def upload_public_music_payload(metadata_dict, audio_data, sample_rate=16000):
    filename = _build_wav_name(metadata_dict.get("fileName"))
    file_path = os.path.join(settings.PUBLIC_MUSIC, filename)
    save_pcm16_to_wav(file_path, audio_data, sample_rate)
    return {"message": "Audio data received successfully."}


def delete_music_payload(metadata_dict):
    deleted_music = metadata_dict.get("targetList") or []
    for path in deleted_music:
        if os.path.exists(path):
            os.remove(path)
            _remove_empty_parent_dirs(path)

    user_id = metadata_dict.get("userId")
    if user_id:
        _remove_music_table_rows(user_id, deleted_music)
    return {"message": "start audio."}


def rename_music_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    old_name = metadata_dict.get("oldName")
    new_name = metadata_dict.get("name")
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)

    for folder in (
        os.path.join(user_folder, "generated_music"),
        os.path.join(user_folder, "generated_midi"),
    ):
        if not os.path.exists(folder):
            continue
        for root, _, files in os.walk(folder):
            if os.path.basename(root) != old_name:
                continue
            for file_name in files:
                if old_name not in file_name:
                    continue
                old_file_path = os.path.join(root, file_name)
                new_file_path = os.path.join(root, file_name.replace(old_name, new_name))
                os.rename(old_file_path, new_file_path)

            new_folder_name = root.replace(old_name, new_name)
            if root != new_folder_name:
                os.rename(root, new_folder_name)

    music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "generated_music", "music_table.csv")
    os.makedirs(os.path.dirname(music_table_path), exist_ok=True)
    df = pd.read_csv(music_table_path)
    df.loc[df["filename"] == old_name, "filename"] = new_name
    df.to_csv(music_table_path, index=False)
    return {"message": "start audio."}


def _collect_music_records(upload_folder, music_type):
    audio_records = []
    for root, _, files in os.walk(upload_folder):
        for filename in files:
            if not filename.endswith(".wav"):
                continue
            file_path = os.path.join(root, filename)
            timestamp = os.path.getmtime(file_path)
            formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            with wave.open(file_path, "r") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration_seconds = frames / float(rate)
                minutes, seconds = divmod(round(duration_seconds), 60)
                duration = f"{minutes:02}:{seconds:02}"
            audio_records.append(
                {
                    "filename": filename.replace(".wav", ""),
                    "filePath": file_path,
                    "timestamp": formatted_timestamp,
                    "duration": duration,
                    "type": music_type,
                }
            )
    return audio_records


def _update_table_row(table_path, match_keys, row_data):
    match_key = next((key for key in match_keys if row_data.get(key) not in (None, "")), None)
    if not match_key:
        return False

    df = pd.read_csv(table_path)
    if match_key not in df.columns:
        return False

    row_value = row_data.get(match_key)
    matches = df[match_key].astype(str) == str(row_value)
    if not matches.any():
        return False

    for key, value in row_data.items():
        if key not in df.columns:
            df[key] = ""
        df.loc[matches, key] = value
    df.to_csv(table_path, index=False)
    return True


def _remove_music_table_rows(user_id, deleted_paths):
    music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "generated_music", "music_table.csv")
    if not os.path.exists(music_table_path):
        return

    deleted_names = {os.path.basename(os.path.dirname(path)) for path in deleted_paths if path}
    if not deleted_names:
        return

    df = pd.read_csv(music_table_path)
    if "filename" not in df.columns:
        return
    df = df[~df["filename"].astype(str).isin(deleted_names)]
    df.to_csv(music_table_path, index=False)


def _remove_empty_parent_dirs(path):
    parent = os.path.dirname(path)
    while parent and os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
        parent = os.path.dirname(parent)


def _build_wav_name(stem):
    filename = os.path.join("", f"{stem}.wav")
    if not isinstance(filename, str):
        raise ValueError("Invalid filename format")
    return filename
