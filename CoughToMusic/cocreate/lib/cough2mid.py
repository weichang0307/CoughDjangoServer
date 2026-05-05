import logging
from pathlib import Path
from CoughToMusic.windowing import select_analysis_window

logger = logging.getLogger(__name__)

def cough_to_midi_wavs(
    threshold, freq_range_th, note_interval_th, min_target, max_target, energy_th, folder_path, out_dir):
    import audio
    import midi
    from cough_to_midi import freq

    recorded_coughs = Path("recorded_coughs").glob("cough_*.wav")
    for cough in recorded_coughs:
        cough = str(cough)
        cough_data, sample_rate = audio.load_from_file(cough)
        cough_data, _ = select_analysis_window(cough_data, sample_rate)
        file_index = cough.split("_")[-1].split(".")[0]
        cough_freq = freq.get_by_crepe(cough_data, sample_rate, threshold, energy_threshold=energy_th)
        # midi_file = f"./{out_dir}/{folder_path}_mid/{folder_path}_{file_index}.mid"
        midi_file = str(Path(out_dir) / f"{folder_path}_mid" / f"{folder_path}_{file_index}.mid")
        freq.write_midi(cough_data,sample_rate,cough_freq,midi_file,min_target,max_target,freq_range_th,note_interval_th)
        if (freq.write_midi(cough_data,sample_rate,cough_freq,midi_file,min_target,max_target,freq_range_th,note_interval_th)== False):
                continue
        else:
            midi_2bars = midi.to_2bars(midi_file, midi_file )  
            midi_2bars.save(midi_file)
            # midi.quantize_midi(midi_file, midi_file, num)  # quantize the midi
            # output_path = f"{out_dir}/{folder_path}_wav/{folder_path}_{file_index}.wav"  # write the coughs to wav
            if folder_path == "mel":
                midi.correct_midi_to_ref_key(midi_file, midi_file)
            else:
                ref_file = str(Path(out_dir) / "mel_mid" / f"mel_{file_index}.mid")
                midi.correct_midi_to_ref_key(ref_file, midi_file)
            output_path = str(Path(out_dir) / f"{folder_path}_wav" / f"{folder_path}_{file_index}.wav")
            midi.write_from_midi(midi_file, output_path, "piano")


def cough2midi(cough_pth, motif_pth, threshold, freq_range_th, note_interval_th,
               min_target, max_target, energy_th):
    import audio
    import midi
    from cough_to_midi import freq

    cough_data, sample_rate = audio.load_from_file(cough_pth)
    cough_data, _ = select_analysis_window(cough_data, sample_rate)

    # Run CREPE once; reuse cached output for fallback instead of re-running inference.
    crepe_time, crepe_raw_freq, crepe_confidence = freq.predict_crepe(cough_data, sample_rate)

    cough_freq = freq.apply_crepe_threshold(
        crepe_time, crepe_raw_freq, crepe_confidence, threshold,
        energy_threshold=energy_th, audio_data=cough_data, sr=sample_rate)
    success = freq.write_midi(cough_data, sample_rate, cough_freq, motif_pth,
                              min_target, max_target, freq_range_th, note_interval_th)

    if not success:
        logger.warning("write_midi failed. Retrying with fallback threshold=0.1 on cached CREPE output.")
        cough_freq = freq.apply_crepe_threshold(
            crepe_time, crepe_raw_freq, crepe_confidence, 0.1,
            energy_threshold=energy_th, audio_data=cough_data, sr=sample_rate)
        success = freq.write_midi(cough_data, sample_rate, cough_freq, motif_pth,
                                  min_target, max_target, freq_range_th, note_interval_th)
        if not success:
            logger.warning("Fallback also failed. Aborting.")
            return False

    midi.to_2bars(motif_pth, motif_pth)
    return True

def correct_key(melody_pth, ref_pth):
    import midi

    midi.correct_midi_to_ref_key(ref_pth, melody_pth)
            
