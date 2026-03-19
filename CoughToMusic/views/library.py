def _legacy():
    from .. import views_legacy

    return views_legacy


def get_music(request):
    return _legacy().get_music(request)


def get_uploads_file(request, filename):
    return _legacy().get_uploads_file(request, filename)


def get_cough_info(request):
    return _legacy().get_cough_info(request)


def set_cough_info(request):
    return _legacy().set_cough_info(request)


def get_music_info(request):
    return _legacy().get_music_info(request)


def set_music_info(request):
    return _legacy().set_music_info(request)


def get_cough_statistics(request):
    return _legacy().get_cough_statistics(request)


def get_music_statistics(request):
    return _legacy().get_music_statistics(request)


def upload_to_public_cough(request):
    return _legacy().upload_to_public_cough(request)


def upload_to_public_music(request):
    return _legacy().upload_to_public_music(request)


def delete_music(request):
    return _legacy().delete_music(request)


def rename_music(request):
    return _legacy().rename_music(request)


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
