// 분석 결과 데이터 모델 (Python inference.py 의 결과 구조를 Dart 로 옮긴 것)
// dart:ui 에 의존하지 않도록 자체 BBox 를 사용한다 (순수 Dart 단위 테스트 가능).

/// 바운딩 박스 (픽셀 좌표).
class BBox {
  final double left;
  final double top;
  final double right;
  final double bottom;
  const BBox(this.left, this.top, this.right, this.bottom);
  static const zero = BBox(0, 0, 0, 0);
}

/// 질병 감지 시 사용자가 취해야 할 "다음 행동" 가이드.
/// classes.yaml 의 disease_response 항목과 1:1 대응.
class DiseaseResponse {
  final String action; // 예: LOWER_TEMPERATURE
  final String temperature; // 예: "18도 이하로 낮추기"
  final String detail;
  final String urgency; // immediate | danger | watch
  final bool isolate;

  const DiseaseResponse({
    required this.action,
    required this.temperature,
    required this.detail,
    required this.urgency,
    required this.isolate,
  });
}

/// 개별 물고기 한 마리의 분석 결과.
class FishResult {
  final int fishId;
  final BBox bbox; // 원본 이미지 픽셀 좌표
  final double detConfidence;
  final String symptom; // normal | white_spot | hemorrhage | ...
  final double symptomConfidence;
  final String? likelyDisease;
  final double? diseaseConfidence;
  final bool contagious;
  final DiseaseResponse? response;
  final double riskScore;
  final String riskLevel; // normal | watch | danger | immediate

  const FishResult({
    required this.fishId,
    required this.bbox,
    required this.detConfidence,
    required this.symptom,
    required this.symptomConfidence,
    required this.likelyDisease,
    required this.diseaseConfidence,
    required this.contagious,
    required this.response,
    required this.riskScore,
    required this.riskLevel,
  });

  bool get isDiseased => riskLevel != 'normal';
}

/// 수조(이미지) 전체 집계 결과.
class TankResult {
  final int fishCount;
  final int diseasedCount;
  final double diseaseRatio;
  final String tankRiskLevel; // normal | watch | danger | immediate
  final Map<String, int> symptomSummary;
  final bool hasContagious;
  final List<FishResult> fish;

  const TankResult({
    required this.fishCount,
    required this.diseasedCount,
    required this.diseaseRatio,
    required this.tankRiskLevel,
    required this.symptomSummary,
    required this.hasContagious,
    required this.fish,
  });

  /// watch 이상인 물고기들의 행동 가이드 목록 (UI 알림 카드용).
  List<FishResult> get alerts =>
      fish.where((f) => f.isDiseased && f.response != null).toList();
}
