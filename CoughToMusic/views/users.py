import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.users import (
    get_user_info_payload,
    refresh_best_song_payload,
    set_recording_publish_state,
    set_user_info_payload,
    sign_up_user,
    stop_record_payload,
    submit_survey_payload,
    delete_account_payload,
)


@csrf_exempt
def sign_up(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(sign_up_user(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def get_user_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(get_user_info_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def set_user_info(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(set_user_info_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def start_record(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(set_recording_publish_state(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def stop_record(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(stop_record_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def refresh_best_song(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(refresh_best_song_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def submit_survey(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(submit_survey_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error in submit_survey: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)
    
@csrf_exempt
def delete_account(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        metadata_dict = json.loads(request.body)
        return JsonResponse(delete_account_payload(metadata_dict), status=200)
    except Exception as exc:
        print("Error in delete_account: ", exc)
        return JsonResponse({"error": str(exc)}, status=400)


__all__ = [
    "get_user_info",
    "refresh_best_song",
    "set_user_info",
    "sign_up",
    "start_record",
    "stop_record",
    "submit_survey",
    "delete_account"
]
