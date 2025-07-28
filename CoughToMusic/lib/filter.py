import numpy as np
import librosa
import soundfile as sf
from scipy import signal
from noisereduce import reduce_noise

COUGH_END_TIME = 0.2  # 咳嗽結束時間延長量（秒）
MIN_COUGH_DURATION = 0.05  # 最短咳嗽段落（秒）
ENERGY_PERCENTILE = 85  # 能量閾值百分位數

def process_audio(audio_path, sample_rate=None):
    # 載入音頻
    audio, sr = librosa.load(audio_path, sr=sample_rate)
    print(f"音訊載入成功：採樣率 {sr} Hz，總長 {len(audio)/sr:.2f} 秒")

    # === 降噪處理 ===
    try:
        reduced_audio = reduce_noise(y=audio, sr=sr, prop_decrease=0.5, stationary=False)
        if not np.isfinite(reduced_audio).all():
            print("⚠️ 發現非有限值，進行清理")
            reduced_audio = np.nan_to_num(reduced_audio, nan=0.0, posinf=0.0, neginf=0.0)
            if not np.isfinite(reduced_audio).all():
                print("⚠️ 清理失敗，使用原始音訊")
                reduced_audio = audio.copy()
        max_val = np.max(np.abs(reduced_audio))
        if max_val > 0:
            reduced_audio = reduced_audio / max_val * 0.9
    except Exception as e:
        print(f"⚠️ 降噪錯誤：{e}，使用原始音訊")
        reduced_audio = audio.copy()

    # === 動態能量分割 ===
    frame_length = int(0.025 * sr)
    hop_length = int(0.01 * sr)
    energy = np.array([np.sum(np.abs(reduced_audio[i:i+frame_length]**2))
                       for i in range(0, len(reduced_audio) - frame_length, hop_length)])
    threshold = np.percentile(energy, ENERGY_PERCENTILE)
    cough_mask = energy > threshold

    cough_segments = []
    start = None
    for i in range(len(cough_mask)):
        if cough_mask[i] and start is None:
            start = i * hop_length
        elif not cough_mask[i] and start is not None:
            end = (i * hop_length) + frame_length
            duration = (end - start) / sr
            if duration >= MIN_COUGH_DURATION:
                cough_segments.append((start, min(len(reduced_audio), end + int(COUGH_END_TIME * sr))))
            start = None
    if start is not None:
        end = len(reduced_audio)
        duration = (end - start) / sr
        if duration >= MIN_COUGH_DURATION:
            cough_segments.append((start, end))

    if not cough_segments:
        print("⚠️ 未偵測到咳嗽段落，輸出與原始音訊相同")
        sf.write(audio_path, reduced_audio, sr)
        return

    # === 濾波器設定 ===
    nyquist = sr / 2
    lowcut = 50
    highcut = min(7500, nyquist * 0.95)  # 自動修正高頻

    if lowcut >= highcut:
        lowcut = highcut * 0.1
        print(f"⚠️ 自動調整低頻截止點為: {lowcut:.0f} Hz")

    def bandpass_filter(segment):
        try:
            b, a = signal.butter(4, [lowcut, highcut], btype='band', fs=sr)
            return signal.filtfilt(b, a, segment)
        except Exception as e:
            print(f"⚠️ 濾波失敗：{e}，返回原始段落")
            return segment

    # === 咳嗽段落濾波 ===
    output_audio = np.zeros_like(reduced_audio)
    total_cough_duration = 0.0

    for i, (start, end) in enumerate(cough_segments):
        segment = reduced_audio[start:end]
        if len(segment) < 100:
            output_audio[start:end] = segment
            print(f"段落 {i+1} 太短，跳過濾波")
            continue
        filtered_segment = bandpass_filter(segment)
        output_audio[start:end] = filtered_segment
        total_cough_duration += (end - start) / sr

    # === 寫入檔案 ===
    sf.write(audio_path, output_audio, sr)
    print(f"✅ 咳嗽音訊處理完成，已覆蓋儲存至 {audio_path}")
    print(f"📊 共檢測 {len(cough_segments)} 個咳嗽段落，總時長 {total_cough_duration:.2f} 秒，佔比 {(total_cough_duration / (len(audio)/sr)) * 100:.1f}%")

# 範例用法（實際使用時請自行呼叫 process_audio）
# process_audio("your_audio_file.wav")
