import os
import pandas as pd
from django.conf import settings
import os
from .util import generate_music, save_music_move
from .co_create_utils import gen_trio_mid, cough2midi, gen_trio_trk, generate_groove_intp_autofill, cough2mid_manual, gen_trio_manual,gen_trio_trk_manual,  generate_groove_intp_manual
from django.conf import settings
import pandas as pd
import time
from pathlib import Path

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
        self.coughlist = coughlist

        # cough_path = data.get('cough_path', None) + ".wav"
        # self.file_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', cough_path)
        self.file_path = str(coughlist[0]) if coughlist else None
        print(f'self_file_path: {self.file_path}')


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
                    self.file_path,
                    self.uuid,
                    self.data['bass'].lower(),
                    self.data['alto'].lower(),
                    self.data['high'].lower()
                )

                self.result = {'generate_path': generate_path, 'cough_paths':  [str(p) for p in self.coughlist]}

            elif self.mode == 'trio':
                print("----------trio mode----------")
                user_id = self.data['user_id']
                print(self.coughlist[0])
                cough_path = str(self.coughlist[0])
                print(f"cough_path: {cough_path}")
                print(f"----------cough_path_trio_1: {cough_path}")
                uuid = self.uuid
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_trio')
                os.makedirs(user_tmp_folder, exist_ok=True)
                
                cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
                df = pd.read_csv(cough_table_path)
                match = df[df['time'] == time_value]
                pubCoughID = int(match.iloc[0]['pubCoughID'])
                generate_path_triomotif = cough2midi(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)
                print('----generrate_trio_mid----')
                used_cough_paths = gen_trio_mid(pubCoughID)  
                print('----generrate_trio_trk----')
                generate_path_trio = gen_trio_trk(pubCoughID, 'string', user_tmp_folder, uuid, sample_rate=16000)


                self.result = {
                    'cough_paths':  [str(p) for p in self.coughlist],
                    'used_public_paths': [str(p) for p in used_cough_paths],
                    'generated_music': generate_path_trio
                }
                print(self.result)

            elif self.mode == 'trio_manual':
                user_id = self.data['user_id']
                uuid = self.uuid
                # time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_manual_trio')
                os.makedirs(user_tmp_folder, exist_ok=True)
                # final_manual_dir = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_manual_trio')
                # os.makedirs(final_manual_dir, exist_ok=True)
                mid_dic = {'mel':[], 'acc':[], 'bass':[]}
                for cough_pth in self.coughlist:
                    cough2mid_manual(cough_pth, user_tmp_folder, mid_dic)
                
                gen_trio_manual(user_tmp_folder, mid_dic, uuid)
                generated_manual_trio = gen_trio_trk_manual(user_tmp_folder,uuid, sample_rate=16000)

                self.result = {
                    'cough_paths': [str(p) for p in self.coughlist],
                    'generated_music': generated_manual_trio
                }
                print(self.result)
            # elif self.mode == 'drum':
            #     user_id = self.data['user_id']
            #     cough_path = str(self.coughlist[0])
            #     uuid = self.uuid
            #     time_value = os.path.splitext(os.path.basename(cough_path))[0]
            #     user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_drum')
            #     os.makedirs(user_tmp_folder, exist_ok=True)

            #     cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
            #     df = pd.read_csv(cough_table_path)
            #     match = df[df['time'] == time_value]
            #     pubCoughID = int(match.iloc[0]['pubCoughID'])

            #     generate_path_drum, used_cough_paths = generate_groove_intp(
            #         settings.PUBLIC_COUGH, pubCoughID, user_tmp_folder, uuid)
            #     self.result = {
            #         'cough_path':  [str(p) for p in self.coughlist],
            #         'used_public_paths': [str(p) for p in used_cough_paths],
            #         'generate_path_drum': generate_path_drum
            #     }
            elif self.mode == 'drum_manual':
                user_id = self.data['user_id']
                cough_path = self.data['cough_path']
                uuid = self.uuid
                time_value = os.path.splitext(os.path.basename(cough_path))[0]
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_manual_drum')
                os.makedirs(user_tmp_folder, exist_ok=True)
                # final_manual_dir = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_manual_drum')
                # os.makedirs(final_manual_dir, exist_ok=True)
                generated_manual_drum = generate_groove_intp_manual(self.coughlist, user_tmp_folder, uuid)
                print(self.result)
                self.result = {
                    'cough_paths': [str(p) for p in self.coughlist],
                    'generated_music': generated_manual_drum
                }
                print(self.result)

            elif self.mode == 'drum':
                user_id = self.data['user_id']
                uuid = self.uuid
                user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_autofill_drum')
                os.makedirs(user_tmp_folder, exist_ok=True)
                public_base = os.path.abspath(settings.PUBLIC_COUGH)
                try:
                    generate_path_drum, used_public_paths = generate_groove_intp_autofill(
                        self.coughlist,
                        settings.PUBLIC_COUGH,
                        user_tmp_folder,
                        uuid
                    )

                    self.result = {
                        'cough_paths': [str(p) for p in self.coughlist],
                        'used_public_paths':[
                            str(p) for p in used_public_paths
                            if os.path.abspath(p).startswith(public_base)
                        ],
                        'generated_music': generate_path_drum,
                    }
                    print(self.result)
                except Exception as e:
                    self.result = {'error': str(e)}

            else:
                raise ValueError(f"Unsupported mode: {self.mode}")          
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


#test用的



# # 模擬使用者 ID 和 cough input 路徑
# user_id = 'jag22325477@gapp.nthu.edu.tw'
# test_uuid = "gg"
# # 假設你有兩段使用者上傳的咳嗽
# user_cough_paths = [
#     # os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', '2025-07-02-23-50-22.wav'),
#     os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', '2025-07-02-23-50-38.wav')
# ]
# data = {
#     'user_id': user_id
# }
# Mode = 'drum'  # 可以是 'normal', 'trio', 'drum', 'trio_manual', 'drum_manual', 'drum_autofill'
# # 建立一個 autofill job
# job = GenerateJob(
#     mode=Mode,
#     data=data,
#     uuid=test_uuid,
#     user_id=user_id,
#     coughlist=user_cough_paths,
# )
# print(f"🛠 測試開始 UUID: {test_uuid}")
# job.run()
# print(f"✅ 狀態: {job.status}")
# print(f"⏱ 執行時間: {job.duration} 秒")
# print(f"📦 回傳資料:\n{job.result}")

# save_music_move(user_id, test_uuid, "gg",Mode)