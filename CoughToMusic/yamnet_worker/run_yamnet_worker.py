import sys
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
NUMBA_CACHE_DIR = BASE_DIR / ".numba_cache"
os.makedirs(NUMBA_CACHE_DIR, exist_ok=True)
os.environ.setdefault("NUMBA_CACHE_DIR", str(NUMBA_CACHE_DIR))

import numpy as np

from yamnet_loader import get_yamnet_model
from cough_cluster_core import classify_cough_file, cluster_audio
from filter_core import process_audio

def convert_ndarray_to_list(obj):
    if isinstance(obj, np.ndarray):
        if obj.size > 100:  # 陣列太大就不印了
            return f"<array shape={obj.shape}>"
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_ndarray_to_list(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_ndarray_to_list(i) for i in obj]
    return obj

def main():
    payload = json.load(sys.stdin)
    mode = payload.get("mode")

    try:
        if mode == "classify":
            res = classify_cough_file(
                cough_wav_path=payload["audio_path"],
                user_data_path=payload["user_data_path"],
                template_data_path=payload["template_data_path"],
                strict_mode=payload.get("strict_mode", True)
            )
        elif mode == "cluster":
            cluster_id = cluster_audio(
                audio_path=payload["path"],
                sample_rate=payload["sample_rate"],
                all_cough_file_path=payload["all_cough_file_path"],
                csv_file_path=payload["cough_csv_path"],
                template_path_dir=payload["template_path_dir"]
            )
            res = {"cluster_id": cluster_id}  # ✅ 包裝成字典
        elif mode == "filter":
            if payload.get("force_error", False):
                raise RuntimeError(payload.get("force_error_message") or "Forced filter worker failure")

            res = process_audio(
                audio_path=payload["audio_path"],
                sample_rate=payload.get("sample_rate"),
                write_mode=payload.get("write_mode", "mask"),
                out_dir=payload.get("out_dir"),
                keep_gain=payload.get("keep_gain", 0.9),
                apply_energy_gate=payload.get("apply_energy_gate", True),
                force_error=payload.get("force_error", False),
                force_error_message=payload.get("force_error_message")
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # ✅ 成功結果印出 JSON
        print(json.dumps(convert_ndarray_to_list(res)))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
