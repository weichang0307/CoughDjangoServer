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

USER_TABLE_COLUMNS = ['isSignUp', 'name', 'age', 'gender', 'education', 'musicProficiency', 'isCoughPublish', 'userEmail']
COUGH_TABLE_COLUMNS = ['filename', 'timestamp', 'pubCoughID', 'time']
MUSIC_TABLE_COLUMNS = ['filename', 'timestamp', 'time']


@csrf_exempt
def create_cough_audio(request):
    if request.method == 'POST':
        try:
            sample_rate = 16000
            # 獲取 JSON 數據（存放於普通表單字段中）
            metadata = request.POST.get('metadata')
            
            # 將 metadata 轉換為字典並提取 userid 和 filename
            metadata_dict = json.loads(metadata)
            userid = metadata_dict.get('userId')
            filename = metadata_dict.get('fileName')
            time = filename
            filename = os.path.join('', filename + '.wav')
            
            # 獲取上傳的音檔
            audio_file = request.FILES.get('file')  # 獲取名為 'file' 的文件
            audio_data = audio_file.read()
            
            # 接收音頻數據 
            file_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            save_pcm16_to_wav(file_path, audio_data, sample_rate)

            user_folder = os.path.join(settings.MEDIA_ROOT, userid)
            os.makedirs(user_folder, exist_ok=True)
            user_table_path = os.path.join(user_folder, f'{userid}.csv')

            df = pd.read_csv(user_table_path)
            isCoughPub = df.loc[0, 'isCoughPublish']

            file_count = -1

            if isCoughPub:
                # 定義存儲路徑
                folder_path_public = os.path.join(settings.MEDIA_ROOT, 'public_cough')
    
                # 確保資料夾存在
                os.makedirs(folder_path_public, exist_ok=True)
    
                # 取得資料夾內檔案數量
                existing_files = os.listdir(folder_path_public)
                file_count = len(existing_files)
    
                # 設定新檔案名稱
                filename = f"{file_count + 1}.wav"  # 你可以根據需要調整檔案名稱格式
    
                # 完整檔案路徑
                file_path_public = os.path.join(folder_path_public, filename)
    
                # 儲存檔案
                save_pcm16_to_wav(file_path_public, audio_data, sample_rate)

            # 更新 cough_table.csv
            cough_table_data = {'filename': filename, 'timestamp': datetime.datetime.now().timestamp(), 'pubCoughID' : file_count+1, 'time' : time}
            update_cough_table(userid, cough_table_data)
            
            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'Audio data received successfully.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_coughs(request):
    if request.method == 'POST':
        try:
            # 準備回傳的音訊資料
            audio_records = []
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            upload_folder = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio')

            for filename in os.listdir(upload_folder):
                if filename.endswith('.wav'):  # 只處理 WAV 檔案
                    file_path = os.path.join(upload_folder, filename)
                    print("relative_path: ", file_path)
                    timestamp = os.path.getmtime(file_path)  # 檔案修改時間
                    duration = "00:00"  # 可替換成實際計算的音訊時長邏輯
                    
                    # 建立音訊紀錄字典
                    audio_record = {
                        "filename": filename.replace('.wav', ''),
                        "filePath": file_path,
                        "timestamp": int(timestamp),
                        "duration": duration
                    }
                    audio_records.append(audio_record)

            return JsonResponse(audio_records, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

 
def get_uploads_file(request, filename):
    # 確保檔案存在
    filename = filename.replace('^', '/') 
    file_path = filename
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True)
    else:
        raise Http404("File not found")
    
    
