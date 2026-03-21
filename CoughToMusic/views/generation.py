import json
import os
import shutil

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.generation import (
    enqueue_generation_request,
    get_generation_status_payload,
    save_cocreate_result,
    save_music_result,
)


@csrf_exempt
def save_music(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        save_music_result(
            user_id=metadata_dict.get("userId"),
            job_uuid=metadata_dict.get("uuid"),
            file_name=metadata_dict.get("fileName"),
            output_type=metadata_dict.get("type"),
        )
        return JsonResponse({"message": "Save music successfully."}, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def save_music_cocreate(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        save_cocreate_result(
            user_id=metadata_dict.get("userId"),
            job_uuid=metadata_dict.get("uuid"),
            file_name=metadata_dict.get("fileName"),
        )
        return JsonResponse({"message": "Save music successfully."}, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def clean_temper(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        user_id = metadata_dict.get("userId")
        user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
        temp_music_folder = os.path.join(user_folder, "temp_music")
        temp_midi_folder = os.path.join(user_folder, "temp_midi")
        if os.path.exists(temp_music_folder):
            shutil.rmtree(temp_music_folder)
        if os.path.exists(temp_midi_folder):
            shutil.rmtree(temp_midi_folder)
        return JsonResponse({"message": "Save music successfully."}, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def generate(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body.decode("utf-8"))
        job_uuid = enqueue_generation_request(data)
        return JsonResponse({"status": "queued", "uuid": job_uuid}, status=202)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        print("[generate] Error:", exc)
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def generate_status_view(request):
    try:
        payload, status_code = get_generation_status_payload(request.body)
        print("@@@@@@@@@@@ GOOOD @@@@@@@@@@@") 
        return JsonResponse(payload, safe=not isinstance(payload, list), status=status_code)
    except json.JSONDecodeError:
        print("@@@@@@@@@@@ BAD JSON @@@@@@@@@@@") 
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as exc:
        print("[generate_status_view] Error:", exc)
        return JsonResponse({"error": str(exc)}, status=500)


__all__ = [
    "clean_temper",
    "generate",
    "generate_status_view",
    "save_music",
    "save_music_cocreate",
]
