import os
from pathlib import Path

import pandas as pd
from django.conf import settings


def execute_generation_mode(job):
    if job.mode == "normal":
        return _run_normal(job)
    if job.mode == "trio":
        return _run_trio(job)
    if job.mode == "trio_manual":
        return _run_trio_manual(job)
    if job.mode == "drum_manual":
        return _run_drum_manual(job)
    if job.mode == "drum":
        return _run_drum(job)
    raise ValueError(f"Unsupported mode: {job.mode}")


def _run_normal(job):
    from ..util import generate_music

    generate_path = generate_music(
        job.data["user_id"],
        job.file_path,
        job.uuid,
        job.data["bass"].lower(),
        job.data["alto"].lower(),
        job.data["high"].lower(),
    )
    return {
        "generate_path": generate_path,
        "cough_paths": [str(path) for path in job.coughlist],
    }


def _run_trio(job):
    from ..co_create_utils import cough2midi, gen_trio_mid, gen_trio_trk

    user_id = job.data["user_id"]
    cough_path = str(job.coughlist[0])
    filename = os.path.splitext(os.path.basename(cough_path))[0]
    user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, "temp_trio")
    os.makedirs(user_tmp_folder, exist_ok=True)

    cough_table_path = os.path.join(settings.MEDIA_ROOT, user_id, "cough_audio", "cough_table.csv")
    df = pd.read_csv(cough_table_path)
    match = df[df["filename"] == filename + ".wav"]
    pub_cough_id = int(match.iloc[0]["pubCoughID"])

    generate_path_triomotif = Path(cough2midi(pub_cough_id, "string", user_tmp_folder, job.uuid, sample_rate=16000))
    used_cough_paths, used_motif_paths = gen_trio_mid(pub_cough_id)
    generate_path_trio = gen_trio_trk(pub_cough_id, "string", user_tmp_folder, job.uuid, sample_rate=16000)
    return {
        "cough_paths": [str(path) for path in job.coughlist],
        "cough_motifs": [str(generate_path_triomotif)],
        "used_public_paths": [str(path) for path in used_cough_paths],
        "used_motif_paths": [str(path) for path in used_motif_paths],
        "generated_music": generate_path_trio,
    }


def _run_trio_manual(job):
    from ..co_create_utils import cough2mid_manual, gen_trio_manual, gen_trio_trk_manual

    user_id = job.data["user_id"]
    user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, "temp_manual_trio")
    os.makedirs(user_tmp_folder, exist_ok=True)

    mid_dic = {"mel": [], "acc": [], "bass": []}
    merged_trio_motif_wavs = []
    for filename in job.coughlist:
        trio_wav = cough2mid_manual(filename, user_tmp_folder, mid_dic)
        merged_trio_motif_wavs.append(trio_wav)

    gen_trio_manual(user_tmp_folder, mid_dic, job.uuid)
    generated_manual_trio = gen_trio_trk_manual(user_tmp_folder, job.uuid, sample_rate=16000)
    return {
        "cough_paths": [str(path) for path in job.coughlist],
        "cough_motifs": [str(path) for path in merged_trio_motif_wavs],
        "generated_music": generated_manual_trio,
    }


def _run_drum_manual(job):
    from ..co_create_utils import generate_groove_intp_manual

    user_id = job.data["user_id"]
    user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, "temp_manual_drum")
    os.makedirs(user_tmp_folder, exist_ok=True)

    generated_manual_drum, drum_motif_wavs = generate_groove_intp_manual(job.coughlist, user_tmp_folder, job.uuid)
    return {
        "cough_paths": [str(path) for path in job.coughlist],
        "cough_motifs": [os.path.join(settings.BASE_DIR, str(path)) for path in drum_motif_wavs],
        "generated_music": generated_manual_drum,
    }


def _run_drum(job):
    from ..co_create_utils import generate_groove_intp_autofill

    user_id = job.data["user_id"]
    user_tmp_folder = os.path.join(settings.MEDIA_ROOT, user_id, "temp_autofill_drum")
    os.makedirs(user_tmp_folder, exist_ok=True)
    public_base = os.path.abspath(settings.PUBLIC_COUGH)

    generate_path_drum, used_public_paths, drum_motif_wavs = generate_groove_intp_autofill(
        job.coughlist,
        settings.PUBLIC_COUGH,
        user_tmp_folder,
        job.uuid,
    )
    return {
        "cough_paths": [str(path) for path in job.coughlist],
        "cough_motifs": [str(path) for path in drum_motif_wavs[: len(job.coughlist)]],
        "used_public_paths": [
            str(path) for path in used_public_paths if os.path.abspath(path).startswith(public_base)
        ],
        "used_motif_paths": [os.path.join(settings.BASE_DIR, str(path)) for path in drum_motif_wavs[len(job.coughlist) :]],
        "generated_music": generate_path_drum,
    }
