import json
import os
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
from django.views.decorators.csrf import csrf_exempt
from .util import generate_music, save_pcm16_to_wav, init_user_folder, save_music_move
from .table import update_user_table, init_user_table, init_cough_table, update_cough_table, init_music_table, update_music_table
from .co_create_utils import gen_trio_mid, cough2midi, gen_trio_trk, generate_groove_intp, save_final_cocreate
from django.conf import settings
from django.http import JsonResponse
from django.http import FileResponse, Http404
import shutil
import pandas as pd
import json
import datetime

task_progress = {}

class GenerateJob:
    def __init__(self, mode, data, uuid):
        self.mode = mode
        self.data = data
        self.uuid = uuid

    def run(self):
        try:
            task_progress[self.uuid] = 'processing'
            if self.mode == 'custom':
                generate_path = generate_music(
                    self.data['user_id'],
                    self.data['cough_path'],
                    self.data['uuid'],
                    self.data['bass'].lower(),
                    self.data['alto'].lower(),
                    self.data['high'].lower()
                )
                result = {'generate_path': generate_path, 'cough_path': self.data['cough_path']}

            elif self.mode == 'trio':
                user_id = self.data['userId']
                cough_path = self.data['coughPath']
                uuid = self.data['uuid']
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_cocreate')
                os.makedirs(user_tmp_folder, exist_ok=True)

                cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
                df = pd.read_csv(cough_table_path)
                match = df[df['time'] == time_value]
                pubCoughID = int(match.iloc[0]['pubCoughID'])

                generate_path_triomotif = cough2midi(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)
                gen_trio_mid(pubCoughID)
                generate_path_trio = gen_trio_trk(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)
                result = {
                    'cough_path': cough_path,
                    'generate_path_triomotif': generate_path_triomotif,
                    'generate_path_trio': generate_path_trio
                }

            elif self.mode == 'drum':
                user_id = self.data['userId']
                cough_path = self.data['coughPath']
                uuid = self.data['uuid']
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_cocreate')
                os.makedirs(user_tmp_folder, exist_ok=True)

                cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
                df = pd.read_csv(cough_table_path)
                match = df[df['time'] == time_value]
                pubCoughID = int(match.iloc[0]['pubCoughID'])

                generate_path_drummotif, generate_path_drum = generate_groove_intp(
                    settings.PUBLIC_COUGH, pubCoughID, user_tmp_folder, uuid)
                result = {
                    'cough_path': cough_path,
                    'generate_path_drummotif': generate_path_drummotif,
                    'generate_path_drum': generate_path_drum
                }

            task_progress[self.uuid] = result
        except Exception as e:
            import traceback; traceback.print_exc()
            task_progress[self.uuid] = {'error': str(e)}




