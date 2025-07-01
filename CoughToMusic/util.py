import os
from django.conf import settings
from .lib import cough
import wave
import shutil
import datetime
from .table import update_music_table


def save_pcm16_to_wav(filename, data, rate):
    """保存音頻數據到 WAV 文件。"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)  # 單聲道
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(rate)
        wf.writeframes(data)

  
def generate_music(user_id, cough_path, filename, bass_music = "tuba", alto_music = "clarinet", high_music = "flute", sample_rate = 16000):
   
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

    if type == 'trio':
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        trio_new_fp = os.path.join(user_folder, 'generated_trio')
        os.makedirs(trio_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_trio')
        new_music_folder = os.path.join(trio_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
        #togo
    elif type == 'drum':
        drum_new_fp = os.path.join(user_folder, 'generated_drum')
        #music_folder = os.path.join(user_folder, 'generated_music_cocreate')
        os.makedirs(drum_new_fp, exist_ok=True)
        old_music_folder = os.path.join(user_folder, 'temp_drum')
        new_music_folder = os.path.join(drum_new_fp, filename_display)
        os.makedirs(new_music_folder, exist_ok=True)
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
                if file.endswith(f"{uuid}_short_drum.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_short_drum.wav")
                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)
                elif file.endswith(f"{uuid}_drum_auto.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_drum_auto.wav")
                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)


        elif type == 'trio':
            for file in os.listdir(old_music_folder):
                if file.endswith(f"{uuid}_short_trio.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_short_trio.wav")

                    if file.endswith(".wav"):
                        shutil.move(old_file_path, new_file_path)

                elif file.endswith(f"{uuid}_trio_auto.wav"):
                    old_file_path = os.path.join(old_music_folder, file)
                    new_file_path = os.path.join(new_music_folder, f"{filename_display}_trio_auto.wav")

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
    os.makedirs(cough_folder, exist_ok=True)
    os.makedirs(generate_music_folder, exist_ok=True)
    os.makedirs(generate_midi_folder, exist_ok=True)
    os.makedirs(generate_drum, exist_ok=True)
    os.makedirs(generate_trio, exist_ok=True)
    

    
