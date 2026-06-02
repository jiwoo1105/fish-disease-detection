"""
Stage 1: 넙치 Detection 학습 (Roboflow 데이터)
- YOLO26-Det 사용 (물고기 bbox만 탐지)
- Roboflow 499장 → train/val 자동 분리 (80/20)
- 목표 mAP50 >= 0.85, 최대 3라운드
"""

import shutil
import random
import yaml
import torch
from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROBOFLOW_DIR  = PROJECT_ROOT / "data/fish_det_roboflow"
PROCESSED_DIR = PROJECT_ROOT / "data/processed/detection"
MODEL_SAVE_DIR = PROJECT_ROOT / "models/det"
DATA_YAML     = PROCESSED_DIR / "data.yaml"

TARGET_MAP50 = 0.85
MAX_ROUNDS   = 3
SEED         = 42
VAL_RATIO    = 0.2

DEVICE = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"

ROUND_CONFIGS = [
    {"model": "yolo26n.pt", "epochs": 100, "imgsz": 640, "batch": 32, "lr0": 0.01,  "patience": 20},
    {"model": "yolo26s.pt", "epochs": 150, "imgsz": 640, "batch": 16, "lr0": 0.005, "patience": 30},
    {"model": None,          "epochs": 100, "imgsz": 800, "batch": 8,  "lr0": 0.001, "patience": 30},
]


def split_dataset():
    """Roboflow train 폴더를 train/val로 분리"""
    src_images = ROBOFLOW_DIR / "train/images"
    src_labels = ROBOFLOW_DIR / "train/labels"

    if not src_images.exists():
        raise FileNotFoundError(f"Roboflow 데이터 없음: {src_images}")

    images = sorted(src_images.glob("*.jpg")) + sorted(src_images.glob("*.png"))
    if len(images) == 0:
        raise FileNotFoundError(f"이미지 없음: {src_images}")

    # val 폴더가 이미 있으면 스킵
    val_dir = PROCESSED_DIR / "val/images"
    if val_dir.exists() and len(list(val_dir.glob("*"))) > 0:
        print(f"  이미 분리된 데이터 존재, 스킵")
        return

    random.seed(SEED)
    random.shuffle(images)
    n_val = max(1, int(len(images) * VAL_RATIO))
    val_imgs  = images[:n_val]
    train_imgs = images[n_val:]

    print(f"  전체: {len(images)}장 → train: {len(train_imgs)}, val: {n_val}")

    for split, split_imgs in [("train", train_imgs), ("val", val_imgs)]:
        img_out = PROCESSED_DIR / split / "images"
        lbl_out = PROCESSED_DIR / split / "labels"
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for img_path in split_imgs:
            shutil.copy2(img_path, img_out / img_path.name)
            lbl_path = src_labels / (img_path.stem + ".txt")
            if lbl_path.exists():
                shutil.copy2(lbl_path, lbl_out / lbl_path.name)
            else:
                # 라벨 없으면 빈 파일 생성 (background)
                (lbl_out / (img_path.stem + ".txt")).touch()


def make_data_yaml():
    """data.yaml 생성"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "train": str(PROCESSED_DIR / "train/images"),
        "val":   str(PROCESSED_DIR / "val/images"),
        "nc":    1,
        "names": ["fish"],
    }
    with open(DATA_YAML, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    print(f"  data.yaml 생성: {DATA_YAML}")


def train():
    print("\n[1] 데이터 분리 중...")
    split_dataset()

    print("\n[2] data.yaml 생성 중...")
    make_data_yaml()

    MODEL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
    best_map50 = 0.0
    best_model_path = None

    for r in range(MAX_ROUNDS):
        cfg = ROUND_CONFIGS[r]
        print(f"\n{'='*60}")
        print(f"  Round {r+1}/{MAX_ROUNDS} | best mAP50: {best_map50:.4f} / target: {TARGET_MAP50}")
        print(f"  device={DEVICE}, imgsz={cfg['imgsz']}, batch={cfg['batch']}, epochs={cfg['epochs']}")
        print(f"{'='*60}\n")

        # 첫 라운드는 pretrained, 이후는 이전 best 모델에서 파인튜닝
        if cfg["model"]:
            model_path = cfg["model"]
        elif best_model_path:
            model_path = best_model_path
        else:
            model_path = "yolo26n.pt"

        model = YOLO(model_path)
        model.train(
            data=str(DATA_YAML),
            epochs=cfg["epochs"],
            imgsz=cfg["imgsz"],
            batch=cfg["batch"],
            lr0=cfg["lr0"],
            patience=cfg["patience"],
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
            dest = MODEL_SAVE_DIR / "best_det.pt"
            shutil.copy2(round_best, dest)
            print(f"  새 최고 모델 저장: models/det/best_det.pt (mAP50={best_map50:.4f})")

        if best_map50 >= TARGET_MAP50:
            print(f"\n  목표 달성! mAP50={best_map50:.4f}")
            break
        else:
            print(f"  목표 미달 ({best_map50:.4f} < {TARGET_MAP50}), 다음 라운드...")

    print(f"\n{'='*60}")
    print(f"최종 결과: mAP50={best_map50:.4f}")
    print(f"모델 저장 위치: models/det/best_det.pt")
    print(f"{'='*60}")
    return str(MODEL_SAVE_DIR / "best_det.pt")


if __name__ == "__main__":
    train()
