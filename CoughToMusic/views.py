import os
from django.views.decorators.csrf import csrf_exempt
from .util import save_pcm16_to_wav, init_user_folder, save_music_move, save_wav_with_resample, save_pcm16_to_wav, fake_cough_dist, filter_coughs, clustering, classify_cough_event, filter_coughs_template
from .table import update_user_table, init_user_table, init_cough_table, update_cough_table, init_music_table, update_music_table
from .co_create_utils import save_final_cocreate
from .task import GenerateJob, task_progress
from django.conf import settings
from django.http import JsonResponse 
from django.http import Http404
from django.http import HttpResponse
import shutil
import uuid
import pandas as pd
import json
from django.http import StreamingHttpResponse, Http404
from wsgiref.util import FileWrapper
import os
import datetime
from threading import Thread
from queue import Queue
import warnings
import soundfile as sf
warnings.filterwarnings("ignore", category=UserWarning, module="pyloudnorm")
import wave
from pathlib import Path

import pandas as pd

# === 模型與參數 ===


USER_TABLE_COLUMNS = ['isSignUp', 'name', 'age', 'gender', 'education', 'musicProficiency', 'isCoughPublish', 'userEmail','bestSong1','bestSong2','bestSong3','isSmoker']
COUGH_TABLE_COLUMNS = ['filename', 'timestamp', 'pubCoughID', 'time', 'latitude', 'longitude', 'clusterID', 'people']
MUSIC_TABLE_COLUMNS = ['filename', 'timestamp', 'time']


generate_task_queue = Queue()
processing_jobs = []  # 存放處理中的工作
completed_jobs = []   # 存放完成的工作

def remove_job_by_uuid(completed_jobs, uuid_to_remove):
    for job in completed_jobs:
        if job.uuid == uuid_to_remove:
            completed_jobs.remove(job)
            break  # 找到並刪除後立即退出迴圈

def generate_worker():
    while True:
        job = generate_task_queue.get()
        print(f"[Worker] Running job {job.uuid} ({job.mode})")

        # 將工作加入處理中的列表
        processing_jobs.append(job)
        job.run()

        # 從處理中的列表移除，並加入完成的列表
        processing_jobs.remove(job)
        completed_jobs.append(job)
        print(f"[Worker] Finished job {job.uuid}")
        generate_task_queue.task_done()

Thread(target=generate_worker, daemon=True).start()

# ✅ Queue monitor: print queue length every 2 seconds
# def monitor_queue(queue):
#     while True:
#         print(f"[Queue Monitor] Current queue size: {queue.qsize()}")
#         time.sleep(2)

