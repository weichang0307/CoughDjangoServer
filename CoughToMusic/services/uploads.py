import datetime
import json
import os
import shutil
from threading import Lock

import pandas as pd
import soundfile as sf
from django.conf import settings

from ..table import update_cough_table
from ..util import (
    classify_cough_event,
    clustering,
    filter_coughs_template,
    is_blank,
    save_pcm16_to_wav,
)

_UPLOAD_STATS_LOCK = Lock()
_UPLOAD_STATS = {"total": 0, "blank": 0}


def save_template_audio(metadata, audio_data, sample_rate=16000):
    user_id = metadata.get("userId")
    filename = _build_wav_name(metadata.get("fileName"))
    file_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_template", filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    save_pcm16_to_wav(file_path, audio_data, sample_rate)
    filter_coughs_template(file_path)
    return {"IsSaving": "true"}


def process_cough_upload(metadata, audio_data, sample_rate=16000):
    user_id = metadata.get("userId")
    filename = _build_wav_name(metadata.get("fileName"))
    latitude = metadata.get("latitude")
    longitude = metadata.get("longitude")
    mode = metadata.get("mode")
    time_value = metadata.get("fileName")

    all_cough_file_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio")
    template_path_dir = os.path.join(settings.MEDIA_ROOT, user_id, "cough_template")
    cough_csv_path = os.path.join(all_cough_file_path, "cough_table.csv")
    file_path = os.path.join(all_cough_file_path, filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    save_pcm16_to_wav(file_path, audio_data, sample_rate)
    _record_upload_seen()
    if is_blank(file_path):
        _discard_blank_upload(file_path, user_id, filename)
        return {"IsSaving": "false", "isBlank": True, "message": "Blank cough skipped."}

    user_table_path = os.path.join(settings.MEDIA_ROOT, user_id, f"{user_id}.csv")
    df = pd.read_csv(user_table_path)
    is_cough_pub = df.loc[0, "isCoughPublish"]
    is_cough_pub = True

    classification_result = classify_cough_event(
        cough_wav_path=file_path,
        user_data_path=all_cough_file_path,
        template_data_path=template_path_dir,
        strict_mode=True,
    )
    cluster_id = clustering(file_path, sample_rate, all_cough_file_path, cough_csv_path, template_path_dir)
    time_stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_non_user_cough = classification_result["has_non_user_cough"]
    has_user_cough = classification_result["has_user_cough"]
    pub_cough_id = "-1"

    if is_cough_pub and not (has_non_user_cough and has_user_cough):
        pub_cough_id = _save_public_cough_copy(file_path)

    cough_table_data = {
        "filename": filename,
        "timestamp": time_stamp,
        "pubCoughID": pub_cough_id,
        "time": time_value,
        "latitude": latitude,
        "longitude": longitude,
        "clusterID": cluster_id,
        "people": has_non_user_cough and has_user_cough,
    }
    update_cough_table(user_id, cough_table_data)

    if has_non_user_cough and has_user_cough:
        _save_split_classification_outputs(
            user_id=user_id,
            filename=filename,
            latitude=latitude,
            longitude=longitude,
            time_stamp=time_stamp,
            time_value=time_value,
            all_cough_file_path=all_cough_file_path,
            classification_result=classification_result,
        )

    if mode == "realtime":
        from .generation import enqueue_realtime_generation

        return {"uuid": enqueue_realtime_generation(user_id, file_path)}

    return {"IsSaving": "true", "message": "Audio data received successfully."}


def _save_public_cough_copy(file_path):
    folder_path_public = os.path.join(settings.MEDIA_ROOT, "public_cough")
    pub_cough_id = _next_public_cough_id()
    file_path_public = os.path.join(folder_path_public, f"{pub_cough_id}.wav")
    os.makedirs(folder_path_public, exist_ok=True)
    shutil.copy2(file_path, file_path_public)
    return pub_cough_id


def _save_split_classification_outputs(
    user_id,
    filename,
    latitude,
    longitude,
    time_stamp,
    time_value,
    all_cough_file_path,
    classification_result,
):
    user_filename = os.path.join(all_cough_file_path, filename.replace(".wav", "") + "_1.wav")
    non_user_filename = os.path.join(all_cough_file_path, filename.replace(".wav", "") + "_2.wav")
    _persist_split_cough_output(
        user_id=user_id,
        file_path=user_filename,
        filename=f"{filename.replace('.wav', '')}_1.wav",
        audio_data=classification_result["user_output"],
        sample_rate=classification_result["sample_rate"],
        timestamp=time_stamp,
        time_value=time_value,
        latitude=latitude,
        longitude=longitude,
        cluster_id=0,
    )
    _persist_split_cough_output(
        user_id=user_id,
        file_path=non_user_filename,
        filename=f"{filename.replace('.wav', '')}_2.wav",
        audio_data=classification_result["non_user_output"],
        sample_rate=classification_result["sample_rate"],
        timestamp=time_stamp,
        time_value=time_value,
        latitude=latitude,
        longitude=longitude,
        cluster_id=1,
    )


def _next_public_cough_id():
    candidate_ids = []
    search_roots = [
        os.path.join(settings.MEDIA_ROOT, "public_cough"),
        os.path.join(settings.MEDIA_ROOT, "archive", "public_cough"),
    ]
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for current_root, _, files in os.walk(root):
            for file_name in files:
                stem, ext = os.path.splitext(file_name)
                if ext.lower() != ".wav":
                    continue
                if stem.isdigit():
                    candidate_ids.append(int(stem))
    return str(max(candidate_ids, default=0) + 1)


def _build_wav_name(stem):
    filename = os.path.join("", f"{stem}.wav")
    if not isinstance(filename, str):
        raise ValueError("Invalid filename format")
    return filename


def _record_upload_seen():
    with _UPLOAD_STATS_LOCK:
        _UPLOAD_STATS["total"] += 1


def _record_blank_upload():
    with _UPLOAD_STATS_LOCK:
        _UPLOAD_STATS["blank"] += 1
        return _UPLOAD_STATS["blank"], _UPLOAD_STATS["total"]


def _log_blank_upload(user_id, filename, blank_count, total_count):
    yellow = "\033[93m"
    reset = "\033[0m"
    print(
        f"{yellow}[blank-upload] user={user_id} file={filename} "
        f"blank_count={blank_count} total_uploads={total_count}{reset}"
    )


def _discard_blank_upload(file_path, user_id, filename):
    blank_count, total_count = _record_blank_upload()
    _log_blank_upload(user_id, filename, blank_count, total_count)
    if os.path.exists(file_path):
        os.remove(file_path)


def _persist_split_cough_output(
    *,
    user_id,
    file_path,
    filename,
    audio_data,
    sample_rate,
    timestamp,
    time_value,
    latitude,
    longitude,
    cluster_id,
):
    sf.write(file_path, audio_data, sample_rate)
    if is_blank(file_path):
        _discard_blank_upload(file_path, user_id, filename)
        return False

    public_cough_id = _next_public_cough_id()
    update_cough_table(
        user_id,
        {
            "filename": filename,
            "timestamp": timestamp,
            "pubCoughID": public_cough_id,
            "time": time_value,
            "latitude": latitude,
            "longitude": longitude,
            "clusterID": cluster_id,
            "people": False,
        },
    )
    sf.write(
        os.path.join(settings.MEDIA_ROOT, "public_cough", f"{public_cough_id}.wav"),
        audio_data,
        sample_rate,
    )
    return True
