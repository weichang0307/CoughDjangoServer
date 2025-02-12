import os
from django.views.decorators.csrf import csrf_exempt
from .util import generate_music, save_pcm16_to_wav, init_user_folder, save_music_move
from django.conf import settings
from django.http import JsonResponse
from django.http import FileResponse, Http404
import shutil
import json

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
            
            print("upload_folder: ", upload_folder)
            
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
            print("generate_path: ", generate_path)

            # Success response
            return JsonResponse({'generate_path': generate_path}, status=200)

@csrf_exempt        
def sign_up(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            userid = metadata_dict.get('userId')
            init_user_folder(userid)
            print(metadata_dict)
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
            return JsonResponse({
                'isSignUp': True,
                'name' : 'test',
                'age' : '20',
                'gender' : 'Male',
                'education' : 'Master',
                'musicProficiency' : '4'
            }, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def set_user_info(request):
    if request.method == 'POST':
        try:
            metadata_dict = json.loads(request.body)
            print(metadata_dict)
            return JsonResponse({'message': 'Save music successfully.'}, status=200)
            
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)
        
    return JsonResponse({'error': 'Invalid request method'}, status=400)
def upload_cough(request):
    return JsonResponse({'message': 'Upload cough audio successfully.'}, status=200)



