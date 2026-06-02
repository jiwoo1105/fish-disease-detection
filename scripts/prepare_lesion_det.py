"""
병변 탐지 데이터 준비 (AIHub → YOLO Detection)
- AIHub JSON의 병변 bbox + symptom_type → disease-specific YOLO 라벨
- 원본 이미지(6000×4000) → 1280×1280 리사이즈

사용법:
  python scripts/prepare_lesion_det.py --image-dir /path/to/images
  (이미지 디렉토리: zip 해제 후 JPG들이 있는 폴더)

출력:
  data/processed/lesion_det/
    train/images/, train/labels/
    val/images/,   val/labels/
    data.yaml
"""

import argparse
import json
import random
import shutil
from pathlib import Path

import cv2
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_DIRS = [
    PROJECT_ROOT / "data/301.넙치 질병 데이터/01-1.정식개방데이터/Training/02.라벨링데이터/TL_1. RGB Data",
    PROJECT_ROOT / "data/301.넙치 질병 데이터/01-1.정식개방데이터/Validation/02.라벨링데이터/VL_1. RGB Data",
    PROJECT_ROOT / "data/301.넙치 질병 데이터/01-1.정식개방데이터/Validation/02.라벨링데이터/VL_1. RGB Data 2",
]
OUT_DIR   = PROJECT_ROOT / "data/processed/lesion_det"
IMGSZ     = 1280
VAL_RATIO = 0.15
SEED      = 42

# AIHub symptom_type → 클래스명 매핑 (준비 스크립트와 동일)
SYMPTOM_MAP = {
    1:  "hemorrhage",    # 출혈_체표
    2:  "hemorrhage",    # 출혈_지느러미
    3:  "color_change",  # 체색변화
    4:  "tumor",         # 반점/결절
    10: "white_spot",    # 백점
    11: "ulcer",         # 궤양
    12: "ulcer",         # 지느러미부식
    22: "emaciation",    # 여윔
}
# 제외 symptom_type: 6(안구돌출), 8(복부팽만), 9(아가미이상), 29(기타)

CLASS_NAMES = ["hemorrhage", "white_spot", "tumor", "color_change", "emaciation", "ulcer"]
CLASS_IDX   = {name: i for i, name in enumerate(CLASS_NAMES)}


def parse_json(json_path: Path, image_dir: Path):
    """JSON 1개 파싱 → (image_path, [(class_id, cx, cy, w, h), ...])"""
    with open(json_path) as f:
        data = json.load(f)

    img_meta = data.get("images", [{}])[0]
    fname = img_meta.get("file_name", json_path.stem)
    orig_w = img_meta.get("width", 6000)
    orig_h = img_meta.get("height", 4000)

    # 이미지 파일 탐색 (.jpg, .JPG, .jpeg)
    img_path = None
    for ext in [".jpg", ".JPG", ".jpeg", ".png"]:
        candidate = image_dir / (fname + ext)
        if candidate.exists():
            img_path = candidate
            break
    if img_path is None:
        return None, []

    annotations = data.get("annotations", [])
    labels = []
    for ann in annotations:
        s_type = ann.get("symptom_type") or ann.get("symptom")
        if s_type not in SYMPTOM_MAP:
            continue
        class_name = SYMPTOM_MAP[s_type]
        class_id = CLASS_IDX[class_name]

        bbox = ann.get("bbox")  # [x1, y1, x2, y2] 픽셀 단위
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        # 정규화
        cx = ((x1 + x2) / 2) / orig_w
        cy = ((y1 + y2) / 2) / orig_h
        bw = abs(x2 - x1) / orig_w
        bh = abs(y2 - y1) / orig_h
        # 유효성 검사
        if not (0 < cx < 1 and 0 < cy < 1 and 0 < bw <= 1 and 0 < bh <= 1):
            continue
        labels.append((class_id, cx, cy, bw, bh))

    return img_path, labels


def prepare(image_dir: Path, max_per_class: int = 5000):
    print(f"[병변 탐지 데이터 준비]")
    print(f"  이미지 디렉토리: {image_dir}")
    print(f"  출력 디렉토리: {OUT_DIR}")

    # JSON 수집
    json_files = []
    for d in JSON_DIRS:
        if d.exists():
            json_files.extend(sorted(d.glob("*.json")))
    print(f"  JSON 파일 수: {len(json_files)}")

    # 파싱
    valid_samples = []  # (img_path, labels)
    class_counts = {name: 0 for name in CLASS_NAMES}
    skip_no_img = 0
    skip_no_label = 0

    for jp in json_files:
        img_path, labels = parse_json(jp, image_dir)
        if img_path is None:
            skip_no_img += 1
            continue
        if not labels:
            skip_no_label += 1
            continue
        # 클래스별 상한 적용
        classes_in_sample = {l[0] for l in labels}
        if any(class_counts[CLASS_NAMES[c]] >= max_per_class for c in classes_in_sample):
            continue
        for c in classes_in_sample:
            class_counts[CLASS_NAMES[c]] += 1
        valid_samples.append((img_path, labels))

    print(f"  유효 샘플: {len(valid_samples)} (이미지없음: {skip_no_img}, 라벨없음: {skip_no_label})")
    print(f"  클래스별 분포:")
    for name, cnt in class_counts.items():
        print(f"    {name}: {cnt}")

    if not valid_samples:
        print("ERROR: 유효 샘플이 없습니다. 이미지 디렉토리를 확인하세요.")
        return

    # train/val 분리
    random.seed(SEED)
    random.shuffle(valid_samples)
    n_val = max(1, int(len(valid_samples) * VAL_RATIO))
    splits = {"val": valid_samples[:n_val], "train": valid_samples[n_val:]}
    print(f"  train: {len(splits['train'])}, val: {len(splits['val'])}")

    # 출력 폴더 생성
    for split in ["train", "val"]:
        (OUT_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    # 이미지 복사 + 라벨 저장
    for split, samples in splits.items():
        img_out = OUT_DIR / split / "images"
        lbl_out = OUT_DIR / split / "labels"
        for img_path, labels in samples:
            out_img = img_out / (img_path.stem + ".jpg")
            # 리사이즈
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            img = cv2.resize(img, (IMGSZ, IMGSZ))
            cv2.imwrite(str(out_img), img, [cv2.IMWRITE_JPEG_QUALITY, 90])

            # 라벨 저장
            with open(lbl_out / (img_path.stem + ".txt"), "w") as f:
                for (cid, cx, cy, bw, bh) in labels:
                    f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

    # data.yaml 생성
    data_yaml = {
        "train": str(OUT_DIR / "train/images"),
        "val":   str(OUT_DIR / "val/images"),
        "nc":    len(CLASS_NAMES),
        "names": CLASS_NAMES,
    }
    with open(OUT_DIR / "data.yaml", "w") as f:
        yaml.dump(data_yaml, f, allow_unicode=True, default_flow_style=False)

    print(f"\n완료! 데이터셋: {OUT_DIR}")
    print(f"  data.yaml: {OUT_DIR / 'data.yaml'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="병변 탐지 데이터 준비")
    parser.add_argument(
        "--image-dir", type=str, required=True,
        help="원본 이미지 디렉토리 (zip 해제 후 JPG들이 있는 폴더)"
    )
    parser.add_argument(
        "--max-per-class", type=int, default=5000,
        help="클래스당 최대 샘플 수 (기본: 5000)"
    )
    args = parser.parse_args()
    prepare(Path(args.image_dir), args.max_per_class)
