import numpy as np
import librosa
import matplotlib.pyplot as plt
import os
import glob
import noisereduce
import pretty_midi

def freq_spectrogram(audios_data, time_freqs, sample_rate):
    # 如果 audios_data 或 audios_freq 不是列表，則將它們轉換為列表
    if not isinstance(audios_data, list):
        audios_data = [audios_data]
    if not isinstance(time_freqs, list):
        time_freqs = [time_freqs]

    # 根據 audios_data 的長度動態設定子圖的大小，並保持每個子圖的長寬比例為 1:3
    fig, axs = plt.subplots(len(audios_data), 1, figsize=(15, 5*len(audios_data)))

    if len(audios_data) == 1:
        axs = [axs]

    for i, audio_data, time_freq in zip(range(len(audios_data)), audios_data, time_freqs):
        time, f0 = time_freq
        S = librosa.feature.melspectrogram(y=audio_data, sr=sample_rate, n_mels=128, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)
        img = librosa.display.specshow(S_dB, x_axis='time', y_axis='mel', sr=sample_rate, fmax=8000, ax=axs[i])
        axs[i].plot(time, f0, label='f0', color='cyan', linewidth=1)
        fig.colorbar(img, ax=axs[i], format='%+2.0f dB')
        axs[i].set(title='Mel-frequency spectrogram')

    plt.tight_layout()
    plt.show()

def midi(midis_dir):
    midis_path = glob.glob(os.path.join(midis_dir, '*.mid'))

    if not isinstance(midis_path, list):
        midis_path = [midis_path]

    fig, axs = plt.subplots(len(midis_path), 1, figsize=(15, 5*len(midis_path)))

    if len(midis_path) == 1:
        axs = [axs]

    for i, midi_path in enumerate(midis_path):
        midi_data = pretty_midi.PrettyMIDI(midi_path)

        notes = []
        for instrument in midi_data.instruments:
            for note in instrument.notes:
                notes.append((note.start, note.end, note.pitch, note.velocity))

        notes = np.array(notes)

        for start, end, pitch, velocity in notes:
            axs[i].plot([start, end], [pitch, pitch], color='black')

        axs[i].set_xlabel('Time (s)')
        axs[i].set_ylabel('Pitch')
        axs[i].set_title('MIDI Visualization')

    plt.tight_layout()
    plt.show()

def freq_spectrogram_onset(audios_data, sample_rate, onset_times, audios_freq):

    fig, axs = plt.subplots(len(audios_data), 1, figsize=(10, 10))

    for i, audio_data, audio_freq, onset_time in zip(range(len(audios_data)), audios_data, audios_freq, onset_times):
        time, f0 = audio_freq
        S = librosa.feature.melspectrogram(y=audio_data, sr=sample_rate, n_mels=128, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)
        img = librosa.display.specshow(S_dB, x_axis='time', y_axis='mel', sr=sample_rate, fmax=8000, ax=axs[i])
        axs[i].plot(time, f0, label='f0', color='cyan', linewidth=1)
        axs[i].vlines(onset_time, 0, 8000, color='green', linestyles='dashed', linewidth=1)
        fig.colorbar(img, ax=axs[i], format='%+2.0f dB')
        axs[i].set(title='Mel-frequency spectrogram')

    plt.tight_layout()
    plt.show()