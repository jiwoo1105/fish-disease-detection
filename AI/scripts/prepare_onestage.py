"""
1-Stage 데이터 준비: 물고기 전체 bbox + 질병 클래스 라벨 생성

기존 방식: seg(병변 bbox) + cls(크롭 분류) → 2-stage
새 방식: YOLO 1개로 물고기 전체 bbox + 질병 클래스 동시 탐지

1) 이미지에서 물고기 전체 bbox 자동 생성 (배경 분리)
2) 원본 JSON에서 질병 라벨 가져오기
3) YOLO format 라벨 생성 → 학습

실행: python3 scripts/prepare_onestage.py
"""

import json
import os
import random
import zipfile
from pathlib import Path

import cv2
import numpy as np
import yaml

random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data/processed/onestage"
CONFIG_PATH = PROJECT_ROOT / "configs/classes.yaml"

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

SYMPTOM_CODE_MAP = CONFIG["symptom_code_map"]

# 1-stage 클래스 정의
CLASS_NAMES = ["normal", "hemorrhage", "white_spot", "tumor", "color_change", "emaciation", "ulcer"]
CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}

IMGSZ = 1280

# 밸런싱 타겟
BALANCE_TARGETS = {
    "normal": 3000,
    "hemorrhage": 3000,
    "white_spot": 3000,
    "tumor": 2500,
    "color_change": 3000,
    "emaciation": 2000,
    "ulcer": 1500,
}


def find_data_paths():
    data_dir = PROJECT_ROOT / "data"
    train_label = data_dir / "labels/train/TL_1. RGB Data"
    if not train_label.exists():
        train_label = data_dir / "labels/train"
    val_label = data_dir / "labels/val/VL_1. RGB Data"
    if not val_label.exists():
        val_label = data_dir / "labels/val"

    train_zip = data_dir / "TS_1.zip"
    val_zip = data_dir / "VS_1.zip"

    return {
        "train": {"label_dir": train_label, "image_zip": train_zip},
        "val": {"label_dir": val_label, "image_zip": val_zip},
    }


def get_dominant_symptom(data):
    severity = CONFIG["symptom_severity"]
    best_class = "normal"
    best_score = 0
    all_normal = True

    for ann in data.get("annotations", []):
        if ann.get("symptom_type") is not None:
            all_normal = False
        s = ann.get("symptom")
        if s is not None:
            cls_name = SYMPTOM_CODE_MAP.get(s)
            if cls_name and cls_name != "null":
                score = severity.get(cls_name, 0)
                if score > best_score:
                    best_score = score
                    best_class = cls_name

    if all_normal and best_class == "normal":
        return "normal"
    if best_class == "normal" and not all_normal:
        return None
    return best_class


