"""
위험도 점수 계산 엔진
- 개별 물고기 위험도 + 수조 전체 위험도
"""

import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "classes.yaml"

with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

SEVERITY = CONFIG["symptom_severity"]
THRESHOLDS = CONFIG["risk_thresholds"]


def score_fish(symptom: str, confidence: float) -> dict:
    """개별 물고기 위험도 계산"""
    severity = SEVERITY.get(symptom, 0)
    score = round(severity * confidence, 3)

    if score >= THRESHOLDS["immediate"]:
        level = "immediate"
    elif score >= THRESHOLDS["danger"]:
        level = "danger"
    elif score >= THRESHOLDS["watch"]:
        level = "watch"
    else:
        level = "normal"

    return {"risk_score": score, "risk_level": level}


def score_tank(fish_results: list) -> dict:
    """수조 전체 위험도 집계"""
    total = len(fish_results)
    if total == 0:
        return {
            "fish_count": 0,
            "diseased_count": 0,
            "disease_ratio": 0.0,
            "tank_risk_level": "normal",
            "symptom_summary": {},
        }

    diseased = sum(1 for f in fish_results if f.get("risk_level", "normal") != "normal")
    ratio = diseased / total
    max_score = max((f.get("risk_score", 0) for f in fish_results), default=0)

    # 증상별 통계
    symptom_counts = {}
    for f in fish_results:
        s = f.get("symptom", "normal")
        symptom_counts[s] = symptom_counts.get(s, 0) + 1

    # 전염성 질병 감지 여부
    has_contagious = any(f.get("contagious", False) for f in fish_results)

    # 수조 위험도 결정
    if ratio >= THRESHOLDS["tank_disease_ratio_immediate"] or (has_contagious and max_score >= THRESHOLDS["danger"]):
        tank_level = "immediate"
    elif ratio >= THRESHOLDS["tank_disease_ratio_danger"] or max_score >= THRESHOLDS["danger"]:
        tank_level = "danger"
    elif diseased > 0:
        tank_level = "watch"
    else:
        tank_level = "normal"

    return {
        "fish_count": total,
        "diseased_count": diseased,
        "disease_ratio": round(ratio, 3),
        "tank_risk_level": tank_level,
        "symptom_summary": symptom_counts,
        "has_contagious": has_contagious,
    }
