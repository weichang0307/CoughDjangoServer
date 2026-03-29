import os
from django.conf import settings
import wave
import shutil
import datetime
import io
from .table import update_music_table
import numpy as np
from .utils.runner import run_cli
from .windowing import detect_onsets, select_analysis_window


def save_pcm16_to_wav(filename, data, rate):
    """保存音頻數據到 WAV 文件。"""

    try:
        # 如果 data 是 numpy array (float32)，先轉 int16
        if isinstance(data, np.ndarray):
            if data.dtype == np.float32 or data.dtype == np.float64:
                data = (data * 32767).astype(np.int16).tobytes()
            elif data.dtype == np.int16:
                data = data.tobytes()
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(data)
    except Exception as e:
        print(f"Error saving wav: {e}")
        raise

def save_wav_with_resample(filename, data, target_rate=16000):
    """自動偵測並轉換 sample rate，保存音頻數據到 WAV 文件。"""
    try:
        # 讀取 bytes 為 numpy array，sr=None 代表用原始 sample rate
        import librosa
        import soundfile as sf
        y, sr = librosa.load(io.BytesIO(data), sr=None, mono=True)
        if sr != target_rate:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_rate)
        sf.write(filename, y, target_rate)
    except Exception as e:
        print(f"Error saving wav: {e}")
        raise

def generate_music(user_id, cough_path, filename, bass_music = "tuba", alto_music = "clarinet", high_music = "flute", sample_rate = 16000):
    from .lib import cough

   
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    # temp改成和cocreate一樣的temp資料夾
    music_output_path_temp = os.path.join(user_folder, 'temp_music') 
    music_midi_path_temp = os.path.join(user_folder, 'temp_midi')
    
    # 檢查並創建資料夾
    os.makedirs(music_output_path_temp, exist_ok=True)
    os.makedirs(music_midi_path_temp, exist_ok=True)
    
    music_output_path = os.path.join(user_folder, 'generated_music')
    music_midi_path = os.path.join(user_folder, 'generated_midi')
    
    os.makedirs(music_output_path, exist_ok=True)
    os.makedirs(music_midi_path, exist_ok=True)
    
    
    cough_instance = cough.Cough(
        audio_path=cough_path,
        sample_rate=sample_rate,
        filename=filename,
        midi_path=music_midi_path_temp,
        output_path=music_output_path_temp,
        instrument_bass=bass_music,
        instrument_alto=alto_music,
        instrument_high=high_music
    )

    print(f"Generating music for {cough_instance.filename} with instruments: {bass_music}, {alto_music}, {high_music}") 
    
    cough_instance.midi_generation()
    cough_instance.write_audio()
    cough_instance.loudness_normalize()
    
    generated_music_path_folder = os.path.join(music_output_path_temp, cough_instance.filename)
    generated_music_path = os.path.join(generated_music_path_folder, f"{cough_instance.filename}.wav")
    
    return generated_music_path


