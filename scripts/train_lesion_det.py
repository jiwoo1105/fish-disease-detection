"""
병변 탐지 모델 학습 (AIHub 데이터)
prepare_lesion_det.py 실행 후 사용

사용법:
  python scripts/train_lesion_det.py
"""

import shutil
import torch
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_YAML     = PROJECT_ROOT / "data/processed/lesion_det/data.yaml"
MODEL_SAVE_DIR = PROJECT_ROOT / "models/lesion_det"
TARGET_MAP50  = 0.50   # 병변 탐지는 난이도 높아 목표를 낮게 설정
MAX_ROUNDS    = 3

DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

ROUND_CONFIGS = [
    {"model": "yolo26n.pt", "epochs": 100, "imgsz": 640,  "batch": 32, "lr0": 0.01,  "patience": 20},
    {"model": "yolo26s.pt", "epochs": 150, "imgsz": 640,  "batch": 16, "lr0": 0.005, "patience": 30},
    {"model": None,          "epochs": 100, "imgsz": 1280, "batch": 2,  "lr0": 0.001, "patience": 30, "workers": 4},
]


def train():
    if not DATA_YAML.exists():
        print(f"ERROR: data.yaml 없음. 먼저 prepare_lesion_det.py를 실행하세요.")
        print(f"  python scripts/prepare_lesion_det.py --image-dir /path/to/images")
        return

    MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    best_map50 = 0.0
    best_model_path = None

    for r in range(MAX_ROUNDS):
        cfg = ROUND_CONFIGS[r]
        print(f"\n{'='*60}")
        print(f"  Round {r+1}/{MAX_ROUNDS} | best mAP50: {best_map50:.4f} / target: {TARGET_MAP50}")
        print(f"  device={DEVICE}, imgsz={cfg['imgsz']}, batch={cfg['batch']}")
        print(f"{'='*60}\n")

        model_path = cfg["model"] if cfg["model"] else (best_model_path or "yolo26n.pt")
        model = YOLO(model_path)
        model.train(
            data=str(DATA_YAML),
            epochs=cfg["epochs"],
            imgsz=cfg["imgsz"],
            batch=cfg["batch"],
            lr0=cfg["lr0"],
            patience=cfg["patience"],
            workers=cfg.get("workers", 8),
            augment=True,
            device=DEVICE,
            project=str(MODEL_SAVE_DIR),
            name=f"round_{r+1}",
            exist_ok=True,
        )

        metrics = model.val()
        current = float(metrics.box.map50)
        print(f"\n  Round {r+1} mAP50 = {current:.4f}")

        if current > best_map50:
            best_map50 = current
            round_best = MODEL_SAVE_DIR / f"round_{r+1}/weights/best.pt"
            best_model_path = str(round_best)
            dest = MODEL_SAVE_DIR / "best_lesion_det.pt"
            shutil.copy2(round_best, dest)
            print(f"  새 최고 모델 저장: models/lesion_det/best_lesion_det.pt")

        if best_map50 >= TARGET_MAP50:
            print(f"\n  목표 달성!")
            break

    print(f"\n최종 mAP50={best_map50:.4f} → models/lesion_det/best_lesion_det.pt")


if __name__ == "__main__":
    train()
