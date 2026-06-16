// 이상 탐지 결과 1건 (결과 탭에서 시간대별로 표시).
// 수조 영상 종료 후 "확인" 을 누르면 그 수조의 지정 증상으로 1건이 추가된다.

import '../labels.dart';
import '../services/disease_config.dart';
import '../tank_config.dart';

class DetectionRecord {
  final String tankId;
  final String tankName;
  final DateTime time;
  final List<String> symptoms; // 증상 키 목록
  final String disease; // 대표 의심 질병명
  final String riskLevel; // immediate | danger | watch | normal

  const DetectionRecord({
    required this.tankId,
    required this.tankName,
    required this.time,
    required this.symptoms,
    required this.disease,
    required this.riskLevel,
  });

  /// 수조 설정 + classes.yaml 로부터 결과 1건 생성.
  /// 여러 증상이면 가장 심각한 증상의 위험도/질병을 대표로 삼는다.
  factory DetectionRecord.fromTank(
      TankConfig tank, DiseaseConfig cfg, DateTime time) {
    final actual = tank.symptoms.where((s) => s != 'normal').toList();
    String worst = 'normal';
    String disease = '';
    for (final s in actual) {
      final g = cfg.symptomGuide(s);
      final u = g?.response?.urgency ?? 'normal';
      if (urgencyRank(u) > urgencyRank(worst)) {
        worst = u;
        disease = g?.disease ?? '';
      }
    }
    if (disease.isEmpty && actual.isNotEmpty) {
      disease = cfg.symptomGuide(actual.first)?.disease ?? '';
    }
    return DetectionRecord(
      tankId: tank.id,
      tankName: tank.name,
      time: time,
      symptoms: actual,
      disease: disease,
      riskLevel: worst,
    );
  }

  Map<String, dynamic> toJson() => {
        'tankId': tankId,
        'tankName': tankName,
        'time': time.toIso8601String(),
        'symptoms': symptoms,
        'disease': disease,
        'riskLevel': riskLevel,
      };

  factory DetectionRecord.fromJson(Map<String, dynamic> j) => DetectionRecord(
        tankId: j['tankId'] as String? ?? '',
        tankName: j['tankName'] as String? ?? '',
        time: DateTime.tryParse(j['time'] as String? ?? '') ?? DateTime(2000),
        symptoms: (j['symptoms'] as List?)?.cast<String>() ?? const [],
        disease: j['disease'] as String? ?? '',
        riskLevel: j['riskLevel'] as String? ?? 'normal',
      );
}
