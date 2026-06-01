"""
Stage 1: 물고기 Segmentation 학습
- YOLO26 사용, 목표 mAP50 >= 0.85까지 자동 반복
- 실행: venv/bin/python scripts/train_seg.py
"""

import os
import shutil
from ultralytics import YOLO

TARGET_MAP50 = 0.85
MAX_ROUNDS = 5
DATA_YAML = "data/processed/segmentation/data.yaml"
MODEL_SAVE_DIR = "models/seg"
DEVICE = "cuda"

ROUND_CONFIGS = [
    {"model": "yolo26n-seg.pt", "epochs": 100, "imgsz": 640, "batch": 64, "lr0": 0.01, "patience": 20},
    {"model": "yolo26s-seg.pt", "epochs": 150, "imgsz": 640, "batch": 32, "lr0": 0.005, "patience": 30},
    {"model": None, "epochs": 100, "imgsz": 640, "batch": 32, "lr0": 0.001, "patience": 30},
    {"model": None, "epochs": 100, "imgsz": 800, "batch": 16, "lr0": 0.0005, "patience": 30},
    {"model": None, "epochs": 150, "imgsz": 800, "batch": 16, "lr0": 0.0001, "patience": 50},
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
            model_path = "yolo26n-seg.pt"

        model = YOLO(model_path)
        model.train(
            data=DATA_YAML, epochs=cfg["epochs"], imgsz=cfg["imgsz"],
            batch=cfg["batch"], lr0=cfg["lr0"], patience=cfg["patience"],
            augment=True, device=DEVICE,
            project=MODEL_SAVE_DIR, name=f"round_{r+1}", exist_ok=True,
        )

        metrics = model.val()
        current = metrics.seg.map50 if hasattr(metrics, 'seg') else metrics.box.map50
        print(f"\n  Round {r+1} mAP50 = {current:.4f}")

        if current > best_map50:
            best_map50 = current
            best_model_path = os.path.join(MODEL_SAVE_DIR, f"round_{r+1}", "weights", "best.pt")
            shutil.copy2(best_model_path, os.path.join(MODEL_SAVE_DIR, "best_seg.pt"))
            print(f"  새 최고 모델 저장: models/seg/best_seg.pt")

        if best_map50 >= TARGET_MAP50:
            print(f"\n  목표 달성! mAP50={best_map50:.4f}")
            break
        print(f"  목표 미달, 다음 라운드...")

    print(f"\n최종: mAP50={best_map50:.4f}, 모델={best_model_path}")
    return best_model_path


if __name__ == "__main__":
    train()
