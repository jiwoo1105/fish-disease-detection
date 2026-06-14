"""
3-Stage 추론 파이프라인
Stage 1: YOLO26-Det → 물고기 탐지 + 크롭
Stage 2: YOLO26-Cls → 증상 분류
Stage 2.5: YOLO26-Det(lesion) → 병변 위치 탐지 (증상 있는 물고기만)
Stage 3: 질병 매핑 + 위험도 계산

사용법:
    python scripts/inference.py --image path/to/image.jpg
    python scripts/inference.py --video path/to/video.mp4
"""

import argparse
import json
import time
from pathlib import Path

import sys
import cv2
import numpy as np
from ultralytics import YOLO

# import 경로 설정 (어디서 실행해도 동작하도록)
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from disease_mapper import map_symptom_to_disease
from risk_scorer import score_fish, score_tank

# 모델 경로
DET_MODEL    = str(PROJECT_ROOT / "models/det/best_det.pt")
SEG_MODEL    = str(PROJECT_ROOT / "models/seg/best_seg.pt")
CLS_MODEL    = str(PROJECT_ROOT / "models/cls/best_cls.pt")
LESION_MODEL = str(PROJECT_ROOT / "models/lesion_det/best_lesion_det.pt")
CLS_IMGSZ    = 224


def load_models(det_path=None, cls_path=CLS_MODEL, lesion_path=LESION_MODEL):
    """모델 로드 - Det 모델 우선, 없으면 Seg fallback / Lesion은 선택"""
    if det_path is None:
        if Path(DET_MODEL).exists():
            det_path = DET_MODEL
        elif Path(SEG_MODEL).exists():
            det_path = SEG_MODEL
            print(f"  [WARN] Det 모델 없음, Seg 모델로 fallback: {det_path}")
        else:
            raise FileNotFoundError(f"탐지 모델 없음: {DET_MODEL} / {SEG_MODEL}")

    print(f"Loading det model: {det_path}")
    det = YOLO(det_path)
    print(f"Loading cls model: {cls_path}")
    cls = YOLO(cls_path)

    lesion = None
    if Path(lesion_path).exists():
        print(f"Loading lesion model: {lesion_path}")
        lesion = YOLO(lesion_path)
    else:
        print(f"  [INFO] Lesion 모델 없음, 병변 탐지 비활성화")

    return det, cls, lesion


def crop_fish(image, bbox, target_size=CLS_IMGSZ):
    """바운딩박스로 물고기 크롭"""
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = image[y1:y2, x1:x2]
    if target_size:
        return cv2.resize(crop, (target_size, target_size))
    return crop