# Thread(target=monitor_queue, args=(generate_task_queue,), daemon=True).start()
@csrf_exempt
def modify_clusterID(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            filename = metadata_dict.get('filename')
            clusterID = metadata_dict.get('clusterID')

            # 檢查必要的參數是否存在
            if not userid or not filename or clusterID is None:
                return JsonResponse({'error': 'Missing required parameters'}, status=400)

            # 更新 clusterID
            user_folder = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio')
            cough_table_path = os.path.join(user_folder, 'cough_table.csv')

            if not os.path.exists(cough_table_path):
                return JsonResponse({'error': 'Cough table does not exist'}, status=404)

            df = pd.read_csv(cough_table_path)
            df.loc[df['time'] == filename, 'clusterID'] = clusterID
            df.to_csv(cough_table_path, index=False)


            return JsonResponse({'message': 'Cluster ID updated successfully'}, status=200)

        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def set_template(request):
    # 檢查請求方法
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        # 設定樣本率
        sample_rate = 16000

        # 獲取並解析元數據
        metadata = request.POST.get('metadata')
        metadata_dict = json.loads(metadata)
        userid = metadata_dict.get('userId')
        filename = metadata_dict.get('fileName')
        latitude = metadata_dict.get('latitude')
        longitude = metadata_dict.get('longitude')
        time = filename


        
        
        # 設定文件名路徑
        filename = os.path.join('', filename + '.wav')
        if not isinstance(filename, str):
            raise ValueError("Invalid filename format")

        # 讀取上傳的音頻文件
        audio_file = request.FILES.get('file')
        audio_data = audio_file.read()

        # 創建用戶的文件路徑
        file_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_template', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 保存音頻檔案
        save_pcm16_to_wav(file_path, audio_data, sample_rate)
        filter_coughs_template(file_path)
        #save_wav_with_resample(file_path, audio_data)


        return JsonResponse({'IsSaving': "true"}, status=200)

        

    except Exception as e:
        # 處理錯誤
        print("Error: ", e)
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def create_cough_audio(request):
    # 檢查請求方法
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    try:
        # 設定樣本率
        sample_rate = 16000

        # 獲取並解析元數據
        metadata = request.POST.get('metadata')
        metadata_dict = json.loads(metadata)
        userid = metadata_dict.get('userId')
        filename = metadata_dict.get('fileName')
        latitude = metadata_dict.get('latitude')
        mode = metadata_dict.get('mode')
        longitude = metadata_dict.get('longitude')
        time = filename

        
        # 設定文件名路徑
        filename = os.path.join('', filename + '.wav')
        if not isinstance(filename, str):
            raise ValueError("Invalid filename format")
                # 對咳嗽進行分群
        all_cough_file_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio')
        template_path_dir = os.path.join(settings.MEDIA_ROOT, userid, 'cough_template')
        cough_csv_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio', 'cough_table.csv')

        # 讀取上傳的音頻文件
        audio_file = request.FILES.get('file')
        audio_data = audio_file.read()

        # 創建用戶的文件路徑
        file_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio', filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 保存音頻檔案
        save_pcm16_to_wav(file_path, audio_data, sample_rate)
        filter_coughs(file_path)
        # save_wav_with_resample(file_path, audio_data)

        #辨別真假咳嗽
        #result = fake_cough_dist(file_path)
        result = True

        # 如果是真咳嗽的話就正常存下來
        if result:
            # 更新用戶資料夾路徑及CSV檔案
            user_folder = os.path.join(settings.MEDIA_ROOT, userid)
            os.makedirs(user_folder, exist_ok=True)
            user_table_path = os.path.join(user_folder, f'{userid}.csv')

            # 讀取並檢查咳嗽公開狀態
            df = pd.read_csv(user_table_path)
            isCoughPub = df.loc[0, 'isCoughPublish']
            isCoughPub = True  # 修改為 True，確保能夠上傳
            classification_result = classify_cough_event(
                cough_wav_path=file_path,
                user_data_path=all_cough_file_path,
                template_data_path=template_path_dir,
                strict_mode=True
            )
            #print(f"[create_cough_audio] Classification result: {classification_result}")


            # 預備處理公開咳嗽音頻

            # 音檔太短會報錯
            clusterid = clustering(file_path, sample_rate, all_cough_file_path, cough_csv_path, template_path_dir)
            time_stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            has_non_user_cough = classification_result['has_non_user_cough']
            
            has_user_cough = classification_result['has_user_cough']

            pubCoughID = '-1'

            if isCoughPub and result == True and not (has_non_user_cough and has_user_cough):
                folder_path_public = os.path.join(settings.MEDIA_ROOT, 'public_cough')
                #    os.makedirs(folder_path_public, exist_ok=True)
                existing_files = os.listdir(folder_path_public)
                file_count = len(existing_files)
                pubCoughID =str( file_count + 1)
                # 保存公開的音頻文件
                file_path_public = os.path.join(folder_path_public, pubCoughID)+'.wav'
                save_pcm16_to_wav(file_path_public, audio_data, sample_rate)
                filter_coughs(file_path_public)
                # save_wav_with_resample(file_path, audio_data)
            cough_table_data = {
                'filename': filename,
                'timestamp':time_stamp,
                'pubCoughID': pubCoughID,
                'time': time,
                'latitude': latitude,
                'longitude': longitude,
                'clusterID': clusterid,  
                'people' : has_non_user_cough and has_user_cough
            }
            update_cough_table(userid, cough_table_data)
            # 如果有非使用者咳嗽和使用者咳嗽，則儲存音訊檔案
            if has_non_user_cough and  has_user_cough:
                user_filename = os.path.join(all_cough_file_path,  filename.replace('.wav', '') + '_1.wav')
                non_user_filename = os.path.join(all_cough_file_path,  filename.replace('.wav', '') + '_2.wav')
                sf.write(user_filename, classification_result['user_output'], classification_result['sample_rate'])
                sf.write(non_user_filename, classification_result['non_user_output'], classification_result['sample_rate'])
                folder_path_public = os.path.join(settings.MEDIA_ROOT, 'public_cough')
                existing_files = os.listdir(folder_path_public)
                file_count = len(existing_files)
                pubCoughID =str( file_count + 1)
                print(f"[user] Saving public cough audio to {pubCoughID}")
                # 保存公開的音頻文件
                file_path_public = os.path.join(folder_path_public, pubCoughID)+'.wav'
                cough_table_data = {
                    'filename': filename.replace('.wav', '') + '_1.wav',
                    'timestamp':time_stamp,
                    'pubCoughID': pubCoughID,
                    'time': time,
                    'latitude': latitude,
                    'longitude': longitude,
                    'clusterID': 0,  
                    'people' : False
                }
                update_cough_table(userid, cough_table_data)
                sf.write(os.path.join(folder_path_public, f'{pubCoughID}.wav'), classification_result['user_output'], classification_result['sample_rate'])
                existing_files = os.listdir(folder_path_public)
                file_count = len(existing_files)
                pubCoughID =str( file_count + 1)
                print(f"[non_user] Saving public cough audio to {pubCoughID}")
                file_path_public = os.path.join(folder_path_public, pubCoughID) + '.wav'
                cough_table_data = {
                    'filename':  filename.replace('.wav', '') + '_2.wav',
                    'timestamp':time_stamp,
                    'pubCoughID': pubCoughID,
                    'time': time,
                    'latitude': latitude,
                    'longitude': longitude,
                    'clusterID': 1,  
                    'people' : False
                }
                update_cough_table(userid, cough_table_data)
                sf.write(os.path.join(folder_path_public, f'{pubCoughID}.wav'), classification_result['non_user_output'], classification_result['sample_rate'])


            if mode == "realtime":
                data = {"user_id":userid, "bass": "tuba", "alto":"clarinet", "high":"flute"} 
                uuid_this = str(uuid.uuid4())
                coughlist = [file_path]
                job = GenerateJob("normal", data, uuid_this, userid, coughlist)
                generate_task_queue.put(job)
                task_progress[uuid_this] = job
                return JsonResponse({'uuid':uuid_this}, status=200)

            else:
                return JsonResponse({'IsSaving':'true','message': 'Audio data received successfully.'}, status=200)
            
            
        
        else:
            # 如果是假咳嗽，則不儲存音訊檔案
            print("Fake cough detected, not saving the audio file.")
            if os.path.exists(file_path):  # 檢查檔案是否存在
                os.remove(file_path)  # 刪除檔案

            return JsonResponse({'IsSaving':'false','message': 'Fake cough detected, not saving the audio file.'}, status=200)

        

    except Exception as e:
        # 處理錯誤
        print("Error: ", e)
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def get_coughs(request):
    if request.method == 'POST':
        try:
            audio_records = []
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            upload_folder = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio')
            cough_table_path = os.path.join(upload_folder, 'cough_table.csv')
            df = None
            if os.path.exists(cough_table_path):
                df = pd.read_csv(cough_table_path)

            for filename in os.listdir(upload_folder):
                if filename.endswith('.wav'):
                    file_path = os.path.join(upload_folder, filename)
                    timestamp = os.path.getmtime(file_path)
                    formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    with wave.open(file_path, 'r') as wav_file:
                        frames = wav_file.getnframes()
                        rate = wav_file.getframerate()
                        duration_seconds = frames / float(rate)
                        minutes, seconds = divmod(round(duration_seconds), 60)
                        duration = f"{minutes:02}:{seconds:02}"

                    cluster_id = None
                    people = None
                    if df is not None:
                        # 取得 base_name
                        match = df[df['filename'] == filename]
                        if not match.empty:
                            cluster_id = str(int(match.iloc[0]['clusterID']))
                            # 取得 people 欄位
                            people = match.iloc[0].get('people', None)
          
                    # 只回傳 people 為 False 的咳嗽
                    if people == False:
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "clusterID": cluster_id
                        }
                        audio_records.append(audio_record)

            return JsonResponse(audio_records, safe=False, status=200)

        except Exception as e:
            print("Error: ", e)
            return JsonResponse({"error": str(e)}, status=500)

 