def save_music_move(user_id, uuid, filename_display, type):
    """
    修正後的 save_music_move 確保最內層的檔案名稱是 filename 而不是 uuid。
    """

    if not uuid or not filename_display:
        print("Error: filename or filename_display is empty.")
        return
    
    if not settings.MEDIA_ROOT:
        raise ValueError("settings.MEDIA_ROOT is not set")
    if not user_id:
        raise ValueError("user_id is not provided")
    
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)


    ### 處理 generated_music 資料夾 ###
    
    old_music_folder = ''
    new_music_folder = ''

    if type == 'drum_autofill':
        type = 'drum'

    if type == 'trio':
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        trio_new_fp = os.path.join(user_folder, 'generated_trio')
        os.makedirs(trio_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_trio')
        new_music_folder = os.path.join(trio_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
        #togo
    # elif type == 'drum':
    #     drum_new_fp = os.path.join(user_folder, 'generated_drum')
    #     #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
    #     os.makedirs(drum_new_fp, exist_ok=True)
    #     old_music_folder = os.path.join(user_folder, 'temp_drum')
    #     new_music_folder = os.path.join(drum_new_fp, filename_display)
    #     os.makedirs(new_music_folder, exist_ok=True)
    elif type == 'trio_manual':
        drum_new_fp = os.path.join(user_folder, 'generated_manual_trio')
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        os.makedirs(drum_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_manual_trio')
        new_music_folder = os.path.join(drum_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
    elif type == 'drum_manual':
        drum_new_fp = os.path.join(user_folder, 'generated_manual_drum')
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        os.makedirs(drum_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_manual_drum')
        new_music_folder = os.path.join(drum_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
    elif type == 'drum':
        drum_new_fp = os.path.join(user_folder, 'generated_autofill_drum')
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        os.makedirs(drum_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_autofill_drum')
        new_music_folder = os.path.join(drum_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
        #togo
    else:
        #music_folder = os.path.join(user_folder, 'generated_music')
        music_folder = os.path.join(user_folder, 'generated_music')
        os.makedirs(music_folder, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_music', uuid)
        new_music_folder = os.path.join(music_folder, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
    
    if os.path.exists(old_music_folder):
        if type == 'normal':
            for file in os.listdir(old_music_folder):
                old_file_path = os.path.join(old_music_folder, file)
                new_file_path = os.path.join(new_music_folder, f"{filename_display}.wav")  # 直接命名成 filename_display
                if file.endswith(".wav"):
                    shutil.move(old_file_path, new_file_path)
                    shutil.rmtree(old_music_folder)  # 移動完畢後刪除空資料夾

        elif type == 'drum':
            for file in os.listdir(old_music_folder):
                # if file.endswith(f"{uuid}_short_drum.wav"):
                #     old_file_path = os.path.join(old_music_folder, file)
                #     new_file_path = os.path.join(new_music_folder, f"{filename_display}_short_drum.wav")
                #     if file.endswith(".wav"):
                #         shutil.move(old_file_path, new_file_path)
                if file.endswith(f"{uuid}_drum.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_drum.wav")
                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)


        elif type == 'trio':
            for file in os.listdir(old_music_folder):
                # if file.endswith(f"{uuid}_short_trio.wav"):
                #     old_file_path = os.path.join(old_music_folder, file)
                #     new_file_path = os.path.join(new_music_folder, f"{filename_display}_short_trio.wav")

                #     if file.endswith(".wav"):
                #         shutil.move(old_file_path, new_file_path)

                if file.endswith(f"{uuid}_trio.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_trio.wav")

                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)
                

        elif type == 'trio_manual':
            for file in os.listdir(old_music_folder):
                if file.endswith(f"{uuid}_trio.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_trio.wav")

                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)

        elif type == 'drum_manual':
            for file in os.listdir(old_music_folder):
                if file.endswith(f"{uuid}_drum.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_drum.wav")

                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)
        # elif type == 'drum_autofill':
        #     for file in os.listdir(old_music_folder):
        #         if file.endswith(f"{uuid}_drum.wav"):
        #             old_file_path = os.path.join(old_music_folder, file)
        #             new_file_path = os.path.join(new_music_folder, f"{filename_display}_drum.wav")

        #             if file.endswith(".wav"):
        #                 shutil.move(old_file_path, new_file_path)
            
    else:
        print(f"Error: {old_music_folder} does not exist.")

    ### 處理 generated_midi 資料夾 ###
    if type == 'normal':
        midi_folder = os.path.join(user_folder, 'generated_midi')
        os.makedirs(midi_folder, exist_ok=True)

        old_midi_folder = os.path.join(user_folder, 'temp_midi', uuid)
        new_midi_folder = os.path.join(midi_folder, filename_display)
        os.makedirs(new_midi_folder, exist_ok=True)

        if os.path.exists(old_midi_folder):
            for file in os.listdir(old_midi_folder):
                old_file_path = os.path.join(old_midi_folder, file)
                substr = old_file_path.split('_')
                new_file_path = os.path.join(new_midi_folder, f"{filename_display}_{substr[-1]}")
                if file.endswith(".mid"):
                    shutil.move(old_file_path, new_file_path)
            #shutil.rmtree(old_midi_folder)  # 移動完畢後刪除空資料夾
        else:
            print(f"Error: {old_midi_folder} does not exist.")


    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    music_table_data = {"filename": filename_display, "timestamp": datetime.datetime.now().timestamp(), 'time' : current_datetime}
    update_music_table(user_id, music_table_data)

    print(f"✅ Successfully moved music & midi files for {filename_display}")

    

def init_user_folder(user_id):
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    os.makedirs(user_folder, exist_ok=True)
    cough_folder = os.path.join(user_folder, 'cough_audio')
    generate_music_folder = os.path.join(user_folder, 'generated_music')
    generate_drum = os.path.join(user_folder, 'generated_drum')
    generate_trio = os.path.join(user_folder, 'generated_trio')
    generate_midi_folder = os.path.join(user_folder, 'generated_midi')
    COUGH_TEMPLATE_FOLDER = os.path.join(user_folder, 'cough_template')
    os.makedirs(COUGH_TEMPLATE_FOLDER, exist_ok=True)
    os.makedirs(cough_folder, exist_ok=True)
    os.makedirs(generate_music_folder, exist_ok=True)
    os.makedirs(generate_midi_folder, exist_ok=True)
    os.makedirs(generate_drum, exist_ok=True)
    os.makedirs(generate_trio, exist_ok=True)


def fake_cough_dist(cough_path, sample_rate=16000):
    from .lib import Fake_cough_filter
    import librosa

    audio_data, sr = librosa.load(cough_path, sr=sample_rate)
    result = Fake_cough_filter.detect_inhale(audio_data, sr)
    return result


def is_blank(wav_path, *, audio_loader=None, onset_module=None, freq_module=None, configs=None):
    # Enable narrow local debugging without turning normal uploads into noisy logs.
    debug_enabled = os.environ.get("COUGHTOMUSIC_BLANK_DEBUG") == "1"

    def _debug(message):
        if debug_enabled:
            print(f"[is_blank] {os.path.basename(wav_path)}: {message}", flush=True)

    if audio_loader is None:
        _debug("using lightweight wav loader")
        audio_loader = _load_wav_audio
    if onset_module is None or freq_module is None or configs is None:
        _debug("importing blank-detection onset/freq helpers and configs")
        from .cocreate.workflow_common import ACC_CONFIG, BASS_CONFIG, MEL_CONFIG

        onset_module = onset_module or _BlankOnsetModule()
        freq_module = freq_module or _BlankFreqModule()
        configs = configs or (MEL_CONFIG, ACC_CONFIG, BASS_CONFIG)
        _debug("finished blank-detection helper/config imports")

    _debug("loading audio")
    audio_data, sample_rate = audio_loader(wav_path, sr=None, mono=True)
    audio_data = np.asarray(audio_data)
    _debug(f"loaded samples={audio_data.size} sample_rate={sample_rate}")

    analysis_audio, window_info = select_analysis_window(audio_data, sample_rate)
    audio_data = np.asarray(analysis_audio)
    _debug(
        "analysis window "
        f"reason={window_info.get('reason')} "
        f"start_sample={window_info.get('window_start_sample')} "
        f"end_sample={window_info.get('window_end_sample')} "
        f"target_samples={window_info.get('target_samples')}"
    )

    if audio_data.size == 0 or np.ptp(audio_data) <= 1e-6 or np.max(np.abs(audio_data)) <= 1e-6:
        _debug("rejected as blank due to empty/flat waveform")
        return True

    _debug("running onset detection")
    onset_times = onset_module.detect(audio_data, sample_rate)
    _debug(f"onset_count={len(onset_times)}")
    if len(onset_times) == 0:
        _debug("rejected as blank due to missing onset")
        return True

    audio_duration = len(audio_data) / float(sample_rate) if sample_rate else 0

    for index, config in enumerate(configs, start=1):
        _debug(
            "running crepe/note pass "
            f"{index}/{len(configs)} threshold={config['threshold']} energy_th={config['energy_th']}"
        )
        _, f0 = freq_module.get_by_crepe(
            audio_data,
            sample_rate,
            config["threshold"],
            energy_threshold=config["energy_th"],
        )
        f0_scaled = freq_module.log_scale_frequencies(f0, config["min_target"], config["max_target"])
        result_array, notes_on_frame, notes_off_frame = freq_module.to_note_msg(
            onset_times,
            f0_scaled,
            config["freq_range_th"],
            config["note_interval_th"],
            60,
            audio_duration,
        )
        if (
            len(result_array) > 0
            and len(notes_on_frame) > 0
            and len(notes_off_frame) > 0
            and not all(p <= 1e-3 for p in result_array)
        ):
            _debug(
                "accepted as non-blank with "
                f"notes={len(result_array)} onsets={len(notes_on_frame)} offsets={len(notes_off_frame)}"
            )
            return False

    _debug("rejected as blank because no config produced usable notes")
    return True


def _load_wav_audio(wav_path, sr=None, mono=True):
    """Load PCM WAV data without importing librosa."""
    with wave.open(wav_path, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        channel_count = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        raw_frames = wav_file.readframes(frame_count)

    audio_data = _decode_wav_frames(raw_frames, sample_width, channel_count)
    if mono and audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)
    if sr is not None and sr != sample_rate:
        raise ValueError("Lightweight WAV loader does not resample audio.")
    return audio_data.astype(np.float32, copy=False), sample_rate


def _decode_wav_frames(raw_frames, sample_width, channel_count):
    if sample_width == 1:
        audio = np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 128.0
    elif sample_width == 2:
        audio = np.frombuffer(raw_frames, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 3:
        audio = _decode_pcm24(raw_frames)
    elif sample_width == 4:
        audio = np.frombuffer(raw_frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    if channel_count > 1:
        frame_count = len(audio) // channel_count
        audio = audio[: frame_count * channel_count].reshape(frame_count, channel_count)
    return audio


def _decode_pcm24(raw_frames):
    byte_count = len(raw_frames) // 3
    bytes_array = np.frombuffer(raw_frames[: byte_count * 3], dtype=np.uint8).reshape(byte_count, 3)
    signed = (
        bytes_array[:, 0].astype(np.int32)
        | (bytes_array[:, 1].astype(np.int32) << 8)
        | (bytes_array[:, 2].astype(np.int32) << 16)
    )
    sign_bit = 1 << 23
    signed = (signed ^ sign_bit) - sign_bit
    return signed.astype(np.float32) / 8388608.0


class _BlankOnsetModule:
    @staticmethod
    def detect(audio_data, sr, initial_threshold=0.2, min_threshold=0.05, step=0.05):
        return detect_onsets(audio_data, sr, initial_threshold, min_threshold, step)


class _BlankFreqModule:
    @staticmethod
    def get_by_crepe(audio_data, sr, threshold, energy_threshold, energy_filter=True):
        import crepe
        import librosa

        time, frequency, confidence, _ = crepe.predict(audio_data, sr=sr, viterbi=True)
        frequency = np.where(confidence < threshold, np.nan, frequency)
        if energy_filter:
            spectrogram = librosa.feature.melspectrogram(y=audio_data, sr=sr, n_mels=128, fmax=8000)
            mel_times = librosa.frames_to_time(np.arange(spectrogram.shape[1]), sr=sr, hop_length=512)
            spectrogram_db = librosa.power_to_db(spectrogram, ref=np.max)
            energy_mask = np.interp(time, mel_times, spectrogram_db.max(axis=0)) > energy_threshold
            frequency = np.where(energy_mask, frequency, np.nan)
        return time, frequency

    @staticmethod
    def log_scale_frequencies(frequencies, min_target, max_target):
        import librosa

        valid_freqs = frequencies[~np.isnan(frequencies) & (frequencies > 0)]
        if len(valid_freqs) == 0:
            return frequencies

        fmin_input = np.min(valid_freqs)
        fmax_input = np.max(valid_freqs)
        if np.isclose(fmax_input, fmin_input):
            return np.asarray(frequencies)
        log_fmin_input = np.log2(fmin_input)
        log_fmax_input = np.log2(fmax_input)
        fmin_target = librosa.note_to_hz(min_target)
        fmax_target = librosa.note_to_hz(max_target)

        scaled = []
        for frequency in frequencies:
            if np.isnan(frequency) or frequency <= 0:
                scaled.append(frequency)
                continue
            log_freq = np.log2(frequency)
            scaled_log_freq = (log_freq - log_fmin_input) / (log_fmax_input - log_fmin_input)
            scaled_log_freq = scaled_log_freq * (np.log2(fmax_target) - np.log2(fmin_target)) + np.log2(fmin_target)
            scaled.append(2 ** scaled_log_freq)
        return np.asarray(scaled)

    @staticmethod
    def to_note_msg(onset_time, f0, freq_range_th, note_interval_th, break_th, wavefile_time):
        onset_point = _seconds_to_frames(onset_time, wavefile_time, f0)
        result_array = []
        time_start_array = []
        time_end_array = []

        def process_interval(start, end):
            temp_array = []
            nan_count = 0
            freq_seen = 0
            nan_token = 0

            for frame_index in range(start, end):
                if np.isnan(f0[frame_index]):
                    if freq_seen:
                        nan_count += 1
                        freq_seen = 0
                    else:
                        if nan_count > note_interval_th:
                            if temp_array:
                                average_freq = np.mean(temp_array)
                                result_array.append(average_freq)
                                time_end_array.append(frame_index - nan_count)
                                temp_array = []
                                nan_count = 0
                            elif nan_token < break_th:
                                nan_token += 1
                            else:
                                break
                        else:
                            nan_count += 1
                else:
                    if not temp_array:
                        temp_array.append(f0[frame_index])
                        time_start_array.append(frame_index)
                        nan_count = 0
                        freq_seen = 1
                    else:
                        average_freq = np.mean(temp_array)
                        if abs(f0[frame_index] - average_freq) > (freq_range_th * average_freq):
                            time_end_array.append(frame_index - 1)
                            result_array.append(average_freq)
                            temp_array = [f0[frame_index]]
                            time_start_array.append(frame_index)
                            nan_count = 0
                            freq_seen = 1
                        else:
                            temp_array.append(f0[frame_index])
                            nan_count = 0
                            freq_seen = 1

            if temp_array:
                average_freq = np.mean(temp_array)
                result_array.append(average_freq)
                time_end_array.append(end - 1)

        if len(onset_point) == 0:
            process_interval(0, len(f0))
        else:
            for index, start in enumerate(onset_point):
                end = onset_point[index + 1] if index < len(onset_point) - 1 else len(f0)
                process_interval(start, end)

        return np.asarray(result_array), np.asarray(time_start_array), np.asarray(time_end_array)

def _seconds_to_frames(time_array, total_time, f0):
    onset_time_array = []
    for onset_time in time_array:
        frame_value = int((onset_time / total_time) * len(f0)) if total_time else 0
        onset_time_array.append(frame_value)
    return np.array(onset_time_array)


def filter_coughs(audio_path):
    payload = {
        "mode": "filter",
        "audio_path": audio_path,
        "write_mode": "mask",
        "apply_energy_gate": True,
    }
    res = run_cli(
        python_exe=settings.YAMNET_PYTHON_EXE,
        entry_py=os.path.join(settings.BASE_DIR, "CoughToMusic", "yamnet_worker", "run_yamnet_worker.py"),
        payload=payload,
        cwd=str(settings.BASE_DIR),
        enable_log=False,
    )
    if not res["ok"]:
        worker_error = res.get("error") or "Filter worker failed"
        worker_stdout = (res.get("stdout") or "").strip()
        worker_stderr = (res.get("stderr") or "").strip()
        details = " | ".join([part for part in [worker_error, worker_stdout or None, worker_stderr or None] if part])
        raise RuntimeError(f"filter_coughs failed: {details}")
    return res.get("json")

def filter_coughs_template(audio_path):
    from .lib import filter_template

    filter_template.process_audio(audio_path)

def classify_cough_event(cough_wav_path, user_data_path, template_data_path, strict_mode=True):
    payload = {
        "mode": "classify",
        "audio_path": cough_wav_path,
        "user_data_path": user_data_path,
        "template_data_path": template_data_path,
        "strict_mode": strict_mode
    }
    res = run_cli(
        python_exe=settings.YAMNET_PYTHON_EXE,
        entry_py="C:/Users/DreamalityLab/Desktop/jayden/CoughDjangoServer/CoughToMusic/yamnet_worker/run_yamnet_worker.py",
        payload=payload,
        cwd=str(settings.BASE_DIR),
        enable_log=False
    )
    return res.get("json")

def clustering(file_path, sample_rate, all_cough_file_path, cough_csv_path, template_path_dir):
    payload = {
        "mode": "cluster",
        "path": file_path,
        "sample_rate": sample_rate,
        "all_cough_file_path": all_cough_file_path,
        "cough_csv_path": cough_csv_path,
        "template_path_dir": template_path_dir
    }
    res = run_cli(
        python_exe=settings.YAMNET_PYTHON_EXE,
        entry_py="C:/Users/DreamalityLab/Desktop/jayden/CoughDjangoServer/CoughToMusic/yamnet_worker/run_yamnet_worker.py",
        payload=payload,
        cwd=str(settings.BASE_DIR),
        enable_log=False
    )

    if res["ok"] and "cluster_id" in res["json"]:
        return res["json"]["cluster_id"]
    else:
        print("[clustering] CLI worker error:", res)
        return "error"



# def classify_cough_event(cough_wav_path, user_data_path, template_data_path, strict_mode=True):
#     """
#     對咳嗽音頻進行分類，返回分類結果。
#     :param cough_wav_path: 咳嗽音頻的路徑
#     :param user_data_path: 使用者數據的路徑
#     :param template_data_path: 模板數據的路徑
#     :param strict_mode: 是否啟用嚴格模式
#     :return: 分類結果
#     """
#     return cough_cluster.classify_cough_file(cough_wav_path, user_data_path, template_data_path, strict_mode)
    
# def clustering(file_path, sample_rate, all_cough_file_path, cough_csv_path, template_path_dir):
#     """
#     對音頻進行聚類，返回聚類結果。
#     :param file_path: 音頻文件的路徑
#     :param sample_rate: 音頻的采樣率
#     :param all_cough_file_path: 所有咳嗽音頻的路徑
#     :param cough_csv_path: 咳嗽 CSV 文件的路徑
#     :param template_path_dir: 模板數據的路徑
#     :return: 聚類結果
#     """
#     return cough_cluster.cluster_audio(file_path, sample_rate, all_cough_file_path, cough_csv_path, template_path_dir)
