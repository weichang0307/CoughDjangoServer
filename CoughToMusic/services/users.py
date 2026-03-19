import os

from django.conf import settings

from ..table import init_cough_table, init_music_table, init_user_table, update_user_table
from ..util import init_user_folder

USER_TABLE_COLUMNS = [
    "isSignUp",
    "name",
    "age",
    "gender",
    "education",
    "musicProficiency",
    "isCoughPublish",
    "userEmail",
    "bestSong1",
    "bestSong2",
    "bestSong3",
    "isSmoker",
]
COUGH_TABLE_COLUMNS = ["filename", "timestamp", "pubCoughID", "time", "latitude", "longitude", "clusterID", "people"]
MUSIC_TABLE_COLUMNS = ["filename", "timestamp", "time"]


def sign_up_user(metadata_dict):
    user_id = metadata_dict.get("userId")
    init_user_folder(user_id)
    init_user_table(user_id, USER_TABLE_COLUMNS)
    init_cough_table(user_id, COUGH_TABLE_COLUMNS)
    init_music_table(user_id, MUSIC_TABLE_COLUMNS)

    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    user_table_path = os.path.join(user_folder, f"{user_id}.csv")
    if not os.path.exists(user_table_path):
        raise ValueError(f"User table {user_table_path} does not exist.")

    data_to_update = {key: value for key, value in metadata_dict.items() if key != "userId"}
    data_to_update["isSignUp"] = True
    update_user_table(user_id, data_to_update)
    return {"message": "Audio data received successfully."}
