# 넙치 백점병 조기 탐지 시스템 (Flatfish White Spot Disease Detection)

## 프로젝트 개요

제주도 넙치 양식장에서 **백점병(White Spot Disease, Ich)**을 조기 탐지하는 임베디드 AI 시스템.
YOLO 기반 물고기 segmentation + 백점병 이진분류 2-Stage 파이프라인으로 구현한다.

---

## 데이터셋

- **출처**: [AIHub - 넙치 질병 데이터](https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=71345)
- **총 용량**: ~916GB (전체)
- **RGB 이미지**: 48,765건 (Training) + 6,096건 (Validation) = JPG, 6000x4000
- **라벨 포맷**: JSON (바운딩박스, COCO 유사 구조)
- **질병 분류**: `disease` 필드 (21개 질병코드) + `symptom` 필드 (31개 증상코드)
- **대상 증상**: 백점 증상 (`symptom=10`, `symptom_type=3`)

### 실제 데이터 분석 결과 (Training 기준)

| 분류 | 조건 | 이미지 수 | 어노테이션 수 |
|------|------|----------|-------------|
| **백점 증상** | `symptom == 10` | **4,989개** | 7,123건 |
| **정상** | `symptom_type == None` | **10,123개** | 9,962건 |
| 기타 질병 | 나머지 | 33,653개 | 93,237건 |

- 비율: 백점 : 정상 = 1 : 2 (균형 양호)
- **참고**: `disease` 필드에는 백점병(코드10)이 없음. `symptom` 필드에서 백점 증상을 구분

### AIHub 다운로드 파일 목록 및 선택 가이드

AIHub 다운로드 페이지의 파일은 아래 명명 규칙을 따름:
- **TS** = Training Source (학습용 원본 이미지)
- **TL** = Training Label (학습용 라벨 JSON)
- **VS** = Validation Source (검증용 원본 이미지)
- **VL** = Validation Label (검증용 라벨 JSON)
- **_1** = RGB 데이터 / **_2** = 초분광(Hyper Spectral) 데이터

#### 반드시 다운로드 (필수)

| 파일명 (예상) | 설명 | 용도 |
|--------------|------|------|
| **TL_1. RGB Data.zip** (33MB) | 학습용 RGB 라벨 (JSON 48,765개) | 백점 필터링 + YOLO 포맷 변환 |
| **VL_1. RGB Data.zip** (4.3MB) | 검증용 RGB 라벨 (JSON 6,096개) | 검증 데이터 라벨 |
| **TS_1. RGB Data_1.zip** (97GB) | 학습용 RGB 이미지 (17,937개) | Stage 1 Seg + Stage 2 Cls 학습 |
| **VS_1. RGB Data.zip** (33GB) | 검증용 RGB 이미지 (6,096개) | 모델 검증 |

#### 나중에 필요시 다운로드 (선택)

| 파일명 | 설명 | 용도 |
|--------|------|------|
| TS_1. RGB Data_2.zip (97GB) | 학습용 RGB 이미지 추가 | 데이터 부족 시 |
| TS_1. RGB Data_3.zip (68GB) | 학습용 RGB 이미지 추가 | 데이터 부족 시 |

#### 다운로드 하지 않음 (스킵)

| 파일명 | 이유 |
|--------|------|
| TS_2. Hyper Spectral Data_1~6.zip | 초분광 데이터, YOLO에서 사용 불가 |
| TL_2. Hyper Spectral Label.zip | 초분광 라벨, 불필요 |
| VL_2. Hyper Spectral Label.zip | 초분광 라벨, 불필요 |
| VS_2. Hyper Spectral Data.zip | 초분광 이미지, 불필요 |

### 다운로드 순서 (중요!)

```
Step 1: TL_1 (RGB Label) 다운로드        ← 가장 먼저! (용량 작음)
        → 백점병 데이터 몇 건인지 파악
        → 정상 데이터 몇 건인지 파악

Step 2: VL_1 (RGB Label) 다운로드        ← 검증용 라벨

Step 3: TS_1. RGB Data_1.zip 다운로드    ← 이미지 1파트만 먼저

Step 4: VS_1 (RGB Data) 다운로드         ← 검증용 이미지

Step 5: (선택) 백점병 데이터가 부족하면 TS_1. RGB Data_2, _3 추가 다운로드
```

