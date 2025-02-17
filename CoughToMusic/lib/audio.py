from midi_ddsp.utils.midi_synthesis_utils import synthesize_mono_midi, conditioning_df_to_audio
from midi_ddsp.midi_ddsp_synthesize import load_pretrained_model
from midi_ddsp.data_handling.instrument_name_utils import INST_NAME_TO_ID_DICT
from midi_ddsp.utils.audio_io import save_wav
import tensorflow as tf
import wave
import numpy as np

def write_from_midi(midi_path, output_path, instrument, volume, sample_rate):
    # Load pre-trained model
    synthesis_generator, expression_generator = load_pretrained_model()
    instrument_id = INST_NAME_TO_ID_DICT[instrument]
    
    # Synthesize MIDI
    _, _, _, conditioning_df = synthesize_mono_midi(synthesis_generator, expression_generator, midi_path, instrument_id, output_dir=None)
    conditioning_df_changed = conditioning_df.copy()
    
    # Modify the volume for odd indices
    odd_indices = conditioning_df_changed.index[conditioning_df_changed.index % 2 == 1]
    for i, idx in enumerate(odd_indices):
        if i < len(volume):
            conditioning_df_changed.at[idx, 'volume'] = volume[i]            
    
    # Re-synthesize
    midi_audio_changed, _, _ = conditioning_df_to_audio(
        synthesis_generator, conditioning_df_changed, tf.constant([instrument_id]))

    synthesized_audio_changed = midi_audio_changed  # The synthesized audio
    
    # Save the synthesized audio to the output path
    save_wav(synthesized_audio_changed[0].numpy(), output_path, sample_rate=sample_rate)
    
def combine_audio_files(audio_files, output_file, sample_rate):
    try:
        # 讀取所有音檔並找出最長的音檔長度
        audio_data = []
        max_length = 0
        for file in audio_files:
            with wave.open(file, 'rb') as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                audio_data.append(np.frombuffer(frames, dtype=np.int16))
                max_length = max(max_length, len(audio_data[-1]))

        # 將較短的音檔數據填充為與最長音檔相同的長度
        for i in range(len(audio_data)):
            if len(audio_data[i]) < max_length:
                audio_data[i] = np.pad(audio_data[i], (0, max_length - len(audio_data[i])), 'constant')

        # 將所有音檔數據相加
        combined_audio = np.sum(audio_data, axis=0)

        # 確保數據不超出範圍
        combined_audio = np.clip(combined_audio, -32768, 32767)

        # 將數據轉換回 bytes
        combined_audio = combined_audio.astype(np.int16).tobytes()

        # 寫入合併後的音檔
        with wave.open(output_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # 單聲道
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(combined_audio)

    except Exception as e:
        raise ValueError(f"Error combining audio files: {e}")
