import os
import soundfile as sf
import pyloudnorm as pyln
import noisereduce as nr
from . import pitch, data_preprocessing, freq, midi, audio , volumn

FREQ_RANGE = 0.25 #0.4
NOTE_INTERVAL = 30 #70
BREAK = 20

class Cough:
    DEFAULT_THRESHOLD = 0.5

    def __init__(self, audio_path, sample_rate, filename, midi_path ,output_path, instrument_bass, instrument_alto, instrument_high):
        self.audio_path = audio_path  
        self.sample_rate = sample_rate   
        self.filename = filename
        self.instrument_bass = instrument_bass
        self.instrument_alto = instrument_alto
        self.instrument_high = instrument_high
        self.midi_path =  midi_path       
        self.output_path = output_path
        
        try:
            self.audio_data = data_preprocessing.load_audio(self.audio_path, self.sample_rate)
        except Exception as e:
            raise ValueError(f"Error loading audio: {e}")
        
        try:
            self.f0 = pitch.analyze_pitch(self.audio_data, self.sample_rate, threshold=self.DEFAULT_THRESHOLD)
        except Exception as e:
            raise ValueError(f"Error analyzing pitch: {e}")
        
        self.midi_volume = volumn.process_audio_to_normalized_rms(self.f0, self.audio_data, self.sample_rate, freq_range_th=FREQ_RANGE, note_interval_th=NOTE_INTERVAL, break_th=BREAK)
        print(self.midi_volume)

    def midi_generation(self, onset_seg=True, freq_range_th=FREQ_RANGE, note_interval_th=NOTE_INTERVAL, break_th=BREAK):
        try:
            freq.write_midi(self.audio_data, self.sample_rate, self.f0, self.midi_path,self.filename ,onset_seg, freq_range_th, note_interval_th, break_th)
        except Exception as e:
            raise ValueError(f"Error generating MIDI: {e}")

    def midi_to_2_bar(self):
        try:
            midi.to_2bars(self.midi_path, self.midi_path)
        except Exception as e:
            raise ValueError(f"Error converting MIDI to 2 bars: {e}")

    def write_audio(self):
        try:
            # 建立 output_path 中的 filename 資料夾
            output_dir = os.path.join(self.output_path, self.filename)
            os.makedirs(output_dir, exist_ok=True)

            # 定義 MIDI 檔案名稱
            midi_files = {
                'Bass': self.instrument_bass,
                'Alto': self.instrument_alto,
                'High': self.instrument_high
            }

            # 生成音檔並存儲
            audio_files = []
            for part, instrument in midi_files.items():
                midi_file = os.path.join(self.midi_path, self.filename, f"{self.filename}_{part}.mid")
                
                # 如果檔案不存在
                if not os.path.exists(midi_file):
                    continue
                
                audio_file = os.path.join(output_dir, f"{self.filename}_{part}.wav")
                audio.write_from_midi(midi_file, audio_file, instrument=instrument, volume=self.midi_volume, sample_rate=self.sample_rate)
                audio_files.append(audio_file)

            # 將三種音檔疊加並存儲
            if audio_files:
                combined_audio_file = os.path.join(output_dir, f"{self.filename}.wav")
                audio.combine_audio_files(audio_files, combined_audio_file, sample_rate=self.sample_rate)
                for file in audio_files:
                    os.remove(file)

        except Exception as e:
            raise ValueError(f"Error writing audio: {e}")
    
    def loudness_normalize(self, target_loudness=-16):
        try:
            for root, _, files in os.walk(self.output_path):
                for file in files:
                    if file.endswith(".wav"):
                        file_path = os.path.join(root, file)
                        
                        # 讀取 WAV 檔案
                        audio_data, sr = sf.read(file_path)
                    
                        meter = pyln.Meter(sr)  # create BS.1770 meter
                    
                        # 計算LUFS
                        current_loudness = meter.integrated_loudness(audio_data)

                        # 計算所需的增益來達到 target_loudness
                        normalized_audio = pyln.normalize.loudness(audio_data, current_loudness, target_loudness)

                        # 確保音量不會超過最大值
                        peak_normalized_audio = pyln.normalize.peak(normalized_audio, -1.0)  # -1.0 dBFS peak
                    
                        # 去除雜聲
                        noise_reduced_audio = nr.reduce_noise(y=peak_normalized_audio, sr=sr)
                    
                        # 寫入標準化後的音訊檔案
                        sf.write(file_path, noise_reduced_audio, sr)
        except Exception as e:
            raise ValueError(f"Error normalizing loudness: {e}")
        
    