def get_uploads_file(request, filename):
    #print(f"[get_uploads_file] Requested filename: {filename}")
    filename = filename.replace('^', '/')
    file_path = filename
    #print(f"[get_uploads_file] Requested file path: {file_path}")

    if not os.path.exists(file_path):
        #print(f"[get_uploads_file] File not found: {file_path}")
        raise Http404("File not found")

    file_size = os.path.getsize(file_path)
    #print(f"[get_uploads_file] File size: {file_size}")
    range_header = request.headers.get('Range', '')
    #print(f"[get_uploads_file] Range header: {range_header}")
    content_type = 'application/octet-stream'

    if range_header:
        try:
            range_val = range_header.strip().split('=')[1]
            byte1, byte2 = range_val.split('-')
            byte1 = int(byte1)
            byte2 = int(byte2) if byte2 else file_size - 1
            #print(f"[get_uploads_file] Parsed range: byte1={byte1}, byte2={byte2}")
        except Exception as e:
            print(f"[get_uploads_file] Range parse error: {e}")
            return HttpResponse(status=400)

        length = byte2 - byte1 + 1
        #print(f"[get_uploads_file] Streaming partial content: length={length}")
        f = open(file_path, 'rb')
        f.seek(byte1)
        response = StreamingHttpResponse(FileWrapper(f, blksize=8192), status=206, content_type=content_type)
        response['Content-Length'] = str(length)
        response['Content-Range'] = f'bytes {byte1}-{byte2}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        #print(f"[get_uploads_file] Response headers: Content-Length={response['Content-Length']}, Content-Range={response['Content-Range']}")
        return response

    else:
        #print(f"[get_uploads_file] No range header, streaming full file")
        f = open(file_path, 'rb')
        response = StreamingHttpResponse(FileWrapper(f, blksize=8192), content_type=content_type)
        response['Content-Length'] = str(file_size)
        response['Accept-Ranges'] = 'bytes'
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        #print(f"[get_uploads_file] Response headers: Content-Length={response['Content-Length']}")
        #print(response)
        return response
    
    
