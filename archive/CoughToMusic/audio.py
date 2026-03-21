import os
from django.conf import settings
import pandas as pd
from datetime import datetime
import wave

class Audio:
    def __init__(self, user_id, wav_path ,media_root=settings.MEDIA_ROOT):
        self.user_id = user_id
        self.wave_path = wav_path
        self.media_root = media_root
        self.length_seconds = self._get_audio_duration()
        self.created_datetime = datetime.fromtimestamp(os.path.getmtime(wav_path))
        self.created_date = self.created_datetime.strftime('%Y-%m-%d')
        self.created_time = self.created_datetime.strftime('%H:%M:%S')

    def _get_audio_duration(self):
        with wave.open(self.wave_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return round(frames / float(rate), 2)

    def get_metadata(self):
        return {
            'user_id': self.user_id,
            'length_seconds': self.length_seconds,
            'created_date': self.created_date,
            'created_time': self.created_time
        }

    def get_paths(self):
        return self.wave_path
    

class CoughAudio(Audio):
    def __init__(self, user_id, wav_path, media_root=settings.MEDIA_ROOT):
        super().__init__(user_id, wav_path ,media_root)  # 呼叫父類別的初始化器
        self.pubCoughID = 0


class CocreateDrumAudio(Audio):
    def __init__(self, user_id, wav_path, cough_object, media_root=settings.MEDIA_ROOT):
        super().__init__(user_id, wav_path ,media_root)  # 呼叫父類別的初始化器
        self.cough_object = cough_object
        

class CocreateTrioAudio(Audio):
    def __init__(self, user_id, wav_path, cough_object, media_root=settings.MEDIA_ROOT):
        super().__init__(user_id, wav_path ,media_root)  # 呼叫父類別的初始化器
        self.cough_object = cough_object

class GenerateAudio(Audio):
    def __init__(self, user_id, wav_path, cough_object, media_root=settings.MEDIA_ROOT):
        super().__init__(user_id, wav_path ,media_root)  # 呼叫父類別的初始化器
        self.cough_object = cough_object
""""   
    class Audio:
    def __init__(self, user_id, wav_path ,media_root=settings.MEDIA_ROOT):
        self.user_id = user_id
        self.wave_path = wav_path


        self.media_root = media_root

        self.time_value = os.path.splitext(os.path.basename(cough_path))[0]
        self.user_tmp_folder = os.path.join(media_root, user_id, 'temp_music')
        self.cough_table_path = os.path.join(media_root, user_id, 'cough_audio', 'cough_table.csv')
        self.ensure_temp_folder()

        self.pubCoughID = self._get_pub_cough_id()
        self.length_seconds = self._get_audio_duration()
        self.created_datetime = datetime.fromtimestamp(os.path.getmtime(cough_path))
        self.created_date = self.created_datetime.strftime('%Y-%m-%d')
        self.created_time = self.created_datetime.strftime('%H:%M:%S')

    def ensure_temp_folder(self):
        os.makedirs(self.user_tmp_folder, exist_ok=True)

    def _get_pub_cough_id(self):
        df = pd.read_csv(self.cough_table_path)
        match = df[df['time'] == self.time_value]
        if match.empty:
            raise ValueError(f"No matching cough record found for time: {self.time_value}")
        return int(match.iloc[0]['pubCoughID'])

    def _get_audio_duration(self):
        with wave.open(self.wave_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return round(frames / float(rate), 2)

    def get_metadata(self):
        return {
            'user_id': self.user_id,
            'uuid': self.uuid,
            'cough_path': self.cough_path,
            'pubCoughID': self.pubCoughID,
            'length_seconds': self.length_seconds,
            'created_date': self.created_date,
            'created_time': self.created_time
        }

    def get_paths(self):
        return {
            'user_tmp_folder': self.user_tmp_folder,
            'cough_table_path': self.cough_table_path,
        }"""