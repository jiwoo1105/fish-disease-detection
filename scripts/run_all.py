"""
전체 파이프라인: 데이터 준비 → Seg 학습 → Cls 학습
실행: venv/bin/python scripts/run_all.py
"""

import subprocess, sys, time, os
from pathlib import Path
from datetime import datetime

LOG = "run_all.log"
# venv python 경로 자동 탐색
VENV_PYTHON = str(Path(__file__).resolve().parent.parent / "venv" / "bin" / "python")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def run(name, script):
    log(f"=== {name} 시작 ===")
    t = time.time()
    r = subprocess.run([VENV_PYTHON, script])
    m = (time.time() - t) / 60
    ok = r.returncode == 0
    log(f"=== {name} {'완료' if ok else '실패'} ({m:.1f}분) ===")
    return ok

def main():
    log("=" * 50)
    log(f"파이프라인 시작 | Python: {VENV_PYTHON}")
    log("=" * 50)

    if not run("데이터 준비", "scripts/prepare_multiclass.py"):
        log("데이터 준비 실패. 중단."); return

    if not run("Stage 1: Fish Seg", "scripts/train_seg.py"):
        log("Seg 실패. Cls로 진행.")

    if not run("Stage 2: Symptom Cls", "scripts/train_cls.py"):
        log("Cls 실패.")

    log("=" * 50)
    log("파이프라인 완료!")
    log("=" * 50)

if __name__ == "__main__":
    main()
