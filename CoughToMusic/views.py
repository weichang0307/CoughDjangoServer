import os
from django.views.decorators.csrf import csrf_exempt
from .util import pcm16_to_float32_wav, generate_music, save_pcm16_to_wav
from django.conf import settings
import numpy as np
from django.http import JsonResponse
from .lib_detect_cough.keras_yamnet.yamnet import YAMNet
from django.http import FileResponse, Http404
from .lib_detect_cough.keras_yamnet.preprocessing import preprocess_input
import json
import uuid

# 檢查音訊數據是否有效（非零）
def check_audio(data):
    """檢查音訊數據是否有效（非零）。"""
    return np.any(data)

# 加載 YAMNet 模型和類別
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
model_path = os.path.join(base_dir, 'CoughToMusicDjango', 'CoughToMusic', 'lib_detect_cough', 'keras_yamnet', 'yamnet.h5')

model = YAMNet(weights=model_path)
cough_class_idx = 42  # 咳嗽對應的類別索引

# 用來保存最近的音頻緩衝區
audio_buffer = []
cough_buffer = []
margin_buffer = []

# 參數設置
WIN_SIZE_SEC = 0.975  # 每個 frame 的大小（秒）
MARGIN_SIZE_SEC = 2  # 邊界 的大小（秒）
MAX_BUFFER_SIZE_SEC = 60  # 最大緩衝區大小（秒）
FRAME_SIZE = 16000 * WIN_SIZE_SEC  # frame 大小（樣本數）
MARGIN_SIZE = 16000 * MARGIN_SIZE_SEC  # frame 大小（樣本數）
COUGH_THRESHOLD = 0.2  # 咳嗽判斷閾值
FULL_AUDIO_SECONDS = 4  # 完整音訊長度（秒）
FULL_AUDIO_SAMPLES = 16000 * FULL_AUDIO_SECONDS  # 完整音訊大小（樣本數）
MAX_BUFFER_SIZE = 16000 * MAX_BUFFER_SIZE_SEC  # 最大緩衝區大小（樣本數）

# 確保 FRAME_SIZE 和 FULL_AUDIO_SAMPLES 是整數
FRAME_SIZE = int(FRAME_SIZE)
FULL_AUDIO_SAMPLES = int(FULL_AUDIO_SAMPLES)

@csrf_exempt
def create_cough_audio(request):
    global audio_buffer
    global cough_buffer
    global margin_buffer
    
    if request.method == 'POST':
        try:
            # 接收音頻數據 
            print("Receiving audio data...")
            audio_data = request.body 
            sample_rate = 16000  # 確保來自客戶端的音頻是 YAMNet 支持的採樣率
            filename = f"cough_{uuid.uuid4()}.wav"
            file_path = os.path.join("media/cough_audio", filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            save_pcm16_to_wav(file_path, audio_data, sample_rate)
            print("file save to: ", file_path)
            # 假設音頻數據為 float32 格式的原始數據流
            return JsonResponse({'message': 'Audio data received successfully.'}, status=200)
        except Exception as e:
            print("Error: ", e)
            return JsonResponse({'error': str(e)}, status=400)

                        

    return JsonResponse({'error': 'Invalid request method'}, status=400)


def get_records(request):
    try:
        # 準備回傳的音訊資料
        audio_records = []
        upload_folder = settings.COUGH_PATH  # 假設你在 settings.py 中設置了 UPLOAD_FOLDER

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

def get_music(request):

    try:
        # 準備回傳的音訊資料
        audio_records = []
        upload_folder = settings.MUSIC_PATH  # 假設你在 settings.py 中設置了 UPLOAD_FOLDER
        
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
            print(f"Request Body: {request.body}")

            # Parse JSON from the request body
            data = json.loads(request.body.decode("utf-8"))

            # Validate required keys
            required_keys = ['cough_path', 'file_name', 'bass', 'alto', 'high']
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                return JsonResponse({'error': f'Missing required keys: {missing_keys}'}, status=400)

            # Process data
            generate_path = generate_music(
                data['cough_path'],
                data['file_name'],
                data['bass'].lower(),
                data['alto'].lower(),
                data['high'].lower()
            )
            print("generate_path: ", generate_path)

            # Success response
            return JsonResponse({'generate_path': generate_path}, status=200)

