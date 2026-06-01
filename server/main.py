"""
넙치 질병 탐지 API 서버
실행: uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

import io
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# scripts 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from inference import load_models, analyze_image, analyze_video, draw_results
from disease_mapper import get_all_possible_diseases
from risk_scorer import score_tank

app = FastAPI(
    title="넙치 질병 탐지 API",
    description="YOLO26 기반 양식장 넙치 질병 탐지 시스템",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모델 로드 (서버 시작 시 1회)
seg_model, cls_model = None, None

@app.on_event("startup")
async def startup():
    global seg_model, cls_model
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    seg_path = str(project_root / "models/seg/best_seg.pt")
    cls_path = str(project_root / "models/cls/best_cls.pt")

    if not Path(seg_path).exists() or not Path(cls_path).exists():
        print(f"WARNING: Model files not found. Server will start without models.")
        print(f"  Seg: {seg_path} ({'EXISTS' if Path(seg_path).exists() else 'MISSING'})")
        print(f"  Cls: {cls_path} ({'EXISTS' if Path(cls_path).exists() else 'MISSING'})")
        return

    seg_model, cls_model = load_models(seg_path, cls_path)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": seg_model is not None and cls_model is not None,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """이미지 업로드 → 질병 분석 결과 반환"""
    if seg_model is None or cls_model is None:
        raise HTTPException(503, "모델이 로드되지 않았습니다. 서버를 재시작하세요.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드 가능합니다")

    contents = await file.read()
    arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(400, "이미지를 읽을 수 없습니다")

    start = time.time()
    result = analyze_image(image, seg_model, cls_model)
    elapsed = time.time() - start

    result["timestamp"] = datetime.now().isoformat()
    result["inference_time_ms"] = round(elapsed * 1000, 1)
    result["image_name"] = file.filename

    return result


@app.get("/api/diseases/{symptom}")
async def disease_info(symptom: str):
    """증상에 대한 의심 질병 목록 + 대응 가이드"""
    diseases = get_all_possible_diseases(symptom)
    if not diseases:
        raise HTTPException(404, f"증상 '{symptom}'에 대한 정보가 없습니다")
    return {"symptom": symptom, "possible_diseases": diseases}


@app.get("/api/classes")
async def list_classes():
    """사용 가능한 증상 클래스 목록"""
    return {
        "classes": [
            "normal", "hemorrhage", "white_spot", "tumor",
            "color_change", "emaciation", "ulcer"
        ]
    }
