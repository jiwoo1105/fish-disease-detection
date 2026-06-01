"""
다중 클래스 데이터 준비 스크립트

AIHub 넙치 질병 데이터에서 7개 증상 클래스로 분류하고,
Segmentation + Classification 학습용 데이터셋을 구성.

- 이미지 추출 시 리사이즈 (6000x4000 → 1280x1280) → 디스크 절약
- 클래스 밸런싱 (다운샘플링 + 증강 예정)
- Cls 이미지는 bbox 크롭 → 224x224

실행: venv/bin/python scripts/prepare_multiclass.py
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

# ============================================================
# 설정 로드
# ============================================================
BASE_DIR = Path("data/301.넙치 질병 데이터/01-1.정식개방데이터")
SEG_DIR = Path("data/processed/segmentation")
CLS_DIR = Path("data/processed/classification")
CONFIG_PATH = Path("configs/classes.yaml")

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

SYMPTOM_CODE_MAP = CONFIG["symptom_code_map"]
BALANCE_TARGETS = CONFIG["balance_targets"]
SEG_IMGSZ = 1280  # seg용 리사이즈
CLS_IMGSZ = 224   # cls용 크롭 리사이즈

SPLITS = {
    "train": {
        "label_dir": BASE_DIR / "Training/02.라벨링데이터/TL_1. RGB Data",
        "image_zip": BASE_DIR / "Training/01.원천데이터/TS_1. RGB Data_1.zip",
    },
    "val": {
        "label_dir": BASE_DIR / "Validation/02.라벨링데이터/VL_1. RGB Data",
        "image_zip": BASE_DIR / "Validation/01.원천데이터/VS_1. RGB Data.zip",
    },
}


def get_dominant_symptom(data):
    """이미지의 annotations에서 가장 심각한 증상 클래스를 반환"""
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
        return None  # 증상이 있지만 매핑 안 되는 경우 → 제외

    return best_class


def classify_labels(label_dir, img_entries):
    """라벨 파일을 클래스별로 분류 (zip에 이미지 있는 것만)"""
    class_data = {cls: [] for cls in BALANCE_TARGETS}
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

    print(f"  스킵: {skipped}개 (매핑 안 됨)")
    for cls, items in sorted(class_data.items(), key=lambda x: -len(x[1])):
        print(f"    {cls:15s}: {len(items):5d}개")

    return class_data


def balance_classes(class_data, is_val=False):
    """클래스 밸런싱 (다운샘플링)"""
    balanced = {}
    for cls, items in class_data.items():
        if is_val:
            # val은 밸런싱 안 함, 전부 사용
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


def resize_image_bytes(img_bytes, target_size):
    """이미지 바이트 → 리사이즈 → 바이트"""
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    img = cv2.resize(img, (target_size, target_size))
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def crop_fish(img_bytes, bbox, orig_w, orig_h, target_size=CLS_IMGSZ):
    """이미지에서 물고기 영역 크롭 + 리사이즈"""
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    x_min, y_min, x_max, y_max = [int(v) for v in bbox]
    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(img.shape[1], x_max)
    y_max = min(img.shape[0], y_max)

    if x_max <= x_min or y_max <= y_min:
        return None

    crop = img[y_min:y_max, x_min:x_max]
    crop = cv2.resize(crop, (target_size, target_size))
    _, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def process_split(split, label_dir, image_zip):
    print(f"\n{'='*50}")
    print(f"  [{split.upper()}] 처리 시작")
    print(f"{'='*50}")

    if not label_dir.exists():
        print(f"  라벨 없음: {label_dir}")
        return
    if not image_zip.exists():
        print(f"  이미지 zip 없음: {image_zip}")
        return

    # Step 1: 이미지 zip 인덱싱
    print("  이미지 zip 인덱싱...")
    img_entries = {}
    with zipfile.ZipFile(image_zip) as iz:
        for entry in iz.namelist():
            base = os.path.splitext(os.path.basename(entry))[0]
            if base:
                img_entries[base] = entry
    print(f"  zip 내 이미지: {len(img_entries)}개")

    # Step 2: 라벨 분류
    class_data = classify_labels(label_dir, img_entries)

    # Step 3: 밸런싱
    is_val = (split == "val")
    balanced = balance_classes(class_data, is_val=is_val)

    # Step 4: 디렉토리 생성
    seg_img_dir = SEG_DIR / split / "images"
    seg_lbl_dir = SEG_DIR / split / "labels"
    os.makedirs(seg_img_dir, exist_ok=True)
    os.makedirs(seg_lbl_dir, exist_ok=True)

    for cls_name in BALANCE_TARGETS:
        os.makedirs(CLS_DIR / split / cls_name, exist_ok=True)

    # Step 5: 이미지 추출 + 라벨 생성
    all_items = []
    for cls_name, items in balanced.items():
        for img_name, data in items:
            all_items.append((img_name, data, cls_name))

    print(f"\n  총 처리할 이미지: {len(all_items)}개")
    print(f"  이미지 추출 + 라벨 생성 중...")

    seg_count = 0
    cls_counts = {cls: 0 for cls in BALANCE_TARGETS}

    with zipfile.ZipFile(image_zip) as iz:
        for idx, (image_name, data, cls_name) in enumerate(all_items):
            entry = img_entries.get(image_name)
            if not entry:
                continue

            img_w = data["images"][0]["width"]
            img_h = data["images"][0]["height"]

            # 이미지 읽기
            with iz.open(entry) as src:
                img_bytes = src.read()

            # === Seg: 리사이즈 이미지 저장 ===
            seg_img_path = seg_img_dir / (image_name + ".JPG")
            if not seg_img_path.exists():
                resized = resize_image_bytes(img_bytes, SEG_IMGSZ)
                if resized:
                    with open(seg_img_path, "wb") as f:
                        f.write(resized)

            # === Seg: YOLO 라벨 (bbox → 정규화) ===
            lines = []
            best_bbox = None
            best_severity = -1
            for ann in data.get("annotations", []):
                bbox = ann.get("bbox", [])
                if len(bbox) != 4:
                    continue
                x_min, y_min, x_max, y_max = bbox
                xc = max(0, min(1, ((x_min + x_max) / 2) / img_w))
                yc = max(0, min(1, ((y_min + y_max) / 2) / img_h))
                w = max(0, min(1, (x_max - x_min) / img_w))
                h = max(0, min(1, (y_max - y_min) / img_h))
                lines.append(f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")

                # cls용 최적 bbox 선택 (가장 큰 bbox)
                area = (x_max - x_min) * (y_max - y_min)
                if area > best_severity:
                    best_severity = area
                    best_bbox = bbox

            if lines:
                with open(seg_lbl_dir / (image_name + ".txt"), "w") as f:
                    f.write("\n".join(lines))
                seg_count += 1

            # === Cls: 물고기 크롭 저장 ===
            if best_bbox:
                cls_img_path = CLS_DIR / split / cls_name / (image_name + ".JPG")
                if not cls_img_path.exists():
                    cropped = crop_fish(img_bytes, best_bbox, img_w, img_h)
                    if cropped:
                        with open(cls_img_path, "wb") as f:
                            f.write(cropped)
                        cls_counts[cls_name] += 1

            if (idx + 1) % 500 == 0:
                print(f"    {idx+1}/{len(all_items)} 처리...")

    print(f"\n  [Seg] {seg_count} img+lbl")
    print(f"  [Cls] 클래스별:")
    for cls, cnt in sorted(cls_counts.items(), key=lambda x: -x[1]):
        print(f"    {cls:15s}: {cnt}")


def update_data_yaml():
    """Segmentation data.yaml 업데이트"""
    yaml_content = {
        "path": str(SEG_DIR.resolve()),
        "train": "train/images",
        "val": "val/images",
        "names": {0: "fish"},
    }
    with open(SEG_DIR / "data.yaml", "w") as f:
        yaml.dump(yaml_content, f, default_flow_style=False)
    print(f"\n  data.yaml 업데이트: {SEG_DIR / 'data.yaml'}")


def main():
    print("=" * 50)
    print("  넙치 다중 증상 데이터 준비")
    print("=" * 50)

    for split, cfg in SPLITS.items():
        process_split(split, cfg["label_dir"], cfg["image_zip"])

    update_data_yaml()

    # 최종 결과
    print(f"\n{'='*50}")
    print("  최종 결과")
    print(f"{'='*50}")
    for split in SPLITS:
        seg_imgs = len(list((SEG_DIR / split / "images").glob("*.JPG")))
        seg_lbls = len(list((SEG_DIR / split / "labels").glob("*.txt")))
        print(f"  [{split}] Seg: {seg_imgs} img / {seg_lbls} lbl")
        for cls_name in sorted(BALANCE_TARGETS):
            cls_count = len(list((CLS_DIR / split / cls_name).glob("*")))
            print(f"    {cls_name:15s}: {cls_count}")

    os.system(f"du -sh {SEG_DIR} {CLS_DIR}")
    os.system("df -h /")


if __name__ == "__main__":
    main()
