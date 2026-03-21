from __future__ import annotations

import os
import random
from pathlib import Path

from django.conf import settings

from .storage import (
    get_public_cough_path,
    get_public_motif_mid_path,
    get_public_motif_wav_path,
    get_public_track_mid_path,
    get_public_track_wav_path,
    list_public_motif_mid_names,
)
from .workflow_common import ACC_CONFIG, BASS_CONFIG, INSTRUMENT_PROGRAMS, MEL_CONFIG, TRACKS


def generate_public_trio_motif(pub_cough_id: int, user_id: str, job_uuid: str) -> str:
    from .lib import cough2mid, midi
    import librosa
    import numpy as np
    import soundfile as sf

    public_cough_path = str(get_public_cough_path(pub_cough_id))
    mel_mtf = str(get_public_motif_mid_path("mel", pub_cough_id))
    acc_mtf = str(get_public_motif_mid_path("acc", pub_cough_id))
    bass_mtf = str(get_public_motif_mid_path("bass", pub_cough_id))

    cough2mid.cough2midi(public_cough_path, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf, mel_mtf)
    cough2mid.cough2midi(public_cough_path, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf, acc_mtf)
    cough2mid.cough2midi(public_cough_path, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf, bass_mtf)

    midi_paths = {"mel": mel_mtf, "acc": acc_mtf, "bass": bass_mtf}
    wav_paths = {track: str(get_public_motif_wav_path(track, pub_cough_id)) for track in TRACKS}
    merged_output_path = str(Path(settings.MOTIF_TRIO_WAV) / f"trio_{pub_cough_id}.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = midi_paths[track]
        wav_path = wav_paths[track]
        tmp_mid_pth = os.path.join(settings.MEDIA_ROOT, user_id, f"{job_uuid}_{track}_short_trio.mid")
        midi.update_midi_program(midi_path, tmp_mid_pth, program_number=program)
        midi.write_from_midi(tmp_mid_pth, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path


def generate_trio_midi_sequence(pub_cough_id: int) -> tuple[list[str], list[str]]:
    from .lib.generation import generate_melody_from_sequence

    midi_files = [filename for filename in list_public_motif_mid_names("mel") if filename != f"mel_{pub_cough_id}.mid"]
    selected = random.sample(midi_files, 2)

    def extract_id(filename: str) -> int:
        return int(filename.replace("mel_", "").replace(".mid", ""))

    sequence = [pub_cough_id] + [extract_id(filename) for filename in selected]
    print(f"MIDI sequence: {sequence}")

    for track in TRACKS:
        sequence_paths = [str(get_public_motif_mid_path(track, item_id)) for item_id in sequence]
        output_mid = str(get_public_track_mid_path(track, pub_cough_id))
        generate_melody_from_sequence(sequence_paths, output_mid)

    used_cough_paths = [str(get_public_cough_path(item_id)) for item_id in sequence if str(item_id) != str(pub_cough_id)]
    used_motif_paths = [
        str(Path(settings.MOTIF_TRIO_WAV) / f"trio_{item_id}.wav")
        for item_id in sequence
        if str(item_id) != str(pub_cough_id)
    ]
    return used_cough_paths, used_motif_paths


def render_public_trio_tracks(pub_cough_id: int, user_id: str, job_uuid: str, user_tmp_folder: str) -> str:
    from .lib import midi
    import librosa
    import numpy as np
    import soundfile as sf

    merged_output_path = os.path.join(user_tmp_folder, f"{job_uuid}_trio.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = str(get_public_track_mid_path(track, pub_cough_id))
        wav_path = str(get_public_track_wav_path(track, pub_cough_id))
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path


def build_manual_trio_motif(cough_path: Path, user_folder: str, mid_dic: dict[str, list[str]]) -> str:
    from .lib import cough2mid, midi
    import librosa
    import numpy as np
    import soundfile as sf

    cough_name = cough_path.stem
    mel_mtf = os.path.join(user_folder, f"{cough_name}_mel_mtf.mid")
    acc_mtf = os.path.join(user_folder, f"{cough_name}_acc_mtf.mid")
    bass_mtf = os.path.join(user_folder, f"{cough_name}_bass_mtf.mid")
    cough_str = str(cough_path)

    cough2mid.cough2midi(cough_str, mel_mtf, **MEL_CONFIG)
    cough2mid.correct_key(mel_mtf, mel_mtf)
    mid_dic["mel"].append(mel_mtf)
    cough2mid.cough2midi(cough_str, acc_mtf, **ACC_CONFIG)
    cough2mid.correct_key(acc_mtf, acc_mtf)
    mid_dic["acc"].append(acc_mtf)
    cough2mid.cough2midi(cough_str, bass_mtf, **BASS_CONFIG)
    cough2mid.correct_key(bass_mtf, bass_mtf)
    mid_dic["bass"].append(bass_mtf)

    midi.update_midi_program(
        mel_mtf,
        os.path.join(user_folder, f"{cough_name}_mel_motif.mid"),
        program_number=INSTRUMENT_PROGRAMS["mel"],
    )
    midi.update_midi_program(
        acc_mtf,
        os.path.join(user_folder, f"{cough_name}_acc_motif.mid"),
        program_number=INSTRUMENT_PROGRAMS["acc"],
    )
    midi.update_midi_program(
        bass_mtf,
        os.path.join(user_folder, f"{cough_name}_bass_motif.mid"),
        program_number=INSTRUMENT_PROGRAMS["bass"],
    )

    mel_wav = os.path.join(user_folder, f"{cough_name}_mel_mtf.wav")
    acc_wav = os.path.join(user_folder, f"{cough_name}_acc_mtf.wav")
    bass_wav = os.path.join(user_folder, f"{cough_name}_bass_mtf.wav")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_mel_motif.mid"), mel_wav, "violin")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_acc_motif.mid"), acc_wav, "violin")
    midi.write_from_midi(os.path.join(user_folder, f"{cough_name}_bass_motif.mid"), bass_wav, "violin")

    mel, _ = librosa.load(mel_wav, sr=16000)
    acc, _ = librosa.load(acc_wav, sr=16000)
    bass, _ = librosa.load(bass_wav, sr=16000)
    max_length = max(len(mel), len(acc), len(bass))
    mel = np.pad(mel, (0, max_length - len(mel)), "constant")
    acc = np.pad(acc, (0, max_length - len(acc)), "constant")
    bass = np.pad(bass, (0, max_length - len(bass)), "constant")
    merged = mel + acc + bass
    trio_wav = os.path.join(user_folder, f"{cough_name}_trio_mtf.wav")
    sf.write(trio_wav, merged, 16000)
    return trio_wav


def generate_manual_trio_sequence(user_folder: str, mid_dic: dict[str, list[str]], job_uuid: str) -> None:
    from .lib.generation import generate_melody_from_sequence

    for track in TRACKS:
        intrp_mid_pth = os.path.join(user_folder, f"{job_uuid}_{track}_trio.mid")
        generate_melody_from_sequence(mid_dic[track], intrp_mid_pth)


def render_manual_trio_tracks(user_folder: str, job_uuid: str) -> str:
    from .lib import midi
    import librosa
    import numpy as np
    import soundfile as sf

    merged_output_path = os.path.join(user_folder, f"{job_uuid}_trio.wav")
    audio: dict[str, np.ndarray] = {}

    for track, program in INSTRUMENT_PROGRAMS.items():
        midi_path = os.path.join(user_folder, f"{job_uuid}_{track}_trio.mid")
        wav_path = os.path.join(user_folder, f"{job_uuid}_{track}_trio.wav")
        midi.update_midi_program(midi_path, midi_path, program_number=program)
        midi.write_from_midi(midi_path, wav_path, "violin")
        audio[track], _ = librosa.load(wav_path, sr=16000)

    max_length = max(len(samples) for samples in audio.values())
    merged_audio = sum(np.pad(samples, (0, max_length - len(samples)), "constant") for samples in audio.values())
    sf.write(merged_output_path, merged_audio, 16000)
    print(f"Saved output path: {merged_output_path}")
    return merged_output_path