def run_lesion_det(image, fish_bbox, lesion_model):
    """물고기 크롭에서 병변 탐지 후 원본 이미지 좌표로 변환"""
    x1, y1, x2, y2 = [int(v) for v in fish_bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(image.shape[1], x2)
    y2 = min(image.shape[0], y2)

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return []

    results = lesion_model(crop, verbose=False)
    lesions = []

    if results[0].boxes is None or len(results[0].boxes) == 0:
        return lesions

    crop_h, crop_w = crop.shape[:2]
    for box in results[0].boxes:
        lx1, ly1, lx2, ly2 = box.xyxy[0].cpu().numpy().tolist()
        conf = float(box.conf[0])
        cls_id = int(box.cls[0])
        cls_name = results[0].names[cls_id]

        # 크롭 좌표 → 원본 이미지 좌표 변환
        orig_lx1 = x1 + lx1
        orig_ly1 = y1 + ly1
        orig_lx2 = x1 + lx2
        orig_ly2 = y1 + ly2

        lesions.append({
            "bbox": [round(v, 1) for v in [orig_lx1, orig_ly1, orig_lx2, orig_ly2]],
            "disease_class": cls_name,
            "confidence": round(conf, 3),
        })

    return lesions


def analyze_image(image, det_model, cls_model, lesion_model=None):
    """단일 이미지 분석 → 결과 JSON"""
    # Stage 1: 물고기 탐지
    det_results = det_model(image, verbose=False)
    fish_results = []

    if len(det_results) == 0 or det_results[0].boxes is None:
        return score_tank(fish_results) | {"fish": fish_results, "alerts": []}

    boxes = det_results[0].boxes
    for i, box in enumerate(boxes):
        bbox = box.xyxy[0].cpu().numpy().tolist()
        det_conf = float(box.conf[0])

        # Stage 2: 증상 분류
        cropped = crop_fish(image, bbox, target_size=CLS_IMGSZ)
        if cropped is None:
            continue

        cls_results = cls_model(cropped, verbose=False)
        if cls_results[0].probs is None:
            continue

        probs = cls_results[0].probs
        cls_id = int(probs.top1)
        cls_conf = float(probs.top1conf)
        cls_name = cls_results[0].names[cls_id]

        # Stage 3: 질병 매핑 + 위험도
        disease_info = map_symptom_to_disease(cls_name, cls_conf)
        risk_info = score_fish(cls_name, cls_conf)

        # Stage 2.5: 병변 위치 탐지 (증상 있는 물고기만)
        lesions = []
        if lesion_model is not None and cls_name != "normal":
            lesions = run_lesion_det(image, bbox, lesion_model)

        fish_results.append({
            "fish_id": i + 1,
            "bbox": [round(v, 1) for v in bbox],
            "det_confidence": round(det_conf, 3),
            "symptom": cls_name,
            "symptom_confidence": round(cls_conf, 3),
            "lesions": lesions,
            **disease_info,
            **risk_info,
        })

    # 수조 집계
    tank_info = score_tank(fish_results)

    # 알림 생성 (watch 이상이면 알림)
    alerts = []
    for f in fish_results:
        if f["risk_level"] != "normal" and f.get("response"):
            alerts.append({
                "fish_id": f["fish_id"],
                "severity": f["risk_level"],
                "disease": f["likely_disease"],
                "contagious": f["contagious"],
                **f["response"],
            })

    return {**tank_info, "fish": fish_results, "alerts": alerts}


def analyze_video(video_path, det_model, cls_model, lesion_model=None, frame_interval=30):
    """영상 분석 (N 프레임마다 분석)"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {fps:.1f} FPS, {total_frames} frames")
    print(f"Analyzing every {frame_interval} frames ({frame_interval/fps:.1f}s interval)")

    results_history = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            result = analyze_image(frame, det_model, cls_model, lesion_model)
            result["frame"] = frame_idx
            result["timestamp"] = round(frame_idx / fps, 2)
            results_history.append(result)

            level = result["tank_risk_level"]
            fish_n = result["fish_count"]
            diseased_n = result["diseased_count"]
            print(f"  Frame {frame_idx}: {fish_n} fish, {diseased_n} diseased, risk={level}")

        frame_idx += 1

    cap.release()
    print(f"\nAnalyzed {len(results_history)} frames")
    return results_history


def draw_results(image, result):
    """결과를 이미지에 시각화"""
    vis = image.copy()

    fish_colors = {
        "normal":    (0, 255, 0),
        "watch":     (0, 255, 255),
        "danger":    (0, 165, 255),
        "immediate": (0, 0, 255),
    }
    LESION_COLOR = (255, 0, 255)  # 병변 bbox: 보라색

    for fish in result.get("fish", []):
        bbox = fish["bbox"]
        x1, y1, x2, y2 = [int(v) for v in bbox]
        level = fish["risk_level"]
        color = fish_colors.get(level, (255, 255, 255))

        # 물고기 bbox
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

        # 물고기 라벨
        symptom = fish["symptom"]
        conf = fish["symptom_confidence"]
        label = f"#{fish['fish_id']} {symptom} {conf:.0%}"
        cv2.putText(vis, label, (x1, max(y1 - 10, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # 병변 bbox (보라색, 점선 효과를 위해 얇게)
        for lesion in fish.get("lesions", []):
            lx1, ly1, lx2, ly2 = [int(v) for v in lesion["bbox"]]
            cv2.rectangle(vis, (lx1, ly1), (lx2, ly2), LESION_COLOR, 2)
            l_label = f"{lesion['disease_class']} {lesion['confidence']:.0%}"
            cv2.putText(vis, l_label, (lx1, max(ly1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, LESION_COLOR, 1)

    # 수조 정보
    tank_level = result.get("tank_risk_level", "normal")
    tank_color = fish_colors.get(tank_level, (255, 255, 255))
    info = f"Fish: {result.get('fish_count', 0)} | Diseased: {result.get('diseased_count', 0)} | Risk: {tank_level}"
    cv2.putText(vis, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, tank_color, 2)

    return vis


def main():
    parser = argparse.ArgumentParser(description="넙치 질병 탐지 추론")
    parser.add_argument("--image", type=str, help="이미지 경로")
    parser.add_argument("--video", type=str, help="영상 경로")
    parser.add_argument("--det-model", type=str, default=None)
    parser.add_argument("--cls-model", type=str, default=CLS_MODEL)
    parser.add_argument("--lesion-model", type=str, default=LESION_MODEL)
    parser.add_argument("--frame-interval", type=int, default=30)
    parser.add_argument("--save", action="store_true", help="결과 이미지/영상 저장")
    args = parser.parse_args()

    det_model, cls_model, lesion_model = load_models(
        args.det_model, args.cls_model, args.lesion_model
    )

    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            print(f"Error: Cannot read {args.image}")
            return

        start = time.time()
        result = analyze_image(image, det_model, cls_model, lesion_model)
        elapsed = time.time() - start

        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nInference time: {elapsed:.3f}s")

        if args.save:
            vis = draw_results(image, result)
            out_path = Path(args.image).stem + "_result.jpg"
            cv2.imwrite(out_path, vis)
            print(f"Saved: {out_path}")

    elif args.video:
        results = analyze_video(args.video, det_model, cls_model, lesion_model, args.frame_interval)
        out_path = Path(args.video).stem + "_results.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Saved: {out_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
