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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
import yaml

random.seed(42)

# ============================================================
# 설정 로드 (프로젝트 루트 기준 절대 경로)
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEG_DIR = PROJECT_ROOT / "data/processed/segmentation"
CLS_DIR = PROJECT_ROOT / "data/processed/classification"
CONFIG_PATH = PROJECT_ROOT / "configs/classes.yaml"

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

SYMPTOM_CODE_MAP = CONFIG["symptom_code_map"]
BALANCE_TARGETS = CONFIG["balance_targets"]
SEG_IMGSZ = 1280  # seg용 리사이즈
CLS_IMGSZ = 224   # cls용 크롭 리사이즈

# 데이터 경로 자동 탐색 (AIHub 원본 구조 또는 서버 flat 구조 둘 다 지원)
def find_data_paths():
    """데이터 경로 자동 탐색"""
    data_dir = PROJECT_ROOT / "data"

    # 경로 후보 1: AIHub 원본 구조 (로컬)
    aihub_base = data_dir / "301.넙치 질병 데이터/01-1.정식개방데이터"
    if aihub_base.exists():
        return {
            "train": {
                "label_dir": aihub_base / "Training/02.라벨링데이터/TL_1. RGB Data",
                "image_zip": aihub_base / "Training/01.원천데이터/TS_1. RGB Data_1.zip",
            },
            "val": {
                "label_dir": aihub_base / "Validation/02.라벨링데이터/VL_1. RGB Data",
                "image_zip": aihub_base / "Validation/01.원천데이터/VS_1. RGB Data.zip",
            },
        }

    # 경로 후보 2: 서버 flat 구조
    # labels: data/labels/train/TL_1. RGB Data/*.json
    # images: data/TS_1.zip, data/VS_1.zip
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

SPLITS = find_data_paths()


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


def _read_json(path):
    """단일 JSON 파일 읽기 (스레드용)"""
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def classify_labels(label_dir, img_entries):
    """라벨 파일을 클래스별로 분류 (zip에 이미지 있는 것만, 멀티스레드)"""
    class_data = {cls: [] for cls in BALANCE_TARGETS}
    skipped = 0

    files = [f for f in os.listdir(label_dir) if f.endswith('.json')]
    print(f"  라벨 파일: {len(files)}개")
    print(f"  멀티스레드로 JSON 읽는 중 (32 workers)...")

    paths = [os.path.join(label_dir, f) for f in files]
    results = [None] * len(paths)

    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(_read_json, p): i for i, p in enumerate(paths)}
        done_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            results[idx] = future.result()
            done_count += 1
            if done_count % 5000 == 0:
                print(f"    {done_count}/{len(files)} 읽기 완료...")

    print(f"  JSON 읽기 완료, 분류 중...")
    for data in results:
        if data is None:
            skipped += 1
            continue

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

    # Step 4: 디렉토리 생성 (Cls만 — Seg는 이미 학습 완료)
    for cls_name in BALANCE_TARGETS:
        os.makedirs(CLS_DIR / split / cls_name, exist_ok=True)

    # Step 5: 이미지 추출 (Cls 크롭만)
    all_items = []
    for cls_name, items in balanced.items():
        for img_name, data in items:
            all_items.append((img_name, data, cls_name))

    # 크롭 단계 클래스당 최대 개수 (train만 제한, val은 전체 사용)
    MAX_CROPS_PER_CLASS = 2500 if not is_val else float('inf')

    print(f"\n  총 처리할 이미지: {len(all_items)}개")
    print(f"  Cls 크롭 이미지 추출 중 (Seg 스킵, 클래스당 max={MAX_CROPS_PER_CLASS})...")

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

            # === Cls: 크롭 저장 ===
            has_bbox = False
            for ann_idx, ann in enumerate(data.get("annotations", [])):
                bbox = ann.get("bbox", [])
                if len(bbox) != 4:
                    continue
                has_bbox = True
                # 개별 annotation의 증상으로 클래스 결정
                s = ann.get("symptom")
                ann_cls = SYMPTOM_CODE_MAP.get(s) if s else None
                if ann_cls is None or ann_cls == "null":
                    if ann.get("symptom_type") is None:
                        ann_cls = "normal"
                    else:
                        continue

                # 클래스당 최대 개수 제한
                if cls_counts.get(ann_cls, 0) >= MAX_CROPS_PER_CLASS:
                    continue

                cls_img_path = CLS_DIR / split / ann_cls / (f"{image_name}_fish{ann_idx}.JPG")
                if not cls_img_path.exists():
                    cropped = crop_fish(img_bytes, bbox, img_w, img_h)
                    if cropped:
                        with open(cls_img_path, "wb") as f:
                            f.write(cropped)
                        if ann_cls in cls_counts:
                            cls_counts[ann_cls] += 1

            # normal 이미지인데 bbox 없으면 → 전체 이미지 리사이즈로 저장
            if not has_bbox and cls_name == "normal":
                if cls_counts["normal"] >= MAX_CROPS_PER_CLASS:
                    continue
                cls_img_path = CLS_DIR / split / "normal" / (f"{image_name}.JPG")
                if not cls_img_path.exists():
                    resized = resize_image_bytes(img_bytes, CLS_IMGSZ)
                    if resized:
                        with open(cls_img_path, "wb") as f:
                            f.write(resized)
                        cls_counts["normal"] += 1

            if (idx + 1) % 500 == 0:
                print(f"    {idx+1}/{len(all_items)} 처리...")

    print(f"\n  [Cls] 클래스별:")
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