### 다운로드 후 데이터 처리 흐름

```
전체 라벨 JSON (48,765건)
    ↓ python scripts/filter_white_spot.py
    ↓
symptom == 10 (백점 증상)       → white_spot/ (4,989개 이미지)
symptom_type == None (정상)     → normal/     (10,123개 이미지)
나머지 (기타 질병)              → 버림
    ↓
Stage 1 (Seg): 백점+정상 전체 이미지 → 물고기 detection 학습 (bbox)
Stage 2 (Cls): white_spot/ vs normal/ → 이진분류 학습
```

### AIHub JSON 라벨 구조

```json
{
  "images": [{"file_name": "F01_..._I00000021", "width": 6000, "height": 4000}],
  "annotations": [
    {
      "bbox": [x_min, y_min, x_max, y_max],
      "symptom_type": 3,       // null이면 정상
      "symptom": 10,           // 10 = 백점 증상
      "disease": [21],         // 질병 코드 리스트
      "body_weight": 483,
      "body_length": 330,
      "growth_level": 2        // 1=치어, 2=준성어, 3=성어
    }
  ]
}
```

---

## 시스템 아키텍처

### 2-Stage 파이프라인

```
카메라 영상 / 이미지 입력
         |
         v
[Stage 1] YOLO-Seg: 물고기 Instance Segmentation
         |
         v
    물고기 영역 크롭 (Crop)
         |
         v
[Stage 2] YOLO-Cls: 정상 vs 백점병 이진분류
         |
         v
    결과 출력 (클래스, 확률, 위치)
         |
         v
    API 서버 -> 모바일 앱 알림
```

### Stage 1: 물고기 Segmentation
- **모델**: YOLO26n-seg (nano, 최신 경량 모델)
- **클래스**: `0: fish` (단일 클래스)
- **역할**: 수조 영상에서 개별 물고기를 분할(segmentation)

### Stage 2: 백점병 이진분류
- **모델**: YOLO26n-cls (nano, classification)
- **클래스**: `normal` / `white_spot`
- **역할**: 크롭된 물고기 이미지에서 백점병 여부 판단

### YOLO26 선택 이유
- 2026년 1월 출시, Ultralytics 최신 모델
- **엣지/임베디드 배포 최적화** (NMS-free 추론)
- CPU 추론 속도 기존 대비 최대 43% 향상
- Detection, Segmentation, Classification 모두 지원
- 모델 크기: n(nano) / s(small) / m(medium) / l(large) / x(xlarge)

---

## 백점병 (White Spot Disease) 선정 이유

| 기준 | 백점병 | 다른 질병 |
|------|--------|---------|
| 시각적 구분 | 매우 명확 (흰 점) | 애매한 경우 많음 |
| 이진분류 적합성 | 최고 | 중간~낮음 |
| 데이터 라벨링 난이도 | 쉬움 | 보통~어려움 |
| 양식장 발생 빈도 | 매우 높음 | 다양 |
| 경제적 피해 | 매우 큼 | 다양 |

---

## 프로젝트 디렉토리 구조

```
embedded_system/
├── data/
│   ├── raw/                        # AIHub 원본 데이터
│   │   ├── images/
│   │   └── labels/
│   ├── processed/
│   │   ├── segmentation/           # Stage 1 데이터
│   │   │   ├── train/images/
│   │   │   ├── train/labels/
│   │   │   ├── val/images/
│   │   │   ├── val/labels/
│   │   │   └── data.yaml
│   │   └── classification/         # Stage 2 데이터
│   │       ├── train/normal/
│   │       ├── train/white_spot/
│   │       ├── val/normal/
│   │       └── val/white_spot/
├── scripts/
│   ├── convert_labels.py           # AIHub JSON -> YOLO 포맷
│   ├── filter_white_spot.py        # 백점병 데이터 필터링
│   ├── crop_fish.py                # seg 결과로 물고기 크롭
│   └── split_dataset.py            # train/val 분할
├── models/
│   ├── seg/                        # segmentation 모델 weights
│   └── cls/                        # classification 모델 weights
├── server/                         # FastAPI 서버
├── app/                            # 모바일 앱
├── notebooks/                      # 실험용 Jupyter 노트북
├── requirements.txt
└── PROJECT_PLAN.md
```

