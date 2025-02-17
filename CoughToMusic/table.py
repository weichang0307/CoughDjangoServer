import pandas as pd
import os
from django.conf import settings

def init_user_table(user_id, columns_name):
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    os.makedirs(user_folder, exist_ok=True)
    user_table_path = os.path.join(user_folder, f'{user_id}.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(user_table_path):
        # 如果不存在，創建一個新的 DataFrame 並保存為 CSV 文件
        df = pd.DataFrame(columns=columns_name)
        df.to_csv(user_table_path, index=False)
        print(f"User table {user_table_path} created successfully.")
    else:
        print(f"User table {user_table_path} already exists.")

def update_user_table(user_id, data):
    user_folder = os.path.join(settings.MEDIA_ROOT, user_id)
    os.makedirs(user_folder, exist_ok=True)
    user_table_path = os.path.join(user_folder, f'{user_id}.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(user_table_path):
        print(f"User table {user_table_path} does not exist.")
        return
    
    # 讀取現有的 CSV 文件
    df = pd.read_csv(user_table_path)
    
    # 更新用戶資料
    for key, value in data.items():
        if key in df.columns:
            df.loc[0, key] = value  # 更新第一行的資料
              
    # 保存更新後的 DataFrame 到 CSV 文件
    df.to_csv(user_table_path, index=False)
    print(f"User {user_id} updated successfully.")
    
def init_cough_table(user_id, columns_name):
    cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio')
    os.makedirs(cough_folder, exist_ok=True)
    cough_table_path = os.path.join(cough_folder, 'cough_table.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(cough_table_path):
        # 如果不存在，創建一個新的 DataFrame 並保存為 CSV 文件
        df = pd.DataFrame(columns=columns_name)
        df.to_csv(cough_table_path, index=False)
        print(f"Cough table {cough_table_path} created successfully.")
    else:
        print(f"Cough table {cough_table_path} already exists.")
        
def update_cough_table(user_id, data):
    cough_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'cough_audio')
    os.makedirs(cough_folder, exist_ok=True)
    cough_table_path = os.path.join(cough_folder, 'cough_table.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(cough_table_path):
        print(f"User table {cough_table_path} does not exist.")
        return
    
    # 讀取現有的 CSV 文件
    df = pd.read_csv(cough_table_path)
    
    for key, value in data.items():
        if key in df.columns:
            df.loc[0, key] = value  # 更新第一行的資料
    
    # 保存更新後的 DataFrame 到 CSV 文件
    df.to_csv(cough_table_path, index=False)
    print(f"User {user_id} updated successfully.")
    
def init_music_table(user_id, columns_name):
    music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
    os.makedirs(music_folder, exist_ok=True)
    music_table_path = os.path.join(music_folder, 'music_table.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(music_table_path):
        # 如果不存在，創建一個新的 DataFrame 並保存為 CSV 文件
        df = pd.DataFrame(columns=columns_name)
        df.to_csv(music_table_path, index=False)
        print(f"Cough table {music_table_path} created successfully.")
    else:
        print(f"Cough table {music_table_path} already exists.")
        
def update_music_table(user_id, data):
    music_folder = os.path.join(settings.MEDIA_ROOT, user_id, 'generated_music')
    os.makedirs(music_folder, exist_ok=True)
    music_table_path = os.path.join(music_folder, 'music_table.csv')
    
    # 檢查 CSV 文件是否存在
    if not os.path.exists(music_table_path):
        print(f"User table {music_table_path} does not exist.")
        return
    
    # 讀取現有的 CSV 文件
    df = pd.read_csv(music_table_path)
    
    for key, value in data.items():
        if key in df.columns:
            df.loc[0, key] = value  # 更新第一行的資料
    
    # 保存更新後的 DataFrame 到 CSV 文件
    df.to_csv(music_table_path, index=False)
    print(f"User {user_id} updated successfully.")