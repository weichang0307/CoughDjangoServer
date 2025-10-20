# utils/runner.py
import json
import subprocess
import uuid
from pathlib import Path

def run_cli(python_exe, entry_py, payload: dict, timeout: int = 900, cwd: str = None, enable_log: bool = True):
    job_id = payload.get("uuid") or str(uuid.uuid4())
    log_dir = Path(cwd or ".") / "media" / "logs" / "jobs"
    log_file = log_dir / f"{job_id}.log"

    # 建立 log 目錄（只有在啟用時才建）
    if enable_log:
        log_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.run(
            [python_exe, entry_py],
            input=json.dumps(payload).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
    except subprocess.TimeoutExpired:
        if enable_log:
            log_file.write_text("TIMEOUT\n", encoding="utf-8")
        return {
            "ok": False,
            "returncode": None,
            "json": None,
            "stdout": "",
            "stderr": "",
            "log_file": str(log_file) if enable_log else None,
            "error": "Worker timed out",
        }

    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    if enable_log:
        with open(log_file, "w", encoding="utf-8") as f:
            if stdout:
                f.write("=== STDOUT ===\n")
                f.write(stdout)
                f.write("\n")
            if stderr:
                f.write("=== STDERR ===\n")
                f.write(stderr)
                f.write("\n")

    parsed = None
    for line in reversed([ln for ln in stdout.splitlines() if ln.strip()]):
        try:
            parsed = json.loads(line)
            break
        except Exception:
            continue

    ok = (proc.returncode == 0) and (parsed is not None)

    return {
        "ok": ok,
        "returncode": proc.returncode,
        "json": parsed,
        "stdout": stdout,
        "stderr": stderr,
        "log_file": str(log_file) if enable_log else None,
        "error": None if ok else ("Invalid JSON from worker" if parsed is None else "Worker returned non-zero exit"),
    }
