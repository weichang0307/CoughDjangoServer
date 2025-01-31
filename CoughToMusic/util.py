import os
from django.conf import settings
from .lib import cough
from .models import CoughAudio
import numpy as np
import uuid
import time
import wave
import io
SAMPLE_RATE = 16000
INSTRUMENT_BASS = "tuba"
INSTRUMENT_ALTO = "clarinet"
INSTRUMENT_HIGH = "flute"

def convert_cough_to_music(cough_file_path):
    
    base_name, ext = os.path.splitext(os.path.basename(cough_file_path))
    
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    
    new_base_name = f"{base_name}_{timestamp}"
    
    # 路徑設定
    music_output_path = os.path.join(settings.MEDIA_ROOT, 'generated_music') # 命名待思考
    music_midi_path = os.path.join(settings.MEDIA_ROOT, 'generated_midi') # 命名待思考
    
    # 檢查並創建資料夾
    os.makedirs(music_output_path, exist_ok=True)
    os.makedirs(music_midi_path, exist_ok=True)
    
    cough_instance = cough.Cough(
        audio_path=cough_file_path,
        sample_rate=SAMPLE_RATE,
        filename=new_base_name,
        midi_path=music_midi_path,
        output_path=music_output_path,
        instrument_bass=INSTRUMENT_BASS,
        instrument_alto=INSTRUMENT_ALTO,
        instrument_high=INSTRUMENT_HIGH
    )
    
    cough_instance.midi_generation()
    cough_instance.write_audio()
    cough_instance.loudness_normalize()


def save_pcm16_to_wav(filename, data, rate):
    """保存音頻數據到 WAV 文件。"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)  # 單聲道
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(rate)
        wf.writeframes(data)



def pcm16_to_float32_wav(input_pcm_buffer: bytes, num_channels: int, sample_rate: int) -> bytes:
    """
    将 16 位 PCM 数据 buffer 转换为 32 位浮点 WAV buffer。
    
    :param input_pcm_buffer: 输入的 16 位 PCM 数据（bytes）
    :param num_channels: 声道数（1 表示单声道，2 表示立体声）
    :param sample_rate: 采样率（例如 44100 Hz）
    :return: 输出的 32 位浮点 WAV 数据（bytes）
    """
    # 将输入 PCM 数据转换为 NumPy 数组
    int16_data = np.frombuffer(input_pcm_buffer, dtype=np.int16)

    # 将 16 位整数数据转换为 32 位浮点数 [-1.0, 1.0]
    float32_data = int16_data.astype(np.float32) / 32768.0

    # 创建内存 buffer 来保存输出 WAV 数据
    output_io = io.BytesIO()

    # 打开一个 wave 写入流
    with wave.open(output_io, 'wb') as wav_out:
        # 设置 WAV 文件参数
        wav_out.setnchannels(num_channels)  # 声道数
        wav_out.setsampwidth(4)  # 32 位浮点的字节宽度是 4
        wav_out.setframerate(sample_rate)  # 采样率

        # 写入浮点 PCM 数据
        wav_out.writeframes(float32_data.tobytes())

    # 返回 WAV 数据的字节流
    return output_io.getvalue()

import time
from .lib import cough
  
def generate_music(cough_path, filename, bass_music = "tuba", alto_music = "clarinet", high_music = "flute", sample_rate = 16000):
    
    # 使用timestape作為檔名
    # base_name, ext = os.path.splitext(os.path.basename(cough_path))
    
    # timestamp = time.strftime('%Y%m%d_%H%M%S')
    
    # new_base_name = f"{base_name}_{timestamp}"
    
    # 路徑設定
    music_output_path = os.path.join(settings.MEDIA_ROOT, 'generated_music') 
    music_midi_path = os.path.join(settings.MEDIA_ROOT, 'generated_midi') 
    
    # 檢查並創建資料夾
    os.makedirs(music_output_path, exist_ok=True)
    os.makedirs(music_midi_path, exist_ok=True)
    
    cough_instance = cough.Cough(
        audio_path=cough_path,
        sample_rate=sample_rate,
        filename=filename,
        midi_path=music_midi_path,
        output_path=music_output_path,
        instrument_bass=bass_music,
        instrument_alto=alto_music,
        instrument_high=high_music
    )
    
    cough_instance.midi_generation()
    cough_instance.write_audio()
    cough_instance.loudness_normalize()
    
    generated_music_path_folder = os.path.join(music_output_path, cough_instance.filename)
    generated_music_path = os.path.join(generated_music_path_folder, f"{cough_instance.filename}.wav")
    
    return generated_music_path

