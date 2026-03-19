import json
import os

import pandas as pd
import wave
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.uploads import process_cough_upload, save_template_audio


@csrf_exempt
def modify_clusterID(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        metadata_dict = json.loads(request.body)
        user_id = metadata_dict.get("userId")
        filename = metadata_dict.get("filename")
        cluster_id = metadata_dict.get("clusterID")

        if not user_id or not filename or cluster_id is None:
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
        if not os.path.exists(cough_table_path):
            return JsonResponse({"error": "Cough table does not exist"}, status=404)

        df = pd.read_csv(cough_table_path)
        df.loc[df["time"] == filename, "clusterID"] = cluster_id
        df.to_csv(cough_table_path, index=False)
        return JsonResponse({"message": "Cluster ID updated successfully"}, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def set_template(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata = request.POST.get("metadata")
        metadata_dict = json.loads(metadata)
        audio_file = request.FILES.get("file")
        audio_data = audio_file.read()
        payload = save_template_audio(metadata_dict, audio_data)
        return JsonResponse(payload, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def create_cough_audio(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata = request.POST.get("metadata")
        metadata_dict = json.loads(metadata)
        audio_file = request.FILES.get("file")
        audio_data = audio_file.read()
        payload = process_cough_upload(metadata_dict, audio_data)
        return JsonResponse(payload, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def get_coughs(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        audio_records = []
        metadata_dict = json.loads(request.body)
        user_id = metadata_dict.get("userId")
        upload_folder = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio")
        cough_table_path = os.path.join(upload_folder, "cough_table.csv")
        df = pd.read_csv(cough_table_path) if os.path.exists(cough_table_path) else None

        for filename in os.listdir(upload_folder):
            if not filename.endswith(".wav"):
                continue

            file_path = os.path.join(upload_folder, filename)
            timestamp = os.path.getmtime(file_path)
            formatted_timestamp = pd.Timestamp.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            with wave.open(file_path, "r") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration_seconds = frames / float(rate)
                minutes, seconds = divmod(round(duration_seconds), 60)
                duration = f"{minutes:02}:{seconds:02}"

            cluster_id = None
            people = None
            if df is not None:
                match = df[df["filename"] == filename]
                if not match.empty:
                    cluster_id = str(int(match.iloc[0]["clusterID"]))
                    people = match.iloc[0].get("people", None)

            if people is False:
                audio_records.append(
                    {
                        "filename": filename.replace(".wav", ""),
                        "filePath": file_path,
                        "timestamp": formatted_timestamp,
                        "duration": duration,
                        "clusterID": cluster_id,
                    }
                )

        return JsonResponse(audio_records, safe=False, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=500)


__all__ = [
    "create_cough_audio",
    "get_coughs",
    "modify_clusterID",
    "set_template",
]
