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
               min_target, max_target, energy_th, tried_fallback=False):
    import audio
    import midi
    from cough_to_midi import freq

    cough_data, sample_rate = audio.load_from_file(cough_pth)
    cough_data, _ = select_analysis_window(cough_data, sample_rate)
    
    cough_freq = freq.get_by_crepe(cough_data, sample_rate, threshold, energy_threshold=energy_th)
    # print(f"cough_freq: {cough_freq}")

    if not cough_freq:
        if tried_fallback:
            logger.warning("No frequency detected even with fallback threshold. Aborting.")
            return False
        logger.warning("No frequency detected in the cough audio. Retrying with fallback threshold = 0.1.")
        return cough2midi(cough_pth, motif_pth, 0.1, freq_range_th, note_interval_th,
                          min_target, max_target, energy_th, tried_fallback=True)
    
    success = freq.write_midi(cough_data, sample_rate, cough_freq, motif_pth,
                              min_target, max_target, freq_range_th, note_interval_th)
    
    if not success:
        if tried_fallback:
            logger.warning("write_midi failed even with fallback threshold. Aborting.")
            return False
        logger.warning("write_midi failed. Retrying with fallback threshold = 0.2.")
        return cough2midi(cough_pth, motif_pth, 0.2, freq_range_th, note_interval_th,
                          min_target, max_target, energy_th, tried_fallback=True)

    midi.to_2bars(motif_pth, motif_pth)
    return True

def correct_key(melody_pth, ref_pth):
    import midi

    midi.correct_midi_to_ref_key(ref_pth, melody_pth)
            