@csrf_exempt
def get_music(request):
    if request.method == 'POST':
        try:
            #print("[get_music] 收到 POST 請求")
            audio_records = []
            metadata_dict = json.loads(request.body)
            #print("[get_music] metadata_dict:", metadata_dict)
            userid = metadata_dict.get('userId')
            #print("[get_music] userid:", userid)
            upload_folder_normal = os.path.join(settings.MEDIA_ROOT, userid, 'generated_music')
            upload_folder_trio = os.path.join(settings.MEDIA_ROOT, userid, 'generated_trio')
            upload_folder_drum = os.path.join(settings.MEDIA_ROOT, userid, 'generated_autofill_drum')
            upload_folder_drum_manual = os.path.join(settings.MEDIA_ROOT, userid, 'generated_manual_drum')
            upload_folder_trio_manual = os.path.join(settings.MEDIA_ROOT, userid, 'generated_manual_trio')
            #print("[get_music] 資料夾路徑:")
            #print("  normal:", upload_folder_normal)
            #print("  trio:", upload_folder_trio)
            #print("  drum:", upload_folder_drum)
            #print("  drum_manual:", upload_folder_drum_manual)
            #print("  trio_manual:", upload_folder_trio_manual)
            os.makedirs(upload_folder_normal, exist_ok=True)
            os.makedirs(upload_folder_trio, exist_ok=True)
            os.makedirs(upload_folder_drum, exist_ok=True)
            os.makedirs(upload_folder_drum_manual, exist_ok=True)
            os.makedirs(upload_folder_trio_manual, exist_ok=True)
            
            # 遍歷 normal
            #print("[get_music] 開始遍歷 normal 資料夾")
            for root, dirs, files in os.walk(upload_folder_normal):
                #print(f"[get_music] 目前資料夾: {root}, 檔案數: {len(files)}")
                for filename in files:
                    #print(f"[get_music] 檢查檔案: {filename}")
                    if filename.endswith('.wav'):
                        file_path = os.path.join(root, filename)
                        #print(f"[get_music] 處理 normal 音檔: {file_path}")
                        timestamp = os.path.getmtime(file_path)
                        formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open(file_path, 'r') as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration_seconds = frames / float(rate)
                            minutes, seconds = divmod(round(duration_seconds), 60)
                            duration = f"{minutes:02}:{seconds:02}"
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "type": "normal"
                        }
                        #print(f"[get_music] 加入 normal 音訊紀錄: {audio_record}")
                        audio_records.append(audio_record)
            # 遍歷 trio
            #print("[get_music] 開始遍歷 trio 資料夾")
            for root, dirs, files in os.walk(upload_folder_trio):
                #print(f"[get_music] 目前資料夾: {root}, 檔案數: {len(files)}")
                for filename in files:
                    #print(f"[get_music] 檢查檔案: {filename}")
                    if filename.endswith('.wav'):
                        file_path = os.path.join(root, filename)
                        #print(f"[get_music] 處理 trio 音檔: {file_path}")
                        timestamp = os.path.getmtime(file_path)
                        formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open(file_path, 'r') as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration_seconds = frames / float(rate)
                            minutes, seconds = divmod(round(duration_seconds), 60)
                            duration = f"{minutes:02}:{seconds:02}"
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "type": "trio"
                        }
                        #print(f"[get_music] 加入 trio 音訊紀錄: {audio_record}")
                        audio_records.append(audio_record)
            for root, dirs, files in os.walk(upload_folder_drum):
                #print(f"[get_music] 目前資料夾: {root}, 檔案數: {len(files)}")
                for filename in files:
                    #print(f"[get_music] 檢查檔案: {filename}")
                    if filename.endswith('.wav'):
                        file_path = os.path.join(root, filename)
                        #print(f"[get_music] 處理 drum 音檔: {file_path}")
                        timestamp = os.path.getmtime(file_path)
                        formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open(file_path, 'r') as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration_seconds = frames / float(rate)
                            minutes, seconds = divmod(round(duration_seconds), 60)
                            duration = f"{minutes:02}:{seconds:02}"
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "type": "drum"
                        }
                        print(f"[get_music] 加入 drum 音訊紀錄: {audio_record}")
                        audio_records.append(audio_record)
            # 遍歷 drum_manual
            #print("[get_music] 開始遍歷 drum_manual 資料夾")
            for root, dirs, files in os.walk(upload_folder_drum_manual):
                #print(f"[get_music] 目前資料夾: {root}, 檔案數: {len(files)}")
                for filename in files:
                    #print(f"[get_music] 檢查檔案: {filename}")
                    if filename.endswith('.wav'):
                        file_path = os.path.join(root, filename)
                        #print(f"[get_music] 處理 drum_manual 音檔: {file_path}")
                        timestamp = os.path.getmtime(file_path)
                        formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open(file_path, 'r') as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration_seconds = frames / float(rate)
                            minutes, seconds = divmod(round(duration_seconds), 60)
                            duration = f"{minutes:02}:{seconds:02}"
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "type": "drum_manual"
                        }
                        #print(f"[get_music] 加入 drum_manual 音訊紀錄: {audio_record}")
                        audio_records.append(audio_record)
            # 遍歷 trio_manual
            #print("[get_music] 開始遍歷 trio_manual 資料夾")
            for root, dirs, files in os.walk(upload_folder_trio_manual):
                #print(f"[get_music] 目前資料夾: {root}, 檔案數: {len(files)}")
                for filename in files:
                    #print(f"[get_music] 檢查檔案: {filename}")
                    if filename.endswith('.wav'):
                        file_path = os.path.join(root, filename)
                        #print(f"[get_music] 處理 trio_manual 音檔: {file_path}")
                        timestamp = os.path.getmtime(file_path)
                        formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open(file_path, 'r') as wav_file:
                            frames = wav_file.getnframes()
                            rate = wav_file.getframerate()
                            duration_seconds = frames / float(rate)
                            minutes, seconds = divmod(round(duration_seconds), 60)
                            duration = f"{minutes:02}:{seconds:02}"
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": formatted_timestamp,
                            "duration": duration,
                            "type": "trio_manual"
                        }
                        #print(f"[get_music] 加入 trio_manual 音訊紀錄: {audio_record}")
                        audio_records.append(audio_record)
            #print(f"[get_music] 最終回傳音訊紀錄數量: {len(audio_records)}")
            return JsonResponse(audio_records, safe=False, status=200)

        except Exception as e:
            #print("[get_music] 發生例外:", e)
            import traceback
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt        
def sign_up(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            init_user_folder(userid)
            init_user_table(userid, USER_TABLE_COLUMNS)
            init_cough_table(userid, COUGH_TABLE_COLUMNS)
            init_music_table(userid, MUSIC_TABLE_COLUMNS)
            
            user_folder = os.path.join(settings.MEDIA_ROOT, userid)
            user_table_path = os.path.join(user_folder, f'{userid}.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(user_table_path):
                return JsonResponse({'error': f'User table {user_table_path} does not exist.'}, status=400)
            
            # 排除 user_id
            data_to_update = {key: value for key, value in metadata_dict.items() if key != 'userId'}
            data_to_update['isSignUp'] = True
            
            # 更新用戶資料
            
            update_user_table(userid, data_to_update)
            
            
            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'Audio data received successfully.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def save_music(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            uuid = metadata_dict.get('uuid')
            fileName = metadata_dict.get('fileName')
            type = metadata_dict.get('type')
            remove_job_by_uuid(completed_jobs, uuid)
            save_music_move(userid, uuid, fileName, type)
            
            return JsonResponse({'message': 'Save music successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def clean_temper(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            user_folder = os.path.join(settings.MEDIA_ROOT, userid)
            temp_music_folder = os.path.join(user_folder, 'temp_music')
            temp_midi_folder = os.path.join(user_folder, 'temp_midi')
            if os.path.exists(temp_music_folder):
                shutil.rmtree(temp_music_folder)
            if os.path.exists(temp_midi_folder):
                shutil.rmtree(temp_midi_folder)
            return JsonResponse({'message': 'Save music successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def get_user_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
            user_table_path = os.path.join(user_folder, f'{user_id}.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(user_table_path):
                return JsonResponse({
                'isSignUp': False
            }, status=200)
            
            # 讀取 CSV 文件
            df = pd.read_csv(user_table_path)
            
            # 獲取所有資料
            user_info = df.to_dict(orient='records')
            print("user_info: ", user_info)
            print("user_info[0]: ", user_info[0])
            return JsonResponse(user_info[0], status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def set_user_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
            user_table_path = os.path.join(user_folder, f'{user_id}.csv')

            print("user_table_path: ", user_table_path)
            print("metadata_dict: ", metadata_dict)
            print("user_id: ", user_id)
            print("os.path.exists(user_table_path): ", os.path.exists(user_table_path))
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(user_table_path):
                return JsonResponse({'error': f'User table {user_table_path} does not exist.'}, status=400)
            
            # 排除 user_id
            data_to_update = {key: value for key, value in metadata_dict.items() if key != 'userId'}
            
            print("data_to_update: ", data_to_update)
            
            # 更新用戶資料
            update_user_table(user_id, data_to_update)
            
            return JsonResponse({'message': 'User info updated successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def get_cough_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio')
            cough_table_path = os.path.join(cough_folder, 'cough_table.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(cough_table_path):
                return JsonResponse({'error': f'Cough table {cough_table_path} does not exist.'}, status=400)
            
            # 讀取 CSV 文件
            df = pd.read_csv(cough_table_path)
            
            # 獲取所有資料
            cough_info = df.to_dict(orient='records')
            
            return JsonResponse(cough_info, safe=False, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def set_cough_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio')
            cough_table_path = os.path.join(cough_folder, 'cough_table.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(cough_table_path):
                return JsonResponse({'error': f'Cough table {cough_table_path} does not exist.'}, status=400)
            
            # 排除 user_id
            data_to_update = {key: value for key, value in metadata_dict.items() if key != 'userId'}
            
            # 更新用戶資料
            update_cough_table(user_id, data_to_update)
            
            return JsonResponse({'message': 'Cough info updated successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def get_music_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
            music_table_path = os.path.join(music_folder, 'music_table.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(music_table_path):
                return JsonResponse({'error': f'Music table {music_table_path} does not exist.'}, status=400)
            
            # 讀取 CSV 文件
            df = pd.read_csv(music_table_path)
            
            # 獲取所有資料
            music_info = df.to_dict(orient='records')
            
            return JsonResponse(music_info, safe=False, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def set_music_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
            music_table_path = os.path.join(music_folder, 'music_table.csv')
            
            # 檢查 CSV 文件是否存在
            if not os.path.exists(music_table_path):
                return JsonResponse({'error': f'Music table {music_table_path} does not exist.'}, status=400)
            
            # 排除 user_id 並移除值為 None 的欄位
            data_to_update = {key: value for key, value in metadata_dict.items() if key != 'userId' and value is not None}
            
            # 更新用戶資料
            update_music_table(user_id, data_to_update)
            
            return JsonResponse({'message': 'Music info updated successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_cough_statistics(request):
    if request.method == 'POST':
        try:
            # 讀取 cough_table.csv
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            start_date = metadata_dict.get('startDate')
            end_date = metadata_dict.get('endDate')
            cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
            
            
            if not os.path.exists(cough_table_path):
                return JsonResponse({'error': 'Cough CSV file not found.'}, status=400)
            
            cough_df = pd.read_csv(cough_table_path)
            
            
            # 轉換 timestamp 為 datetime
            cough_df['timestamp'] = pd.to_datetime(cough_df['timestamp'])
            
            
            # 計算一天、一周、一月內的咳嗽功能使用次數
            now = datetime.datetime.now()
            one_day_ago = now - datetime.timedelta(days=1)
            one_week_ago = now - datetime.timedelta(weeks=1)
            one_month_ago = now - datetime.timedelta(days=30)
            
            cough_day_count = cough_df[cough_df['timestamp'] >= one_day_ago].shape[0]
            cough_week_count = cough_df[cough_df['timestamp'] >= one_week_ago].shape[0]
            cough_month_count = cough_df[cough_df['timestamp'] >= one_month_ago].shape[0]

            # 轉換 start_date 和 end_date 為 datetime
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date)
            

            # 過濾出在 start_date 和 end_date 之間的時間
            filtered_df = cough_df[(cough_df['timestamp'] >= start_date) & (cough_df['timestamp'] <= end_date)]
            time_list = filtered_df['time'].tolist()
            
            # 回傳統計結果
            statistics = {
                    'day': str(cough_day_count),
                    'week': str(cough_week_count),
                    'month': str(cough_month_count),
                    'allTime': time_list
            }
            
            return JsonResponse(statistics, status=200)
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_music_statistics(request):
    if request.method == 'POST':
        try:
            # 讀取 music_table.csv
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            music_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music', 'music_table.csv')
            
            if not os.path.exists(music_table_path):
                return JsonResponse({'error': 'Music CSV file not found.'}, status=400)
            
            music_df = pd.read_csv(music_table_path)
            
            # 轉換 timestamp 為 datetime
            music_df['timestamp'] = pd.to_datetime(music_df['timestamp'], unit='s')
            
            # 計算一天、一周、一月內的音樂生成功能使用次數
            now = datetime.datetime.now()
            one_day_ago = now - datetime.timedelta(days=1)
            one_week_ago = now - datetime.timedelta(weeks=1)
            one_month_ago = now - datetime.timedelta(days=30)
            
            music_day_count = music_df[music_df['timestamp'] >= one_day_ago].shape[0]
            music_week_count = music_df[music_df['timestamp'] >= one_week_ago].shape[0]
            music_month_count = music_df[music_df['timestamp'] >= one_month_ago].shape[0]
            
            time_list = music_df['time'].tolist()
            
            # 回傳統計結果
            statistics = {
                    'day': str(music_day_count),
                    'week': str(music_week_count),
                    'month': str(music_month_count),
                    'allTime': time_list
            }
            
            return JsonResponse(statistics, status=200)
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def upload_to_public_cough(request):
    if request.method == 'POST':
        try:
            sample_rate = 16000
            # 獲取 JSON 數據（存放於普通表單字段中）
            metadata = request.POST.get('metadata')
            
            # 將 metadata 轉換為字典並提取 userid 和 filename
            metadata_dict = json.loads(metadata)
            filename = metadata_dict.get('fileName')
            filename = os.path.join('', filename + '.wav')
            
            # 獲取上傳的音檔
            audio_file = request.FILES.get('file')  # 獲取名為 'file' 的文件
            audio_data = audio_file.read()
            
            # 接收音頻數據 
            file_path = os.path.join(settings.IMPORT_COUGH_FOLDER, filename)
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            
            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'Audio data received successfully.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def upload_to_public_music(request):
    if request.method == 'POST':
        try:
            sample_rate = 16000
            # 獲取 JSON 數據（存放於普通表單字段中）
            metadata = request.POST.get('metadata')
            
            # 將 metadata 轉換為字典並提取 userid 和 filename
            metadata_dict = json.loads(metadata)
            filename = metadata_dict.get('fileName')
            filename = os.path.join('', filename + '.wav')
            
            # 獲取上傳的音檔
            audio_file = request.FILES.get('file')  # 獲取名為 'file' 的文件
            audio_data = audio_file.read()
            
            # 接收音頻數據 
            file_path = os.path.join(settings.PUBLIC_MUSIC, filename)
            
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            
            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'Audio data received successfully.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)
        
        
@csrf_exempt
def start_record(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
            os.makedirs(user_folder, exist_ok=True)
            user_table_path = os.path.join(user_folder, f'{user_id}.csv')
            isCoughPub = metadata_dict.get('isPublish')
            
            df = pd.read_csv(user_table_path)
            df.loc[0, 'isCoughPublish'] = isCoughPub
            df.to_csv(user_table_path, index=False)

            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'start audio.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def stop_record(request):
    if request.method == 'POST':
        try:         
            # 假設音頻數據為 float32 格式的原始數據流
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            detecttime = metadata_dict.get('detectTime')
        
            return JsonResponse({'message': 'start audio.'}, status=200)
        
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def delete_music(request):
    if request.method == 'POST':
        try:         
            # 假設音頻數據為 float32 格式的原始數據流
            metadata_dict = json.loads(request.body)
            deleted_music = metadata_dict.get('targetList')

            for i in deleted_music:
                os.remove(i)           
       
            return JsonResponse({'message': 'start audio.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def refresh_best_song(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            target = metadata_dict.get('target', '')

            user_folder = os.path.join(settings.MEDIA_ROOT, userid)
            user_table_path = os.path.join(user_folder, f'{userid}.csv')

            # 檢查 CSV 文件是否存在
            if not os.path.exists(user_table_path):
                return JsonResponse({'error': f'User table {user_table_path} does not exist.'}, status=400)
 
            df = pd.read_csv(user_table_path)

            if target == '':
                # get 模式，回傳 bestSong 欄位
                best_song1 = df.loc[0, 'bestSong1'] if 'bestSong1' in df.columns else ''
                best_song2 = df.loc[0, 'bestSong2'] if 'bestSong2' in df.columns else ''
                best_song3 = df.loc[0, 'bestSong3'] if 'bestSong3' in df.columns else ''
                return JsonResponse({'bestSong1': best_song1,'bestSong2': best_song2,'bestSong3': best_song3}, status=200)
            else:
                # set 模式，更新 bestSong 欄位
                df.loc[0, 'bestSong3'] = df.loc[0, 'bestSong2']
                df.loc[0, 'bestSong2'] = df.loc[0, 'bestSong1']
                df.loc[0, 'bestSong1'] = target
                df.to_csv(user_table_path, index=False)
                return JsonResponse({'bestSong1': df.loc[0, 'bestSong1'],'bestSong2': df.loc[0, 'bestSong2'],'bestSong3': df.loc[0, 'bestSong3']}, status=200)

        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)



@csrf_exempt
def rename_music(request):
    if request.method == 'POST':
        try:         
            # 假設音頻數據為 float32 格式的原始數據流
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            oldName = metadata_dict.get('oldName')
            name = metadata_dict.get('name')
            
            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)

             ### 處理 generated_music 資料夾 ###
            music_folder = os.path.join(user_folder, 'generated_music')
            midi_folder = os.path.join(user_folder, 'generated_midi')

            folders_to_search = [music_folder, midi_folder]
    
            for folder in folders_to_search:
                # 確保資料夾存在
                if not os.path.exists(folder):
                    continue
        
                # 遍歷資料夾中的所有子資料夾
                for root, dirs, files in os.walk(folder):
                    # 檢查是否有資料夾名稱為 oldname
                    if os.path.basename(root) == oldName:
                        # 找到目標資料夾，接著處理其中的檔案
                
                        # 遍歷資料夾中的所有檔案
                        for file in files:
                            if oldName in file:
                                old_file_path = os.path.join(root, file)
                                new_file_name = file.replace(oldName, name)
                                new_file_path = os.path.join(root, new_file_name)
                        
                                # 重命名檔案
                                os.rename(old_file_path, new_file_path)
                
                        # 重命名資料夾
                        new_folder_name = root.replace(oldName, name)
                        if root != new_folder_name:
                            os.rename(root, new_folder_name)

            music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
            os.makedirs(music_folder, exist_ok=True)
            music_table_path = os.path.join(music_folder, 'music_table.csv')

            # 讀取現有的 CSV 文件
            df = pd.read_csv(music_table_path)

            df.loc[df['filename'] == oldName, 'filename'] = name
    
            # 保存更新後的 DataFrame 到 CSV 文件
            df.to_csv(music_table_path, index=False)
            
       
            return JsonResponse({'message': 'start audio.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

              
@csrf_exempt 
def save_music_cocreate(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            uuid = metadata_dict.get('uuid')
            fileName = metadata_dict.get('fileName')
            save_final_cocreate(userid, uuid, fileName)
            return JsonResponse({'message': 'Save music successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@csrf_exempt
def generate(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    try:
        data = json.loads(request.body.decode("utf-8"))
        mode = data.get('mode', 'normal')     
        userId = data.get('user_id')

        coughlist_str = data.get('cough_path', None)
        #print("cough_path:", coughlist_str)
        coughlist_path = [p for p in (coughlist_str.split('^') if coughlist_str else []) if p]
        coughlist = [
            Path(os.path.join(settings.MEDIA_ROOT, userId, 'cough_audio', p + '.wav'))
            for p in coughlist_path
        ]
        cough_length = len(coughlist_path)
        uuid_this = str(uuid.uuid4())
        #print(f'mode: {mode}, userId: {userId}, coughlist: {coughlist_path}')

        # Determine mode based on cough count and input flag
        if mode == 'co_create_trio':
            if cough_length == 1:
                mode = 'trio'
            elif 2<= cough_length <= 4:
                mode = 'trio_manual'
            else:
                return JsonResponse({'error': 'Trio mode supports 2-4 cough inputs.'}, status=400)
            #print('------------')
        elif mode == 'co_create_drum':
            if 1 <= cough_length <= 6:
                # Auto-fill up to 7 in GenerateJob class later
                mode = 'drum'
            elif cough_length == 7:
                mode = 'drum_manual'
            else:
                return JsonResponse({'error': 'Drum mode supports 1-7 cough inputs.'}, status=400)

        #print(f"[generate] mode: {mode}, userId: {userId}, coughlist: {coughlist_path}")
        job = GenerateJob(mode, data, uuid_this, userId, coughlist)
        generate_task_queue.put(job)
        task_progress[uuid_this] = job
        return JsonResponse({'status': 'queued', 'uuid': uuid_this}, status=202)
    
    except Exception as e:
        print("[generate] 發生例外:", e)
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def generate_status_view(request):

    #print("[generate_status_view] called")
    try:
        data = json.loads(request.body.decode("utf-8"))
        #print("[generate_status_view] request data:", data)
    except Exception as e:
        #print("[generate_status_view] JSON decode error:", e)
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    uuid = data.get('uuid')
    userId = data.get('userId')
    #print("[generate_status_view] uuid:", uuid, "userId:", userId)
    
    # 如果有指定 uuid，返回該 uuid 的狀態
    if uuid:
        job = task_progress.get(uuid, None)
        #print("[generate_status_view] job from task_progress:", job)
        if job:
            #print("[generate_status_view] found job, returning status")
            return JsonResponse({
                'uuid': job.uuid,
                'mode': job.mode,
                'time': job.time,
                'duration': job.duration,
                'status': job.status,
                'result': job.result if job.status == 'completed' else None
            }, status=200)
        #print("[generate_status_view] UUID not found")
        return JsonResponse({'error': 'UUID not found'}, status=404)

    # 過濾 function
    def filter_by_user(jobs):
        if userId:
            filtered = [job for job in jobs if getattr(job, 'user_id', None) == userId]
            #print(f"[generate_status_view] filter_by_user: {len(filtered)} jobs for user {userId}")
            return filtered
        #print(f"[generate_status_view] filter_by_user: return all {len(jobs)} jobs")
        return list(jobs)
    
    # 如果有指定 user_id，返回該 user_id 的所有 queue、processing 和 completed 的物件
    #print("[generate_status_view] checking queued jobs")
    queued_jobs = [
        {
            'uuid': job.uuid,
            'mode': job.mode,
            'time': job.time,
            'duration': job.duration,
            'status': job.status,
            'cough_path': job.data['cough_path'],
            'result': job.result
        }
        for job in filter_by_user(generate_task_queue.queue)
    ]
    #print(f"[generate_status_view] queued_jobs: {len(queued_jobs)}")

    #print("[generate_status_view] checking processing jobs")
    processing_jobs_status = [
        {
            'uuid': job.uuid,
            'mode': job.mode,
            'time': job.time,
            'duration': job.duration,
            'status': job.status,
            'result': job.result
        }
        for job in filter_by_user(processing_jobs)
    ]
    #print(f"[generate_status_view] processing_jobs_status: {len(processing_jobs_status)}")

    #print("[generate_status_view] checking completed jobs")
    completed_jobs_status = [
        {
            'uuid': job.uuid,
            'mode': job.mode,
            'time': job.time,
            'duration': job.duration,
            'status': job.status,
            'result': job.result
        }
        for job in filter_by_user(completed_jobs)
    ]
    #print(f"[generate_status_view] completed_jobs_status: {len(completed_jobs_status)}")

    all_jobs = queued_jobs + processing_jobs_status + completed_jobs_status
    #print(f"[generate_status_view] all_jobs count: {len(all_jobs)}")
    return JsonResponse(all_jobs, safe=False, status=200)

@csrf_exempt
def submit_survey(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
            filename = metadata_dict.get('fileName')
            
            if not user_id or not filename:
                return JsonResponse({'error': 'Missing userId or fileName'}, status=400)

            # 定義問卷記錄的欄位
            columns = [
                'timestamp', 'filename', 'source_type', 'source_detail', 
                'selected_mode', 'thoughts', 'has_shared', 'share_details', 
                'original_process_mode'
            ]

            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
            os.makedirs(user_folder, exist_ok=True)
            survey_table_path = os.path.join(user_folder, 'survey_table.csv')

            # 處理可能為巢狀字典的 source_detail，將其轉為 JSON 字串以便存入單一 CSV 欄位
            source_detail = metadata_dict.get('source_detail', '')
            if isinstance(source_detail, (dict, list)):
                source_detail = json.dumps(source_detail, ensure_ascii=False)

            row_data = {
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'filename': filename,
                'source_type': metadata_dict.get('source_type', ''),
                'source_detail': source_detail,
                'selected_mode': metadata_dict.get('selected_mode', ''),
                'thoughts': metadata_dict.get('thoughts', ''),
                'has_shared': metadata_dict.get('has_shared', ''),
                'share_details': metadata_dict.get('share_details', ''),
                'original_process_mode': metadata_dict.get('original_process_mode', '')
            }

            # 檢查檔案是否存在，以決定是否需要寫入標題列 (header)
            file_exists = os.path.exists(survey_table_path)
            
            df = pd.DataFrame([row_data])
            
            if not file_exists:
                df.to_csv(survey_table_path, index=False, columns=columns)
            else:
                df.to_csv(survey_table_path, mode='a', header=False, index=False, columns=columns)

            return JsonResponse({'message': 'Survey submitted successfully.'}, status=200)

        except Exception as e:
            print("Error in submit_survey: ", e)
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)