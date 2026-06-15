
"""
AIHub 넙치 질병 데이터 필터링 (v3)
- 라벨 zip에서 직접 읽기
- 이미지 zip에 있는 것만 사용
- 이진분류: symptom=10 (백점) vs 나머지 (비백점)
- Cls는 symlink로 디스크 절약
"""

import json
import os
import random
import zipfile
from pathlib import Path

random.seed(42)

BASE_DIR = Path("data/301.넙치 질병 데이터/01-1.정식개방데이터")
SEG_DIR = Path("data/processed/segmentation")
CLS_DIR = Path("data/processed/classification")

SPLITS = {
    "train": {
        "label_zip": BASE_DIR / "Training/02.라벨링데이터/TL_1. RGB Data.zip",
        "image_zip": BASE_DIR / "Training/01.원천데이터/TS_1. RGB Data_1.zip",
    },
    "val": {
        "label_zip": BASE_DIR / "Validation/02.라벨링데이터/VL_1. RGB Data.zip",
        "image_zip": BASE_DIR / "Validation/01.원천데이터/VS_1. RGB Data.zip",
    },
}


def process_split(split, label_zip_path, image_zip_path):
    print(f"\n{'='*50}")
    print(f"  [{split.upper()}] 처리 시작")
    print(f"{'='*50}")

    # Step 1: 이미지 zip 인덱싱
    print("  이미지 zip 인덱싱...")
    img_entries = {}
    with zipfile.ZipFile(image_zip_path) as iz:
        for entry in iz.namelist():
            base = os.path.splitext(os.path.basename(entry))[0]
            if base:
                img_entries[base] = entry
    print(f"  이미지 zip: {len(img_entries)}개")

    # Step 2: 라벨 zip에서 분류 (zip에 있는 이미지만)
    print("  라벨 분류 중...")
    ws_data = []    # 백점 (symptom=10)
    other_data = [] # 비백점 (symptom!=10, 하지만 symptom_type 있음 = 질병 있음)

    with zipfile.ZipFile(label_zip_path) as lz:
        entries = [e for e in lz.namelist() if e.endswith('.json')]
        print(f"  라벨 파일: {len(entries)}개")

        for i, entry in enumerate(entries):
            if (i + 1) % 10000 == 0:
                print(f"    {i+1}/{len(entries)}...")

            with lz.open(entry) as f:
                data = json.load(f)

            image_name = data["images"][0]["file_name"]
            if image_name not in img_entries:
                continue

            has_ws = any(
                ann.get("symptom") == 10
                for ann in data.get("annotations", [])
            )

            if has_ws:
                ws_data.append((image_name, data))
            else:
                other_data.append((image_name, data))

    print(f"  백점: {len(ws_data)}, 비백점: {len(other_data)}")

    # Step 3: 1:1 밸런싱
    n = len(ws_data)
    if len(other_data) > n:
        other_data = random.sample(other_data, n)
    print(f"  밸런싱 → 백점: {len(ws_data)}, 비백점: {len(other_data)}")

    all_data = ws_data + other_data

    # Step 4: YOLO 라벨 + 이미지 추출
    seg_img_dir = SEG_DIR / split / "images"
    seg_lbl_dir = SEG_DIR / split / "labels"
    os.makedirs(seg_img_dir, exist_ok=True)
    os.makedirs(seg_lbl_dir, exist_ok=True)

    needed = {}  # image_name -> data
    for image_name, data in all_data:
        img_w = data["images"][0]["width"]
        img_h = data["images"][0]["height"]

        lines = []
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

        if lines:
            with open(os.path.join(seg_lbl_dir, image_name + ".txt"), "w") as f:
                f.write("\n".join(lines))
            needed[image_name] = True

    print(f"  [Seg] 라벨: {len(needed)}개")

    # 이미지 추출
    print(f"  [Seg] 이미지 추출 중...")
    extracted = 0
    with zipfile.ZipFile(image_zip_path) as iz:
        for img_name in needed:
            entry = img_entries.get(img_name)
            if entry:
                target = os.path.join(seg_img_dir, img_name + ".JPG")
                if not os.path.exists(target):
                    with iz.open(entry) as src, open(target, "wb") as dst:
                        dst.write(src.read())
                    extracted += 1
                    if extracted % 500 == 0:
                        print(f"    {extracted}장...")
    print(f"  [Seg] 추출: {extracted}장")

    # Step 5: Cls symlink
    cls_ws_dir = CLS_DIR / split / "white_spot"
    cls_nm_dir = CLS_DIR / split / "normal"
    os.makedirs(cls_ws_dir, exist_ok=True)
    os.makedirs(cls_nm_dir, exist_ok=True)

    seg_abs = seg_img_dir.resolve()
    ws_names = {n for n, _ in ws_data}
    nm_names = {n for n, _ in other_data}

    for names, cls_dir, label in [(ws_names, cls_ws_dir, "백점"), (nm_names, cls_nm_dir, "정상")]:
        linked = 0
        for name in names:
            src = seg_abs / (name + ".JPG")
            dst = cls_dir / (name + ".JPG")
            if src.exists() and not dst.exists():
                os.symlink(src, dst)
                linked += 1
        print(f"  [Cls] {label} symlink: {linked}개")


def main():
    print("=" * 50)
    print("  넙치 백점병 데이터 필터링 v3")
    print("=" * 50)

    for split, cfg in SPLITS.items():
        process_split(split, cfg["label_zip"], cfg["image_zip"])

    print(f"\n{'='*50}")
    print("  최종 결과")
    print(f"{'='*50}")
    for split in SPLITS:
        seg_imgs = len(list((SEG_DIR / split / "images").glob("*.JPG")))
        seg_lbls = len(list((SEG_DIR / split / "labels").glob("*.txt")))
        cls_ws = len(list((CLS_DIR / split / "white_spot").glob("*")))
        cls_nm = len(list((CLS_DIR / split / "normal").glob("*")))
        print(f"  [{split}] Seg: {seg_imgs} img / {seg_lbls} lbl | Cls: {cls_ws} ws / {cls_nm} nm")

    os.system(f"du -sh {SEG_DIR} {CLS_DIR}")
    os.system("df -h /")


if __name__ == "__main__":
    main()
