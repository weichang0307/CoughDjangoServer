import datetime
import os
import shutil
import wave
from wsgiref.util import FileWrapper

import pandas as pd
from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse

from ..table import update_cough_table, update_music_table
from ..util import is_blank, save_pcm16_to_wav

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


def archive_blank_cough_payload(metadata_dict):
    user_id = metadata_dict.get("userId")
    filename = metadata_dict.get("filename") or metadata_dict.get("fileName")
    if not user_id or not filename:
        raise ValueError("Missing userId or filename")

    filename = _build_wav_name(filename)
    cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio")
    cough_path = os.path.join(cough_folder, filename)
    _debug_blank_archive(f"{user_id}/{filename}: starting archive_blank_cough_payload")
    if not os.path.exists(cough_path):
        raise ValueError(f"Cough file {cough_path} does not exist.")

    _debug_blank_archive(f"{user_id}/{filename}: checking blank status")
    if not _is_blank_cough_audio(cough_path):
        _debug_blank_archive(f"{user_id}/{filename}: kept because is_blank returned False")
        return {
            "archived": False,
            "isBlank": False,
            "message": "Cough audio is not blank.",
        }

    cough_table_path = os.path.join(cough_folder, "cough_table.csv")
    if not os.path.exists(cough_table_path):
        raise ValueError(f"Cough table {cough_table_path} does not exist.")

    cough_df = pd.read_csv(cough_table_path)
    if "filename" not in cough_df.columns:
        raise ValueError("Cough table is missing filename column.")

    matching_rows = cough_df[cough_df["filename"].astype(str) == filename]
    if matching_rows.empty:
        raise ValueError(f"No cough row found for {filename}.")

    archived_rows = matching_rows.to_dict(orient="records")
    pub_cough_id = _resolve_pub_cough_id_from_rows(archived_rows)
    public_cough_path = None
    public_archive_path = None
    if pub_cough_id not in (None, "", "-1"):
        public_cough_path = os.path.join(settings.PUBLIC_COUGH, f"{pub_cough_id}.wav")
        _debug_blank_archive(f"{user_id}/{filename}: resolved public cough id {pub_cough_id}")
        if not os.path.exists(public_cough_path):
            raise ValueError(f"Public cough file {public_cough_path} does not exist.")
        public_archive_path = os.path.join(settings.MEDIA_ROOT, "archive", "public_cough", f"{pub_cough_id}.wav")

    archive_folder = os.path.join(cough_folder, "archive")
    os.makedirs(archive_folder, exist_ok=True)
    archive_csv_path = os.path.join(archive_folder, "cough_table.csv")

    if public_cough_path and public_archive_path:
        _debug_blank_archive(f"{user_id}/{filename}: moving public cough to archive")
        _move_file(public_cough_path, public_archive_path)
    _debug_blank_archive(f"{user_id}/{filename}: moving user cough to archive")
    _move_file(cough_path, os.path.join(archive_folder, filename))
    _debug_blank_archive(f"{user_id}/{filename}: appending archive CSV row")
    _write_archive_rows(archive_csv_path, archived_rows)

    cough_df = cough_df[cough_df["filename"].astype(str) != filename]
    cough_df.to_csv(cough_table_path, index=False)
    _debug_blank_archive(f"{user_id}/{filename}: removed active CSV row")

    return {
        "archived": True,
        "isBlank": True,
        "filename": filename,
        "pubCoughID": pub_cough_id,
        "message": "Blank cough archived successfully.",
    }


def archive_blank_coughs_for_user(user_id):
    if not user_id:
        raise ValueError("Missing userId")

    cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio")
    if not os.path.isdir(cough_folder):
        return {"archivedCount": 0, "results": []}

    cough_table_path = os.path.join(cough_folder, "cough_table.csv")
    if not os.path.exists(cough_table_path):
        return {"archivedCount": 0, "results": []}

    cough_df = pd.read_csv(cough_table_path)
    if "filename" not in cough_df.columns:
        return {"archivedCount": 0, "results": []}

    results = []
    filenames = sorted(
        {
            str(filename)
            for filename in cough_df["filename"].dropna().astype(str).tolist()
            if filename.endswith(".wav")
        }
    )
    for filename in filenames:
        result = archive_blank_cough_payload({"userId": user_id, "filename": filename})
        if result.get("archived"):
            results.append(result)
    return {"archivedCount": len(results), "results": results}


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
    if isinstance(stem, str) and stem.endswith(".wav"):
        return stem
    filename = os.path.join("", f"{stem}.wav")
    if not isinstance(filename, str):
        raise ValueError("Invalid filename format")
    return filename


def _is_blank_cough_audio(cough_path):
    return is_blank(cough_path)


def _resolve_pub_cough_id_from_rows(rows):
    for row in rows:
        pub_cough_id = str(row.get("pubCoughID", "")).strip()
        if pub_cough_id and pub_cough_id != "-1" and pub_cough_id.lower() != "nan":
            return pub_cough_id
    if rows:
        pub_cough_id = str(rows[0].get("pubCoughID", "")).strip()
        return "-1" if pub_cough_id.lower() == "nan" else pub_cough_id
    return "-1"


def _write_archive_rows(table_path, rows):
    archive_df = pd.DataFrame(rows)
    if os.path.exists(table_path):
        existing_df = pd.read_csv(table_path)
        for column in archive_df.columns:
            if column not in existing_df.columns:
                existing_df[column] = ""
        for column in existing_df.columns:
            if column not in archive_df.columns:
                archive_df[column] = ""
        archive_df = pd.concat([existing_df, archive_df[existing_df.columns]], ignore_index=True)
    os.makedirs(os.path.dirname(table_path), exist_ok=True)
    archive_df.to_csv(table_path, index=False)


def _move_file(source_path, target_path):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.exists(target_path):
        os.remove(target_path)
    shutil.move(source_path, target_path)


def _debug_blank_archive(message):
    if os.environ.get("COUGHTOMUSIC_BLANK_DEBUG") == "1":
        print(f"[archive_blank_cough] {message}", flush=True)
