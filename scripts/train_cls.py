"""
Stage 2: 다중 증상 분류 학습
- YOLO26-Cls 7 classes, 목표 Accuracy >= 85%까지 자동 반복
- 실행: venv/bin/python scripts/train_cls.py
"""

import os
import shutil
import torch
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TARGET_ACCURACY = 0.90
MAX_ROUNDS = 5
DATA_DIR = str(PROJECT_ROOT / "data/processed/classification")
MODEL_SAVE_DIR = str(PROJECT_ROOT / "models/cls")
DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

ROUND_CONFIGS = [
    {"model": "yolo26n-cls.pt", "epochs": 50, "imgsz": 224, "batch": 256, "lr0": 0.01, "patience": 15},
    {"model": "yolo26s-cls.pt", "epochs": 80, "imgsz": 224, "batch": 128, "lr0": 0.005, "patience": 20},
    {"model": None, "epochs": 80, "imgsz": 320, "batch": 64, "lr0": 0.001, "patience": 25},
    {"model": None, "epochs": 100, "imgsz": 448, "batch": 32, "lr0": 0.0005, "patience": 30},
    {"model": None, "epochs": 100, "imgsz": 448, "batch": 32, "lr0": 0.0001, "patience": 40},
]


def train():
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    best_acc = 0.0
    best_model_path = None

    for r in range(MAX_ROUNDS):
        cfg = ROUND_CONFIGS[r]
        print(f"\n{'='*60}")
        print(f"  Round {r+1}/{MAX_ROUNDS} | best Acc: {best_acc:.4f} / target: {TARGET_ACCURACY}")
        print(f"{'='*60}\n")

        model_path = cfg["model"] if cfg["model"] else (best_model_path or "yolo26n-cls.pt")

        model = YOLO(model_path)
        model.train(
            data=DATA_DIR, epochs=cfg["epochs"], imgsz=cfg["imgsz"],
            batch=cfg["batch"], lr0=cfg["lr0"], patience=cfg["patience"],
            augment=True,
            device=DEVICE,
            project=MODEL_SAVE_DIR, name=f"round_{r+1}", exist_ok=True,
        )

        metrics = model.val()
        current = metrics.top1
        print(f"\n  Round {r+1} Accuracy = {current:.4f}")

        if current > best_acc:
            best_acc = current
            best_model_path = os.path.join(MODEL_SAVE_DIR, f"round_{r+1}", "weights", "best.pt")
            shutil.copy2(best_model_path, os.path.join(MODEL_SAVE_DIR, "best_cls.pt"))
            print(f"  새 최고 모델 저장: models/cls/best_cls.pt")

        if best_acc >= TARGET_ACCURACY:
            print(f"\n  목표 달성! Accuracy={best_acc:.4f}")
            break
        print(f"  목표 미달, 다음 라운드...")

    print(f"\n최종: Accuracy={best_acc:.4f}, 모델={best_model_path}")
    return best_model_path


if __name__ == "__main__":
    train()
