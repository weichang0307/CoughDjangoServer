import os
import pandas as pd
from django.conf import settings
import os
from .util import generate_music
from .co_create_utils import gen_trio_mid, cough2midi, gen_trio_trk, generate_groove_intp, cough2mid_manual, gen_trio_manual,gen_trio_trk_manual,  generate_groove_intp_manual
from django.conf import settings
import pandas as pd
import time


task_progress = {}

class GenerateJob:
    def __init__(self, mode, data, uuid, user_id, coughlist):
        self.user_id = user_id
        self.mode = mode
        self.data = data
        self.uuid = uuid
        self.type = data.get('type', 'normal')
        self.time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())  # 記錄創建時間
        self.duration = None  # 執行時長
        self.status = 'queued'  # 初始狀態為 queued
        self.result = None  # 儲存結果或錯誤訊息
        self.coughlist = coughlist  # 用於 trio_manual 和 drum_manual 模式

    def run(self):
        try:
            # 更新狀態為 processing
            self.status = 'processing'
            task_progress[self.uuid] = self  # 將整個物件存入 task_progress
            start_time = time.time()  # 記錄開始時間

            # 根據 mode 執行不同的邏輯
            if self.mode == 'normal':
                generate_path = generate_music(
                    self.data['user_id'],
                    self.data['cough_path'],
                    self.data['uuid'],
                    self.data['bass'].lower(),
                    self.data['alto'].lower(),
                    self.data['high'].lower()
                )

                self.result = {'generate_path': generate_path, 'cough_path': self.data['cough_path']}

            elif self.mode == 'trio':
                user_id = self.data['user_id']
                print(f"user_id: {user_id}")
                cough_path = self.data['cough_path']
                print(f"cough_path: {cough_path}")
                uuid = self.data['uuid']
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                print(f"time_value: {time_value}")
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_trio')
                os.makedirs(user_tmp_folder, exist_ok=True)
                
                cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
                print(f"cough_path: {cough_table_path}")
                df = pd.read_csv(cough_table_path)
                match = df[df['time'] == time_value]
                pubCoughID = int(match.iloc[0]['pubCoughID'])
                print(f"pubCoughID: {pubCoughID}")
                print(f'user_tmp_folder: {user_tmp_folder}')
                generate_path_triomotif = cough2midi(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)
                gen_trio_mid(pubCoughID)
                generate_path_trio = gen_trio_trk(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)
                self.result = {
                    # cough path publicID要更新 沒有更新到
                    'cough_path': self.data['cough_path'],
                    'generate_path_triomotif': generate_path_triomotif,
                    'generate_path_trio': generate_path_trio
                }
                print(f'generate_path_triomotif: {generate_path_triomotif}')

            elif self.mode == 'drum':
                user_id = self.data['user_id']
                cough_path = self.data['cough_path']
                uuid = self.data['uuid']
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_drum')
                os.makedirs(user_tmp_folder, exist_ok=True)

                cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
                df = pd.read_csv(cough_table_path)
                match = df[df['time'] == time_value]
                pubCoughID = int(match.iloc[0]['pubCoughID'])

                generate_path_drummotif, generate_path_drum = generate_groove_intp(
                    settings.PUBLIC_COUGH, pubCoughID, user_tmp_folder, uuid)
                self.result = {
                    'cough_path': self.data['cough_path'],
                    'generate_path_drummotif': generate_path_drummotif,
                    'generate_path_drum': generate_path_drum
                }
                print(f'generate_path_drummotif: {generate_path_drummotif}')

            elif self.mode == 'trio_manual':
                user_id = self.data['user_id']
                print(f"user_id: {user_id}")
                uuid = self.data['uuid']
                # time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_manual_trio')
                os.makedirs(user_tmp_folder, exist_ok=True)
                # final_manual_dir = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_manual_trio')
                # os.makedirs(final_manual_dir, exist_ok=True)
                mid_dic = {'mel':[], 'acc':[], 'bass':[]}
                print(f'coughlist: {self.coughlist}')
                for cough_pth in self.coughlist:
                    cough2mid_manual(cough_pth, user_tmp_folder, mid_dic)
                print(f'mid_dic: {mid_dic}')
                
                gen_trio_manual(user_tmp_folder, mid_dic, uuid)
                print("Start gen_trio_trk_manual")
                generated_manual_trio = gen_trio_trk_manual(user_tmp_folder,uuid, sample_rate=16000)

                self.result = {
                    'generated_manual_trio': generated_manual_trio
                }
            elif self.mode == 'drum_manual':
                user_id = self.data['user_id']
                cough_path = self.data['cough_path']
                uuid = self.data['uuid']
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_manual_drum')
                os.makedirs(user_tmp_folder, exist_ok=True)
                # final_manual_dir = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_manual_drum')
                # os.makedirs(final_manual_dir, exist_ok=True)
                generated_manual_drum = generate_groove_intp_manual(self.coughlist, user_tmp_folder, uuid)
                self.result = {
                    'generated_manual_drum': generated_manual_drum
                }
                print(f'generated_manual_drum: {generated_manual_drum}')
            # 計算執行時長並更新狀態
            self.duration = round(time.time() - start_time, 2)
            self.status = 'completed'
                
        except Exception as e:
            # 異常處理
            self.status = 'failed'
            self.result = {'error': str(e)}
        finally:
            # 確保更新 task_progress
            task_progress[self.uuid] = self




