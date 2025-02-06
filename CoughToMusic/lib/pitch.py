import crepe
import numpy as np

def analyze_pitch(audio_data, sr ,threshold=0.5):
    print("Estimating pitch with CREPE...")
    _, frequency, confidence, _ = crepe.predict(audio_data, sr=sr, viterbi=True)
    frequency = np.where(confidence < threshold, np.nan, frequency)
    return frequency