---

## 개발 일정

| Phase | 기간 | 작업 | 산출물 |
|-------|------|------|--------|
| 0 | Day 1 | AIHub 데이터 다운로드 (라벨 우선) | raw 데이터 |
| 1 | Day 1-2 | 프로젝트 구조 + 환경 세팅 | 디렉토리, requirements.txt |
| 2 | Day 3-7 | 라벨 분석 + 데이터 전처리 | YOLO 포맷 데이터셋 |
| 3 | Day 8-14 | 모델 학습 (Seg + Cls) | 모델 weights |
| 4 | Day 15-18 | 추론 파이프라인 통합 | inference.py |
| 5 | Day 19-21 | API 서버 (FastAPI) | REST API |
| 6 | Day 22-30 | 모바일 앱 | 앱 |

---

## 학습 환경

| 환경 | 장치 | YOLO device | 적합성 |
|------|------|-------------|--------|
| **MacBook M시리즈** | Apple Silicon GPU | `mps` | 충분 (사용 예정) |
| Google Colab 무료 | T4 GPU | `cuda` | 대안 |

### 학습 방식: 목표 성능 도달까지 자동 반복 학습

단순 1회 학습이 아닌, **목표 성능에 도달할 때까지 자동으로 재학습**하는 방식 사용.
스크립트: `scripts/train_seg.py`, `scripts/train_cls.py`

```
Round 1: yolo26n (nano, 가벼운 모델) → 성능 확인
    ↓ 목표 미달?
Round 2: yolo26s (small, 더 큰 모델) → 성능 확인
    ↓ 목표 미달?
Round 3: 이전 best 모델 fine-tuning (lr 낮춤) → 성능 확인
    ↓ 목표 미달?
Round 4: 이미지 크기 증가 → 성능 확인
    ↓ 목표 미달?
Round 5: 최종 fine-tuning → 성능 확인
    ↓ 목표 달성 시 어느 라운드든 즉시 종료!
```

| 항목 | Stage 1 (Seg) | Stage 2 (Cls) |
|------|--------------|---------------|
| 목표 | mAP50 >= 0.85 | Accuracy >= 90% |
| 최대 라운드 | 5회 | 5회 |
| 전략 | 모델 크기 증가 + lr 감소 | 모델 크기 + 이미지 크기 증가 |
| 실행 | `python scripts/train_seg.py` | `python scripts/train_cls.py` |

---

## API 서버 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/predict` | 이미지 업로드 -> 분석 결과 반환 |
| GET | `/status` | 시스템 상태 확인 |
| GET | `/alerts` | 경고 기록 조회 |

### 응답 예시
```json
{
  "fish_detected": 3,
  "results": [
    {
      "fish_id": 1,
      "bbox": [100, 200, 300, 400],
      "disease": "white_spot",
      "confidence": 0.92
    }
  ],
  "alert": true,
  "timestamp": "2026-05-18T12:00:00"
}
```

---

## 모바일 앱 주요 화면

1. **대시보드**: 수조별 상태 요약 (정상/경고)
2. **실시간 모니터링**: 카메라 피드 + 탐지 결과 오버레이
3. **알림 기록**: 백점병 감지 이력
4. **상세 분석**: 감지된 물고기 크롭 이미지 + 분류 결과

---

## 모델 평가 목표

- **Segmentation**: mAP50 >= 0.85
- **Classification**: Accuracy >= 90%, F1-Score >= 0.88
- **추론 속도**: CPU 기준 10-30 FPS (ONNX 변환 후)
