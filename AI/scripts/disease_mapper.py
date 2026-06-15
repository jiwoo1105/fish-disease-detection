"""
증상 → 질병 → 대응 가이드 매핑 엔진
configs/classes.yaml의 매핑 정보를 기반으로 동작
"""

import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "classes.yaml"

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

SYMPTOM_DISEASE_MAP = CONFIG["symptom_disease_map"]
DISEASE_RESPONSE = CONFIG["disease_response"]


def map_symptom_to_disease(symptom: str, confidence: float) -> dict:
    """증상으로부터 가장 가능성 높은 질병과 대응 가이드를 반환"""
    if symptom == "normal" or symptom not in SYMPTOM_DISEASE_MAP:
        return {
            "likely_disease": None,
            "disease_confidence": None,
            "contagious": False,
            "response": None,
        }

    diseases = SYMPTOM_DISEASE_MAP[symptom]
    # 가장 확률 높은 질병 선택
    top = max(diseases, key=lambda d: d["probability"])
    disease_name = top["name"]
    disease_conf = round(confidence * top["probability"], 3)

    response = DISEASE_RESPONSE.get(disease_name, {})

    return {
        "likely_disease": disease_name,
        "disease_confidence": disease_conf,
        "contagious": top.get("contagious", False),
        "response": {
            "action": response.get("action", "MONITOR"),
            "temperature": response.get("temperature", "유지"),
            "detail": response.get("detail", ""),
            "urgency": response.get("urgency", "watch"),
            "isolate": response.get("isolate", False),
        } if response else None,
    }


def get_all_possible_diseases(symptom: str) -> list:
    """한 증상에 대한 모든 의심 질병 목록 반환"""
    if symptom not in SYMPTOM_DISEASE_MAP:
        return []
    return [
        {
            "name": d["name"],
            "probability": d["probability"],
            "contagious": d.get("contagious", False),
        }
        for d in SYMPTOM_DISEASE_MAP[symptom]
    ]