@csrf_exempt
def get_music(request):
    if request.method == 'POST':
        try:
            # 準備回傳的音訊資料
            audio_records = []
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            upload_folder = os.path.join(settings.MEDIA_ROOT, userid, 'generated_music')
            
            # 使用 os.walk() 遞迴遍歷資料夾
            for root, dirs, files in os.walk(upload_folder):
                for filename in files:
                    if filename.endswith('.wav'):  # 只處理 WAV 檔案
                        file_path = os.path.join(root, filename)  # 包含子資料夾的完整路徑
                        print("relative_path: ", file_path)
                        timestamp = os.path.getmtime(file_path)  # 檔案修改時間
                        duration = "00:00"  # 可替換成實際計算的音訊時長邏輯
                        
                        # 建立音訊紀錄字典
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": int(timestamp),
                            "duration": duration
                        }
                        audio_records.append(audio_record)

            return JsonResponse(audio_records, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def generate(request):
    if request.method == 'POST':
            # Debug: Log the raw request body

            # Parse JSON from the request body
            data = json.loads(request.body.decode("utf-8"))

            # Validate required keys
            required_keys = ['cough_path', 'user_id', 'bass', 'alto', 'high', 'uuid']
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return JsonResponse({'error': f'Missing required keys: {missing_keys}'}, status=400)

            # Process data
            generate_path = generate_music(
                data['user_id'],
                data['cough_path'],
                data['uuid'],
                data['bass'].lower(),
                data['alto'].lower(),
                data['high'].lower()
            )
            
            # Success response
            return JsonResponse({'generate_path': generate_path, 'cough_path': data['cough_path']}, status=200)

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
            save_music_move(userid, uuid, fileName)
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
            print("user_id: ", user_id)
            user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
            user_table_path = os.path.join(user_folder, f'{user_id}.csv')
            
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
            
            # 排除 user_id
            data_to_update = {key: value for key, value in metadata_dict.items() if key != 'userId'}
            
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
            cough_df['timestamp'] = pd.to_datetime(cough_df['timestamp'], unit='s')
            
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
            print("Receiving audio data...")
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
            print("Receiving audio data...")
            file_path = os.path.join(settings.PUBLIC_MUSIC, filename)
            
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            print("file save to: ", file_path)
            
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
            user_id = metadata_dict.get('userId')
            deleted_music = metadata_dict.get('targetList')

            music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
            os.makedirs(music_folder, exist_ok=True)
            music_table_path = os.path.join(music_folder, 'music_table.csv')

            # 讀取現有的 CSV 文件
            df = pd.read_csv(music_table_path)

            for i in deleted_music:
                df = df[df['filename'] != i['filename']]
                temp = os.path.dirname(i['filePath'])
                shutil.rmtree(temp)

    
            # 保存更新後的 DataFrame 到 CSV 文件
            df.to_csv(music_table_path, index=False)
            
       
            return JsonResponse({'message': 'start audio.'}, status=200)
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
                    print(f"{folder} 資料夾不存在！")
                    continue
        
                # 遍歷資料夾中的所有子資料夾
                for root, dirs, files in os.walk(folder):
                    # 檢查是否有資料夾名稱為 oldname
                    if os.path.basename(root) == oldName:
                        # 找到目標資料夾，接著處理其中的檔案
                        print(f"處理資料夾: {root}")
                
                        # 遍歷資料夾中的所有檔案
                        for file in files:
                            if oldName in file:
                                old_file_path = os.path.join(root, file)
                                new_file_name = file.replace(oldName, name)
                                new_file_path = os.path.join(root, new_file_name)
                        
                                # 重命名檔案
                                os.rename(old_file_path, new_file_path)
                                print(f"檔案已重命名: {old_file_path} -> {new_file_path}")
                
                        # 重命名資料夾
                        new_folder_name = root.replace(oldName, name)
                        if root != new_folder_name:
                            os.rename(root, new_folder_name)
                            print(f"資料夾已重命名: {root} -> {new_folder_name}")

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
def generate_trio_from_cough(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode("utf-8"))
            print("data: ", data)
            user_id = data['userId']
            cough_path = data['coughPath']
            uuid = data['uuid']
            time_value = os.path.splitext(os.path.basename(cough_path))[0]
            print(time_value)  # Output: 2025-04-07-16-30-10

            user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'temp_cocreate')
            os.makedirs(user_tmp_folder, exist_ok=True)

            # time_value = data.get('time')
            instrument_type = 'string'

            cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio', 'cough_table.csv')
            if not os.path.exists(cough_table_path):
                return JsonResponse({'error': f'Cough table not found for user {user_id}.'}, status=404)

            df = pd.read_csv(cough_table_path)
            match = df[df['time'] == time_value]
            if match.empty:
                return JsonResponse({'error': f'No entry found for time {time_value}.'}, status=404)

            pubCoughID = int(match.iloc[0]['pubCoughID'])
            print ("pubCoughID: ", pubCoughID)

            # generate_path_triomotif = cough2midi(pubCoughID, instrument_type, user_tmp_folder, uuid, sample_rate=16000)
            # gen_trio_mid(pubCoughID)
            # generate_path_trio = gen_trio_trk(pubCoughID, instrument_type,user_tmp_folder,uuid,  sample_rate=16000)
            generate_path_drummotif, generate_path_drum = generate_groove_intp(settings.PUBLIC_COUGH, pubCoughID, user_tmp_folder, uuid)

            return JsonResponse({
                # 'generate_path_triomotif': generate_path_triomotif,
                # 'generate_path_trio': generate_path_trio, 
                'generate_path_drummotif': generate_path_drummotif,
                'generate_path_drum': generate_path_drum
            }, status=200)

        except Exception as e:
            import traceback; traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def get_music_cocreate(request):
    if request.method == 'POST':
        try:
            # 準備回傳的音訊資料
            audio_records = []
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            upload_folder = os.path.join(settings.MEDIA_ROOT, userid, 'generated_music_cocreate')
            
            # 使用 os.walk() 遞迴遍歷資料夾
            for root, dirs, files in os.walk(upload_folder):
                for filename in files:
                    if filename.endswith('.wav'):  # 只處理 WAV 檔案
                        file_path = os.path.join(root, filename)  # 包含子資料夾的完整路徑
                        print("relative_path: ", file_path)
                        timestamp = os.path.getmtime(file_path)  # 檔案修改時間
                        duration = "00:00"  # 可替換成實際計算的音訊時長邏輯
                        
                        # 建立音訊紀錄字典
                        audio_record = {
                            "filename": filename.replace('.wav', ''),
                            "filePath": file_path,
                            "timestamp": int(timestamp),
                            "duration": duration
                        }
                        audio_records.append(audio_record)

            return JsonResponse(audio_records, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
        
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