import datetime
import json
import os

import pandas as pd
import soundfile as sf
from django.conf import settings

from ..table import update_cough_table
from ..util import (
    classify_cough_event,
    clustering,
    filter_coughs,
    filter_coughs_template,
    save_pcm16_to_wav,
)


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
    filter_coughs(file_path)

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
        pub_cough_id = _save_public_cough_copy(audio_data, sample_rate)

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


def _save_public_cough_copy(audio_data, sample_rate):
    folder_path_public = os.path.join(settings.MEDIA_ROOT, "public_cough")
    existing_files = os.listdir(folder_path_public)
    pub_cough_id = str(len(existing_files) + 1)
    file_path_public = os.path.join(folder_path_public, f"{pub_cough_id}.wav")
    save_pcm16_to_wav(file_path_public, audio_data, sample_rate)
    filter_coughs(file_path_public)
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
    sf.write(user_filename, classification_result["user_output"], classification_result["sample_rate"])
    sf.write(non_user_filename, classification_result["non_user_output"], classification_result["sample_rate"])

    folder_path_public = os.path.join(settings.MEDIA_ROOT, "public_cough")
    first_public_id = str(len(os.listdir(folder_path_public)) + 1)
    update_cough_table(
        user_id,
        {
            "filename": filename.replace(".wav", "") + "_1.wav",
            "timestamp": time_stamp,
            "pubCoughID": first_public_id,
            "time": time_value,
            "latitude": latitude,
            "longitude": longitude,
            "clusterID": 0,
            "people": False,
        },
    )
    sf.write(
        os.path.join(folder_path_public, f"{first_public_id}.wav"),
        classification_result["user_output"],
        classification_result["sample_rate"],
    )

    second_public_id = str(len(os.listdir(folder_path_public)) + 1)
    update_cough_table(
        user_id,
        {
            "filename": filename.replace(".wav", "") + "_2.wav",
            "timestamp": time_stamp,
            "pubCoughID": second_public_id,
            "time": time_value,
            "latitude": latitude,
            "longitude": longitude,
            "clusterID": 1,
            "people": False,
        },
    )
    sf.write(
        os.path.join(folder_path_public, f"{second_public_id}.wav"),
        classification_result["non_user_output"],
        classification_result["sample_rate"],
    )


def _build_wav_name(stem):
    filename = os.path.join("", f"{stem}.wav")
    if not isinstance(filename, str):
        raise ValueError("Invalid filename format")
    return filename
