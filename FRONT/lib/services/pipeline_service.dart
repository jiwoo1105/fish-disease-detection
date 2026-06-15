// 온디바이스 3-Stage 추론 파이프라인 (Python inference.analyze_image 포팅)
//   Stage 1: det.tflite  → 넙치 탐지 + 크롭
//   Stage 2: cls.tflite  → 크롭된 물고기를 7개 클래스로 분류
//                          (normal/color_change/emaciation/hemorrhage/tumor/ulcer/white_spot)
//   Stage 3: DiseaseConfig → 질병 매핑 + 위험도 + 다음 행동
//
// det / cls 모델을 useMultiInstance 로 동시에 메모리에 올리고, det 결과 박스를
// image 패키지로 크롭해 cls 에 넘긴다. (네이티브 플러그인 수정 불필요)
// cls 는 크롭 1장당 top-1 클래스를 내놓는다. top-1 이 normal 이면 정상, 아니면 해당 질병.

import 'dart:typed_data';
import 'dart:ui';

import 'package:flutter/services.dart' show rootBundle;
import 'package:image/image.dart' as img;
import 'package:ultralytics_yolo/ultralytics_yolo.dart';

import '../models/results.dart';
import 'disease_config.dart';

class PipelineService {
  static const _detAsset = 'assets/models/det.tflite';
  static const _clsAsset = 'assets/models/cls.tflite';
  static const _configAsset = 'assets/config/classes.yaml';

  // 물고기 탐지 신뢰도 임계값. tflite 변환 후 det 신뢰도가 크게 낮아져(.pt 0.26 → tflite ~0.08),
  // 특히 개체가 화면을 꽉 채우면 더 낮다. 개체를 놓치지 않도록 0.05 로 낮춘다.
  // (배경이 복잡하면 오탐이 늘 수 있어, 깨끗한 클로즈업 사용을 권장)
  static const double detConfThreshold = 0.05;

  // 분류 신뢰도 임계값: cls top-1 confidence 가 이 값 미만이면 정상으로 본다.
  // (불확실한 저신뢰 질병 예측이 오경보로 이어지지 않게 하는 게이트)
  // 0.25 → 0.85 임시 상향: test8/9(흙탕물 정상)를 전부 정상으로 판별하도록 강하게 높임.
  // ※ 사실상 질병 탐지를 거의 끈 상태 — 신뢰도 0.85 미만 질병은 모두 정상 처리됨.
  //   근본 해결 아님(밴드에이드). 파인튜닝으로 대체 예정.
  static const double clsConfThreshold = 0.85;

  // 탐지 전용 모드: Stage 2(cls/질병)를 건너뛰고 넙치 박스만 잡는다.
  // (Stage 1 탐지 검증 완료 → 질병 분류 다시 켬)
  static const bool detectionOnly = false;

  late final DiseaseConfig _config;
  late final YOLO _det;
  late final YOLO _cls;
  bool _ready = false;

  bool get isReady => _ready;

  Future<void> init() async {
    if (_ready) return;

    final yamlStr = await rootBundle.loadString(_configAsset);
    _config = DiseaseConfig.fromYaml(yamlStr);

    _det = YOLO(
      modelPath: _detAsset,
      task: YOLOTask.detect,
      useMultiInstance: true,
      useGpu: true, // GPU 델리게이트 가속 (FP16 모델과 궁합이 좋음)
    );
    _cls = YOLO(
      modelPath: _clsAsset,
      task: YOLOTask.classify,
      useMultiInstance: true,
      useGpu: true,
    );

    await _det.loadModel();
    await _cls.loadModel();
    _ready = true;
  }

  Future<void> dispose() async {
    if (!_ready) return;
    await _det.dispose();
    await _cls.dispose();
    _ready = false;
  }

  /// 이미지 1장 분석 → 수조 집계 결과.
  Future<TankResult> analyze(Uint8List imageBytes) async {
    if (!_ready) {
      throw StateError('PipelineService.init() 을 먼저 호출하세요.');
    }
    final decoded = img.decodeImage(imageBytes);
    if (decoded == null) {
      throw const FormatException('이미지를 디코딩할 수 없습니다.');
    }
    return analyzeDecoded(decoded, imageBytes);
  }

