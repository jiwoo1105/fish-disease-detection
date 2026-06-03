"""
넙치 질병 탐지 API 서버
실행: uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

import base64
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from typing import Optional
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# scripts 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from inference import load_models, analyze_image, draw_results
from disease_mapper import get_all_possible_diseases
from risk_scorer import score_sensors, score_disease_temperature

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
seg_model, cls_model, lesion_model = None, None, None

@app.on_event("startup")
async def startup():
    global seg_model, cls_model, lesion_model
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent
    det_path = str(project_root / "models/det/best_det.pt")
    seg_path = str(project_root / "models/seg/best_seg.pt")
    cls_path = str(project_root / "models/cls/best_cls.pt")
    lesion_path = str(project_root / "models/lesion_det/best_lesion_det.pt")

    det_exists = Path(det_path).exists()
    seg_exists = Path(seg_path).exists()

    if not (det_exists or seg_exists) or not Path(cls_path).exists():
        print(f"WARNING: Model files not found. Server will start without models.")
        print(f"  Det: {det_path} ({'EXISTS' if det_exists else 'MISSING'})")
        print(f"  Seg: {seg_path} ({'EXISTS' if seg_exists else 'MISSING'})")
        print(f"  Cls: {cls_path} ({'EXISTS' if Path(cls_path).exists() else 'MISSING'})")
        return

    active_det = det_path if det_exists else seg_path
    seg_model, cls_model, lesion_model = load_models(active_det, cls_path, lesion_path)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).resolve().parent / "templates" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "models_loaded": seg_model is not None and cls_model is not None,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    temperature: Optional[float] = Form(None),
    do: Optional[float] = Form(None),
    ph: Optional[float] = Form(None),
    salinity: Optional[float] = Form(None),
):
    """이미지 업로드 → 질병 분석 결과 반환
    선택적 수질 센서 데이터: temperature, do, ph, salinity
    """
    if seg_model is None or cls_model is None:  # lesion_model is optional
        raise HTTPException(503, "모델이 로드되지 않았습니다. 서버를 재시작하세요.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "이미지 파일만 업로드 가능합니다")

    contents = await file.read()
    arr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(400, "이미지를 읽을 수 없습니다")

    start = time.time()
    result = analyze_image(image, seg_model, cls_model, lesion_model)
    elapsed = time.time() - start

    # 수질 센서 분석
    sensors = {k: v for k, v in {
        "temperature": temperature, "do": do, "ph": ph, "salinity": salinity
    }.items() if v is not None}

    if sensors:
        sensor_result = score_sensors(sensors)
        result["sensors"] = sensors
        result["sensor_alerts"] = sensor_result["sensor_alerts"]
        result["sensor_ok"] = sensor_result["sensor_ok"]

        # 질병 + 수온 조합 경보
        temp_combined = []
        for fish in result.get("fish", []):
            disease = fish.get("likely_disease")
            if disease and temperature is not None:
                combined = score_disease_temperature(disease, temperature)
                if combined:
                    temp_combined.append({
                        "fish_id": fish["fish_id"],
                        "disease": disease,
                        **combined,
                    })
        if temp_combined:
            result["temperature_disease_alerts"] = temp_combined
    else:
        result["sensors"] = {}
        result["sensor_alerts"] = []
        result["sensor_ok"] = True

    # bbox가 그려진 결과 이미지를 base64로 인코딩
    vis = draw_results(image, result)
    _, buf = cv2.imencode('.jpg', vis, [cv2.IMWRITE_JPEG_QUALITY, 85])
    result["result_image"] = base64.b64encode(buf.tobytes()).decode("utf-8")

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
