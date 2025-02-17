import os
from django.views.decorators.csrf import csrf_exempt
from .util import generate_music, save_pcm16_to_wav, init_user_folder, save_music_move
from .table import update_user_table, init_user_table, init_cough_table, update_cough_table, init_music_table, update_music_table
from django.conf import settings
from django.http import JsonResponse
from django.http import FileResponse, Http404
import shutil
import pandas as pd
import json
import datetime

USER_TABLE_COLUMNS = ['isSignUp', 'name', 'age', 'gender', 'education', 'musicProficiency']
COUGH_TABLE_COLUMNS = ['filename', 'timestamp', 'duration']
MUSIC_TABLE_COLUMNS = ['filename', 'timestamp', 'duration', 'bass', 'alto', 'high', 'cough_filename', 'cough_filepath', 'music_filepath']

@csrf_exempt
def create_cough_audio(request):
    if request.method == 'POST':
        try:
            sample_rate = 16000
            # 獲取 JSON 數據（存放於普通表單字段中）
            metadata = request.POST.get('metadata')
            print(metadata)
            
            # 將 metadata 轉換為字典並提取 userid 和 filename
            metadata_dict = json.loads(metadata)
            userid = metadata_dict.get('userId')
            filename = metadata_dict.get('fileName')
            filename = os.path.join('', filename + '.wav')
            print(f"User ID: {userid}")
            print(f"File Name: {filename}")
            
            # 獲取上傳的音檔
            audio_file = request.FILES.get('file')  # 獲取名為 'file' 的文件
            audio_data = audio_file.read()
            
            # 接收音頻數據 
            print("Receiving audio data...")
            file_path = os.path.join(settings.MEDIA_ROOT, userid, 'cough_audio', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            print("file save to: ", file_path)
            
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
    print("filename: ", filename)
    filename = filename.replace('^', '/') 
    print("filename: ", filename)
    file_path = filename
    print("file_path: ", file_path)
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
            return JsonResponse({'generate_path': generate_path}, status=200)

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

def get_cough_statistics(request):
    if request.method == 'POST':
        try:
            # 讀取 cough_table.csv
            metadata_dict = json.loads(request.body)
            user_id = metadata_dict.get('userId')
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
            
            # 回傳統計結果
            statistics = {
                'cough': {
                    'day': cough_day_count,
                    'week': cough_week_count,
                    'month': cough_month_count
                }
            }
            
            return JsonResponse(statistics, status=200)
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

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
            
            # 回傳統計結果
            statistics = {
                'music': {
                    'day': music_day_count,
                    'week': music_week_count,
                    'month': music_month_count
                }
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
            file_path = os.path.join(settings.PUBLIC_COUGH, filename)
            
            
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            print("file save to: ", file_path)
            
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
        
        