  /// 이미 디코딩된 이미지(크롭용)와 det 입력용 JPEG 바이트로 분석.
  /// 라이브 카메라에서 프레임당 재디코딩을 피하기 위해 사용한다.
  Future<TankResult> analyzeDecoded(
    img.Image decoded,
    Uint8List detBytes,
  ) async {
    if (!_ready) {
      throw StateError('PipelineService.init() 을 먼저 호출하세요.');
    }

    // Stage 1: 넙치 탐지
    final detResult = await _det.predict(
      detBytes,
      confidenceThreshold: detConfThreshold,
    );
    final detections = (detResult['detections'] as List?)
            ?.whereType<Map>()
            .map(YOLOResult.fromMap)
            .toList() ??
        const <YOLOResult>[];

    final fishResults = <FishResult>[];
    var fishId = 0;

    for (final det in detections) {
      final b0 = det.boundingBox;

      // 탐지 전용: cls/질병 건너뛰고 넙치 박스만 기록
      if (detectionOnly) {
        fishId++;
        fishResults.add(FishResult(
          fishId: fishId,
          bbox: BBox(b0.left, b0.top, b0.right, b0.bottom),
          detConfidence: det.confidence,
          symptom: 'normal',
          symptomConfidence: 0,
          likelyDisease: null,
          diseaseConfidence: null,
          contagious: false,
          response: null,
          riskScore: 0,
          riskLevel: 'normal',
        ));
        continue;
      }

      final crop = _cropToBytes(decoded, det.boundingBox);
      if (crop == null) continue;
      fishId++;

      // Stage 2: 7-class 분류 (cls) — 크롭된 넙치를 질병/정상으로 분류한다.
      final clsResult = await _cls.predict(
        crop,
        confidenceThreshold: clsConfThreshold,
      );
      final clsDetections = (clsResult['detections'] as List?)
              ?.whereType<Map>()
              .map(YOLOResult.fromMap)
              .toList() ??
          const <YOLOResult>[];

      // classify 는 크롭 1장당 top-1 클래스를 돌려준다.
      // top-1 confidence 가 게이트 미만이거나 결과가 없으면 정상으로 본다.
      var symptom = 'normal';
      var symptomConf = 0.0;
      if (clsDetections.isNotEmpty &&
          clsDetections.first.confidence >= clsConfThreshold) {
        symptom = clsDetections.first.className;
        symptomConf = clsDetections.first.confidence;
      }

      // Stage 3: 질병 매핑 + 위험도
      final mapped = _config.mapSymptomToDisease(symptom, symptomConf);
      final risk = _config.scoreFish(symptom, symptomConf);

      final b = det.boundingBox;
      fishResults.add(FishResult(
        fishId: fishId,
        bbox: BBox(b.left, b.top, b.right, b.bottom),
        detConfidence: det.confidence,
        symptom: symptom,
        symptomConfidence: symptomConf,
        likelyDisease: mapped.likelyDisease,
        diseaseConfidence: mapped.diseaseConfidence,
        contagious: mapped.contagious,
        response: mapped.response,
        riskScore: risk.riskScore,
        riskLevel: risk.riskLevel,
      ));
    }

    return _config.scoreTank(fishResults);
  }

  /// bbox 영역을 원본 이미지에서 크롭해 JPEG 바이트로 인코딩.
  Uint8List? _cropToBytes(img.Image src, Rect box) {
    final x1 = box.left.floor().clamp(0, src.width - 1);
    final y1 = box.top.floor().clamp(0, src.height - 1);
    final x2 = box.right.ceil().clamp(0, src.width);
    final y2 = box.bottom.ceil().clamp(0, src.height);
    final w = x2 - x1;
    final h = y2 - y1;
    if (w <= 1 || h <= 1) return null;

    final cropped = img.copyCrop(src, x: x1, y: y1, width: w, height: h);
    // cls 입력용 — 품질 80 이면 충분하고 인코딩이 더 빠르다(메인 스레드 부하 완화).
    return Uint8List.fromList(img.encodeJpg(cropped, quality: 80));
  }
}