def auto_detect_fish_bbox(img):
    """이미지에서 물고기 전체 bbox 자동 탐지 (배경 분리)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 여러 threshold 시도
    for thresh_val in [180, 160, 200, 140]:
        _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)

        # 노이즈 제거
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        # 가장 큰 컨투어 = 물고기
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        img_area = img.shape[0] * img.shape[1]

        # 물고기가 이미지의 10~90% 차지해야 유효
        if 0.10 < area / img_area < 0.90:
            x, y, w, h = cv2.boundingRect(largest)
            # 약간 여유 추가 (5%)
            margin_x = int(w * 0.05)
            margin_y = int(h * 0.05)
            x = max(0, x - margin_x)
            y = max(0, y - margin_y)
            w = min(img.shape[1] - x, w + 2 * margin_x)
            h = min(img.shape[0] - y, h + 2 * margin_y)
            return x, y, w, h

    return None


def classify_labels(label_dir, img_entries):
    class_data = {cls: [] for cls in CLASS_NAMES}
    skipped = 0

    files = [f for f in os.listdir(label_dir) if f.endswith('.json')]
    print(f"  라벨 파일: {len(files)}개")

    for i, fname in enumerate(files):
        if (i + 1) % 10000 == 0:
            print(f"    {i+1}/{len(files)}...")

        with open(os.path.join(label_dir, fname)) as f:
            data = json.load(f)

        image_name = data["images"][0]["file_name"]
        if image_name not in img_entries:
            continue

        cls_name = get_dominant_symptom(data)
        if cls_name is None or cls_name not in class_data:
            skipped += 1
            continue

        class_data[cls_name].append((image_name, data))

    print(f"  스킵: {skipped}개")
    for cls, items in sorted(class_data.items(), key=lambda x: -len(x[1])):
        print(f"    {cls:15s}: {len(items):5d}개")

    return class_data


def balance_classes(class_data, is_val=False):
    balanced = {}
    for cls, items in class_data.items():
        if is_val:
            balanced[cls] = items
        else:
            target = BALANCE_TARGETS.get(cls, len(items))
            if len(items) > target:
                balanced[cls] = random.sample(items, target)
            else:
                balanced[cls] = items

    print(f"\n  밸런싱 후:")
    for cls, items in sorted(balanced.items(), key=lambda x: -len(x[1])):
        print(f"    {cls:15s}: {len(items):5d}개")
    return balanced


def process_split(split, label_dir, image_zip):
    print(f"\n{'='*50}")
    print(f"  [{split.upper()}] 1-Stage 데이터 준비")
    print(f"{'='*50}")

    if not label_dir.exists():
        print(f"  라벨 없음: {label_dir}")
        return
    if not image_zip.exists():
        print(f"  이미지 zip 없음: {image_zip}")
        return

    # zip 인덱싱
    print("  이미지 zip 인덱싱...")
    img_entries = {}
    with zipfile.ZipFile(image_zip) as iz:
        for entry in iz.namelist():
            base = os.path.splitext(os.path.basename(entry))[0]
            if base:
                img_entries[base] = entry
    print(f"  zip 내 이미지: {len(img_entries)}개")

    # 라벨 분류
    class_data = classify_labels(label_dir, img_entries)

    # 밸런싱
    is_val = (split == "val")
    balanced = balance_classes(class_data, is_val=is_val)

    # 디렉토리 생성
    img_dir = OUT_DIR / split / "images"
    lbl_dir = OUT_DIR / split / "labels"
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(lbl_dir, exist_ok=True)

    # 이미지 추출 + 자동 bbox + 라벨 생성
    all_items = []
    for cls_name, items in balanced.items():
        for img_name, data in items:
            all_items.append((img_name, data, cls_name))

    print(f"\n  총 처리할 이미지: {len(all_items)}개")

    success = 0
    fail_bbox = 0
    class_counts = {cls: 0 for cls in CLASS_NAMES}

    with zipfile.ZipFile(image_zip) as iz:
        for idx, (image_name, data, cls_name) in enumerate(all_items):
            entry = img_entries.get(image_name)
            if not entry:
                continue

            img_path = img_dir / (image_name + ".JPG")
            lbl_path = lbl_dir / (image_name + ".txt")

            if img_path.exists() and lbl_path.exists():
                success += 1
                class_counts[cls_name] += 1
                continue

            # 이미지 읽기
            with iz.open(entry) as src:
                img_bytes = src.read()

            arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue

            # 리사이즈
            img = cv2.resize(img, (IMGSZ, IMGSZ))

            # 자동 bbox 탐지
            bbox = auto_detect_fish_bbox(img)
            if bbox is None:
                fail_bbox += 1
                continue

            x, y, w, h = bbox
            cls_id = CLASS_TO_ID[cls_name]

            # YOLO format (normalized)
            xc = (x + w / 2) / IMGSZ
            yc = (y + h / 2) / IMGSZ
            nw = w / IMGSZ
            nh = h / IMGSZ

            # 이미지 저장
            cv2.imwrite(str(img_path), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

            # 라벨 저장
            with open(lbl_path, "w") as f:
                f.write(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")

            success += 1
            class_counts[cls_name] += 1

            if (idx + 1) % 500 == 0:
                print(f"    {idx+1}/{len(all_items)} 처리... (성공: {success}, bbox실패: {fail_bbox})")

    print(f"\n  결과: 성공 {success}, bbox 탐지 실패 {fail_bbox}")
    for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
        print(f"    {cls:15s}: {cnt}")


def create_data_yaml():
    yaml_content = {
        "path": str(OUT_DIR.resolve()),
        "train": "train/images",
        "val": "val/images",
        "names": {i: name for i, name in enumerate(CLASS_NAMES)},
    }
    with open(OUT_DIR / "data.yaml", "w") as f:
        yaml.dump(yaml_content, f, default_flow_style=False)
    print(f"\n  data.yaml 생성: {OUT_DIR / 'data.yaml'}")


def main():
    print("=" * 50)
    print("  1-Stage 데이터 준비 (물고기 전체 bbox + 질병 클래스)")
    print("=" * 50)

    SPLITS = find_data_paths()
    for split, cfg in SPLITS.items():
        process_split(split, cfg["label_dir"], cfg["image_zip"])

    create_data_yaml()

    print(f"\n{'='*50}")
    print("  최종 결과")
    print(f"{'='*50}")
    for split in ["train", "val"]:
        imgs = len(list((OUT_DIR / split / "images").glob("*.JPG")))
        lbls = len(list((OUT_DIR / split / "labels").glob("*.txt")))
        print(f"  [{split}] {imgs} images / {lbls} labels")

    os.system(f"du -sh {OUT_DIR}")


if __name__ == "__main__":
    main()
