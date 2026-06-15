# 넙치닥터 (Nupchi Doctor)

넙치(광어) 질병을 **휴대폰에서 완전 온디바이스**로 탐지하고, 질병이 감지되면 **대응 행동**을 알려주는 안드로이드 앱.
원본 파이프라인([fish-disease-detection](https://github.com/jiwoo1105/fish-disease-detection))의 YOLO 모델과 질병 매핑 로직을 폰에서 그대로 재현한다 (서버 불필요).

## 동작 구조 (3-Stage 온디바이스 파이프라인)

```
사진/카메라 입력
   │
   ▼
[1] det.tflite   넙치 탐지 → 바운딩박스           (ultralytics_yolo, detect)
   │  └─ 박스 영역을 Dart(image 패키지)로 크롭
   ▼
[2] cls.tflite   크롭된 물고기 증상 분류           (ultralytics_yolo, classify)
   │             normal/hemorrhage/white_spot/tumor/color_change/emaciation/ulcer
   ▼
[3] classes.yaml 증상→질병→대응행동 매핑 + 위험도   (lib/services/disease_config.dart)
   │
   ▼
수조 상태 배너 + 질병별 "다음 행동" 카드
```

- `det.tflite`, `cls.tflite` 는 원본 `best_det.pt`, `best_cls.pt` 를 TFLite(float32)로 변환한 것.
- 두 모델은 `useMultiInstance: true` 로 동시에 메모리에 올려 Dart 에서 체이닝한다.
- 질병 매핑/위험도/대응행동 로직은 `assets/config/classes.yaml` 을 읽어 계산 (Python `disease_mapper.py`·`risk_scorer.py` 와 동일, 단위 테스트로 검증).
- 원본 2.5단계(병변 위치 `lesion_det`)는 v1 에서 제외 (원본 코드에서도 optional).

## 프로젝트 구조

```
lib/
├── main.dart                     앱 진입점
├── labels.dart                   영문코드→한글 라벨/색상
├── models/results.dart           BBox / FishResult / TankResult / DiseaseResponse
├── services/
│   ├── disease_config.dart       classes.yaml 파싱 + 증상→질병 매핑 + 위험도 계산
│   ├── pipeline_service.dart     det→크롭→cls 체인 (ultralytics_yolo)
│   └── annotate.dart             결과 박스 시각화 (image 패키지)
├── widgets/action_card.dart      "다음 행동" 카드
└── screens/home_screen.dart      촬영/갤러리 + 결과 화면
assets/
├── models/{det,cls}.tflite
└── config/classes.yaml
test/logic_test.dart              순수 Dart 로직 테스트 (dart test)
```

## 빌드 & 실행 (안드로이드)

```bash
flutter pub get
dart test test/logic_test.dart      # 로직 검증
flutter build apk --debug           # 또는: flutter run  (기기 연결 시)
# 산출물: build/app/outputs/flutter-apk/app-debug.apk
```

설치: `adb install -r build/app/outputs/flutter-apk/app-debug.apk`

### ⚠️ 한글 사용자명(경로) Windows 빌드 주의

이 PC 처럼 경로에 한글(`C:\Users\안균승\...`)이 있으면 Gradle/AGP 가 경로를 깨뜨려(ISO-8859-1) 빌드가 실패한다. **ASCII 정션으로 우회**한다 (관리자 권한 불필요):

```powershell
# 1) Flutter SDK / Android SDK / pub 캐시 / 프로젝트를 모두 ASCII 경로로 정션
cmd /c "mklink /J C:\fdd_flutter     `"$env:USERPROFILE\Documents\flutter`""
cmd /c "mklink /J C:\fdd_androidsdk  `"$env:USERPROFILE\AppData\Local\Android\sdk`""
cmd /c "mklink /J C:\fdd_pubcache    `"$env:LOCALAPPDATA\Pub\Cache`""
cmd /c "mklink /J C:\fdd_app         `"$env:USERPROFILE\Desktop\dev\fish_disease_detection\nupchi_doctor`""

# 2) 모든 경로를 ASCII 로 지정해서 빌드 (jni 등 네이티브 패키지는 ninja 가 한글 경로를 못 읽음)
Set-Location C:\fdd_app
$env:PUB_CACHE="C:\fdd_pubcache"
$env:ANDROID_SDK_ROOT="C:\fdd_androidsdk"; $env:ANDROID_HOME="C:\fdd_androidsdk"
& C:\fdd_flutter\bin\flutter.bat pub get
& C:\fdd_flutter\bin\flutter.bat build apk --debug
```

추가로 적용된 설정:
- `android/settings.gradle.kts` — `local.properties` 를 UTF-8 로 읽도록 수정
- `android/gradle.properties` — `android.overridePathCheck=true`, `-Dfile.encoding=UTF-8`
- `android/app/build.gradle.kts` — `minSdk 24`, `compileSdk 36`

## 모델 교체 (재학습 후)

```bash
# 원본 저장소에서 .pt → .tflite 변환
venv/Scripts/python.exe scripts/export_tflite.py
# 생성된 *_float32.tflite 를 앱 에셋으로 복사
cp models/det/best_det_saved_model/best_det_float32.tflite  <app>/assets/models/det.tflite
cp models/cls/best_cls_saved_model/best_cls_float32.tflite  <app>/assets/models/cls.tflite
```
모델의 클래스 이름(`names`)이 `classes.yaml` 의 `symptom_classes` 값과 일치해야 한다.

## 변경 사항 (직전 커밋 대비)

### 분류 신뢰도 게이트 상향: `0.25 → 0.85`

- 위치: `lib/services/pipeline_service.dart` 의 `clsConfThreshold`
- 동작: Stage 2(cls)의 top-1 confidence 가 게이트 **미만이면 정상**으로 본다.
- 배경: 탁한 물(수조) 환경의 **정상 넙치가 질병으로 오판**되는 문제를 줄이기 위해 게이트를 강하게 높였다. (실측 결과, 흙탕물 정상 사진의 질병 오답 신뢰도가 게이트 아래로 떨어져 정상 처리됨)
- ⚠️ **한계 (임시 조치)**: 게이트가 0.85 로 매우 높아 **신뢰도 0.85 미만의 질병은 모두 정상 처리**된다. 즉 사실상 질병 탐지 민감도를 크게 낮춘 밴드에이드이며, 진짜 경증 질병도 놓칠 수 있다.
- 근본 해결책: 실제 사용 환경(탁한 물)의 정상 넙치 사진을 모아 `best_cls.pt` 를 **파인튜닝**한 뒤 게이트를 정상 범위로 되돌린다.
