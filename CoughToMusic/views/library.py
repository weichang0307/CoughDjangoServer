import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.library import (
    delete_music_payload,
    get_cough_info_payload,
    get_cough_statistics_payload,
    get_music_info_payload,
    get_music_payload,
    get_music_statistics_payload,
    get_uploads_file_response,
    rename_music_payload,
    set_cough_info_payload,
    set_music_info_payload,
    upload_public_cough_payload,
    upload_public_music_payload,
)


@csrf_exempt
def get_music(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_music_payload(metadata_dict), safe=False, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=500)


def get_uploads_file(request, filename):
    return get_uploads_file_response(request, filename)


@csrf_exempt
def get_cough_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_cough_info_payload(metadata_dict), safe=False, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def set_cough_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(set_cough_info_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def get_music_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_music_info_payload(metadata_dict), safe=False, status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def set_music_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(set_music_info_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def get_cough_statistics(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_cough_statistics_payload(metadata_dict), status=200)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def get_music_statistics(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_music_statistics_payload(metadata_dict), status=200)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def upload_to_public_cough(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata = request.POST.get("metadata")
        metadata_dict = json.loads(metadata)
        audio_data = request.FILES.get("file").read()
        return JsonResponse(upload_public_cough_payload(metadata_dict, audio_data), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def upload_to_public_music(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata = request.POST.get("metadata")
        metadata_dict = json.loads(metadata)
        audio_data = request.FILES.get("file").read()
        return JsonResponse(upload_public_music_payload(metadata_dict, audio_data), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def delete_music(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(delete_music_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def rename_music(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(rename_music_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


__all__ = [
    "delete_music",
    "get_cough_info",
    "get_cough_statistics",
    "get_music",
    "get_music_info",
    "get_music_statistics",
    "get_uploads_file",
    "rename_music",
    "set_cough_info",
    "set_music_info",
    "upload_to_public_cough",
    "upload_to_public_music",
]
