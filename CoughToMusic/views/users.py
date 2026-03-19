import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from ..services.users import sign_up_user


def _legacy():
    from .. import views_legacy

    return views_legacy


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
    return _legacy().get_user_info(request)


@csrf_exempt
def set_user_info(request):
    return _legacy().set_user_info(request)


@csrf_exempt
def start_record(request):
    return _legacy().start_record(request)


@csrf_exempt
def stop_record(request):
    return _legacy().stop_record(request)


@csrf_exempt
def refresh_best_song(request):
    return _legacy().refresh_best_song(request)


@csrf_exempt
def submit_survey(request):
    return _legacy().submit_survey(request)


__all__ = [
    "get_user_info",
    "refresh_best_song",
    "set_user_info",
    "sign_up",
    "start_record",
    "stop_record",
    "submit_survey",
]
