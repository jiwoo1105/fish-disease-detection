"""
1-Stage 학습: 물고기 전체 bbox + 질병 클래스 동시 탐지
7 classes: normal, hemorrhage, white_spot, tumor, color_change, emaciation, ulcer

실행: python3 scripts/train_onestage.py
"""

import os
import shutil
import torch
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGET_MAP50 = 0.70
MAX_ROUNDS = 3
DATA_YAML = str(PROJECT_ROOT / "data/processed/onestage/data.yaml")
MODEL_SAVE_DIR = str(PROJECT_ROOT / "models/onestage")
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

ROUND_CONFIGS = [
    {"model": "yolo11n.pt", "epochs": 100, "imgsz": 640, "batch": 32, "lr0": 0.01, "patience": 20},
    {"model": "yolo11s.pt", "epochs": 150, "imgsz": 640, "batch": 16, "lr0": 0.005, "patience": 30},
    {"model": None, "epochs": 150, "imgsz": 800, "batch": 16, "lr0": 0.001, "patience": 40},
]


def train():
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    best_map50 = 0.0
    best_model_path = None

    for r in range(MAX_ROUNDS):
        cfg = ROUND_CONFIGS[r]
        print(f"\n{'='*60}")
        print(f"  Round {r+1}/{MAX_ROUNDS} | best mAP50: {best_map50:.4f} / target: {TARGET_MAP50}")
        print(f"{'='*60}\n")

        model_path = cfg["model"] if cfg["model"] else best_model_path
        if model_path is None:
            model_path = "yolo11n.pt"

        model = YOLO(model_path)
        model.train(
            data=DATA_YAML, epochs=cfg["epochs"], imgsz=cfg["imgsz"],
            batch=cfg["batch"], lr0=cfg["lr0"], patience=cfg["patience"],
            augment=True, device=DEVICE,
            project=MODEL_SAVE_DIR, name=f"round_{r+1}", exist_ok=True,
        )

        metrics = model.val()
        current = metrics.box.map50
        print(f"\n  Round {r+1} mAP50 = {current:.4f}")

        if current > best_map50:
            best_map50 = current
            best_model_path = os.path.join(MODEL_SAVE_DIR, f"round_{r+1}", "weights", "best.pt")
            shutil.copy2(best_model_path, os.path.join(MODEL_SAVE_DIR, "best_onestage.pt"))
            print(f"  새 최고 모델 저장: models/onestage/best_onestage.pt")

        if best_map50 >= TARGET_MAP50:
            print(f"\n  목표 달성! mAP50={best_map50:.4f}")
            break
        print(f"  목표 미달, 다음 라운드...")

    print(f"\n최종: mAP50={best_map50:.4f}, 모델={best_model_path}")
    return best_model_path


if __name__ == "__main__":
    train()
