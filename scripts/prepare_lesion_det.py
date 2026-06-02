"""
병변 탐지 데이터 준비 (AIHub → YOLO Detection)
- AIHub JSON의 병변 bbox + symptom_type → disease-specific YOLO 라벨
- 이미지를 zip에서 직접 읽음 (압축 해제 불필요)
- 로컬/서버 경로 자동 감지

사용법:
  python scripts/prepare_lesion_det.py

출력:
  data/processed/lesion_det/
    train/images/, train/labels/
    val/images/,   val/labels/
    data.yaml
"""

import json
import os
import random
import zipfile
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR      = PROJECT_ROOT / "data/processed/lesion_det"
IMGSZ        = 1280
SEED         = 42
MAX_PER_CLASS = 3000   # 클래스당 최대 샘플 (디스크 절약)

# symptom_type → 클래스명
SYMPTOM_MAP = {
    1:  "hemorrhage",
    2:  "hemorrhage",
    3:  "color_change",
    4:  "tumor",
    10: "white_spot",
    11: "ulcer",
    12: "ulcer",
    22: "emaciation",
}
CLASS_NAMES = ["hemorrhage", "white_spot", "tumor", "color_change", "emaciation", "ulcer"]
CLASS_IDX   = {name: i for i, name in enumerate(CLASS_NAMES)}


def find_paths():
    """로컬/서버 경로 자동 감지"""
    data_dir = PROJECT_ROOT / "data"

    # 서버 flat 구조: data/labels/train, data/TS_1.zip
    if (data_dir / "TS_1.zip").exists():
        return [
            {
                "label_dir": data_dir / "labels/train",
                "image_zip": data_dir / "TS_1.zip",
            },
            {
                "label_dir": data_dir / "labels/val",
                "image_zip": data_dir / "VS_1.zip",
            },
        ]

    # 로컬 AIHub 원본 구조
    aihub = data_dir / "301.넙치 질병 데이터/01-1.정식개방데이터"
    if aihub.exists():
        return [
            {
                "label_dir": aihub / "Training/02.라벨링데이터/TL_1. RGB Data",
                "image_zip": aihub / "Training/01.원천데이터/TS_1. RGB Data_1.zip",
            },
            {
                "label_dir": aihub / "Validation/02.라벨링데이터/VL_1. RGB Data",
                "image_zip": aihub / "Validation/01.원천데이터/VS_1. RGB Data.zip",
            },
        ]

    return []


def index_zip(zip_path: Path) -> dict:
    """zip 내 이미지 파일명 → zip 내 경로 인덱싱"""
    entries = {}
    with zipfile.ZipFile(zip_path) as z:
        for entry in z.namelist():
            base = os.path.splitext(os.path.basename(entry))[0]
            if base:
                entries[base] = entry
    return entries


def parse_annotations(json_path: Path, img_entries: dict):
    """JSON 파싱 → (image_name, orig_w, orig_h, [(class_id, cx, cy, bw, bh), ...])"""
    with open(json_path) as f:
        data = json.load(f)

    img_meta = data.get("images", [{}])[0]
    img_name = img_meta.get("file_name", json_path.stem)
    orig_w   = img_meta.get("width", 6000)
    orig_h   = img_meta.get("height", 4000)

    if img_name not in img_entries:
        return None, None, None, []

    labels = []
    for ann in data.get("annotations", []):
        s_type = ann.get("symptom")
        if s_type not in SYMPTOM_MAP:
            continue
        bbox = ann.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        cx = ((x1 + x2) / 2) / orig_w
        cy = ((y1 + y2) / 2) / orig_h
        bw = abs(x2 - x1) / orig_w
        bh = abs(y2 - y1) / orig_h
        if not (0 < cx < 1 and 0 < cy < 1 and 0 < bw <= 1 and 0 < bh <= 1):
            continue
        labels.append((CLASS_IDX[SYMPTOM_MAP[s_type]], cx, cy, bw, bh))

    return img_name, orig_w, orig_h, labels


def prepare():
    print("[병변 탐지 데이터 준비]")

    splits_config = find_paths()
    if not splits_config:
        print("ERROR: 데이터 경로를 찾을 수 없습니다.")
        return

    for cfg in splits_config:
        print(f"  라벨: {cfg['label_dir']}")
        print(f"  이미지 zip: {cfg['image_zip']}")

    # 출력 폴더
    for split in ["train", "val"]:
        (OUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    class_counts = {name: 0 for name in CLASS_NAMES}
    total_saved = 0

    for cfg_idx, cfg in enumerate(splits_config):
        label_dir = cfg["label_dir"]
        image_zip = cfg["image_zip"]
        split     = "train" if cfg_idx == 0 else "val"

        if not label_dir.exists():
            print(f"  라벨 폴더 없음: {label_dir}")
            continue
        if not image_zip.exists():
            print(f"  zip 없음: {image_zip}")
            continue

        print(f"\n[{split.upper()}] 처리 중...")
        print("  zip 인덱싱...")
        img_entries = index_zip(image_zip)
        print(f"  zip 내 이미지: {len(img_entries)}개")

        json_files = sorted(label_dir.glob("*.json"))
        print(f"  JSON 파일: {len(json_files)}개")

        # 파싱 (유효한 것만)
        valid = []
        for jp in json_files:
            img_name, orig_w, orig_h, labels = parse_annotations(jp, img_entries)
            if img_name and labels:
                valid.append((img_name, orig_w, orig_h, labels, img_entries[img_name]))

        print(f"  유효 샘플: {len(valid)}개")

        # 클래스 상한 필터
        random.seed(SEED)
        random.shuffle(valid)
        filtered = []
        for item in valid:
            labels = item[3]
            classes_in = {l[0] for l in labels}
            if any(class_counts[CLASS_NAMES[c]] >= MAX_PER_CLASS for c in classes_in):
                continue
            for c in classes_in:
                class_counts[CLASS_NAMES[c]] += 1
            filtered.append(item)

        print(f"  클래스 상한 적용 후: {len(filtered)}개")

        img_out = OUT_DIR / split / "images"
        lbl_out = OUT_DIR / split / "labels"

        # zip에서 이미지 읽어서 저장
        with zipfile.ZipFile(image_zip) as z:
            for idx, (img_name, orig_w, orig_h, labels, zip_entry) in enumerate(filtered):
                if (idx + 1) % 500 == 0:
                    print(f"  {idx+1}/{len(filtered)}...")

                out_img = img_out / (img_name + ".jpg")
                if not out_img.exists():
                    with z.open(zip_entry) as src:
                        img_bytes = src.read()
                    arr = np.frombuffer(img_bytes, np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is None:
                        continue
                    img = cv2.resize(img, (IMGSZ, IMGSZ))
                    cv2.imwrite(str(out_img), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

                with open(lbl_out / (img_name + ".txt"), "w") as f:
                    for (cid, cx, cy, bw, bh) in labels:
                        f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                total_saved += 1

    # data.yaml
    data_yaml = {
        "train": str(OUT_DIR / "train/images"),
        "val":   str(OUT_DIR / "val/images"),
        "nc":    len(CLASS_NAMES),
        "names": CLASS_NAMES,
    }
    with open(OUT_DIR / "data.yaml", "w") as f:
        yaml.dump(data_yaml, f, allow_unicode=True, default_flow_style=False)

    print(f"\n완료! 총 {total_saved}장 저장")
    print("클래스별 분포:")
    for name, cnt in class_counts.items():
        print(f"  {name}: {cnt}")
    print(f"data.yaml: {OUT_DIR / 'data.yaml'}")


if __name__ == "__main__":
    prepare()
