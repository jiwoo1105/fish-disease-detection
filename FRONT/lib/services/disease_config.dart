// classes.yaml 을 읽어 증상→질병→행동 매핑과 위험도 점수를 계산한다.
// 원본 Python: scripts/disease_mapper.py, scripts/risk_scorer.py 와 동일한 로직.

import 'package:yaml/yaml.dart';

import '../models/results.dart';

double _round3(double v) => (v * 1000).round() / 1000.0;

class DiseaseConfig {
  final Map<String, List<Map<String, dynamic>>> symptomDiseaseMap;
  final Map<String, Map<String, dynamic>> diseaseResponse;
  final Map<String, num> symptomSeverity;
  final num watchThreshold;
  final num dangerThreshold;
  final num immediateThreshold;
  final num tankRatioDanger;
  final num tankRatioImmediate;

  DiseaseConfig({
    required this.symptomDiseaseMap,
    required this.diseaseResponse,
    required this.symptomSeverity,
    required this.watchThreshold,
    required this.dangerThreshold,
    required this.immediateThreshold,
    required this.tankRatioDanger,
    required this.tankRatioImmediate,
  });

  factory DiseaseConfig.fromYaml(String yamlString) {
    final doc = loadYaml(yamlString) as YamlMap;

    final sdm = <String, List<Map<String, dynamic>>>{};
    final rawSdm = doc['symptom_disease_map'] as YamlMap;
    for (final entry in rawSdm.entries) {
      final list = <Map<String, dynamic>>[];
      for (final d in (entry.value as YamlList)) {
        final m = d as YamlMap;
        list.add({
          'name': m['name'] as String,
          'probability': (m['probability'] as num).toDouble(),
          'contagious': (m['contagious'] as bool?) ?? false,
        });
      }
      sdm[entry.key as String] = list;
    }

    final dr = <String, Map<String, dynamic>>{};
    final rawDr = doc['disease_response'] as YamlMap;
    for (final entry in rawDr.entries) {
      final m = entry.value as YamlMap;
      dr[entry.key as String] = {
        'action': m['action'] as String? ?? 'MONITOR',
        'temperature': m['temperature'] as String? ?? '유지',
        'detail': m['detail'] as String? ?? '',
        'urgency': m['urgency'] as String? ?? 'watch',
        'isolate': (m['isolate'] as bool?) ?? false,
      };
    }

    final severity = <String, num>{};
    for (final entry in (doc['symptom_severity'] as YamlMap).entries) {
      severity[entry.key as String] = entry.value as num;
    }

    final thr = doc['risk_thresholds'] as YamlMap;

    return DiseaseConfig(
      symptomDiseaseMap: sdm,
      diseaseResponse: dr,
      symptomSeverity: severity,
      watchThreshold: thr['watch'] as num,
      dangerThreshold: thr['danger'] as num,
      immediateThreshold: thr['immediate'] as num,
      tankRatioDanger: thr['tank_disease_ratio_danger'] as num,
      tankRatioImmediate: thr['tank_disease_ratio_immediate'] as num,
    );
  }

  /// 증상으로부터 가장 가능성 높은 질병 + 대응 가이드 반환.
  /// (disease_mapper.map_symptom_to_disease 포팅)
  ({
    String? likelyDisease,
    double? diseaseConfidence,
    bool contagious,
    DiseaseResponse? response,
  }) mapSymptomToDisease(String symptom, double confidence) {
    if (symptom == 'normal' || !symptomDiseaseMap.containsKey(symptom)) {
      return (
        likelyDisease: null,
        diseaseConfidence: null,
        contagious: false,
        response: null,
      );
    }

    final diseases = symptomDiseaseMap[symptom]!;
    final top = diseases.reduce(
      (a, b) => (a['probability'] as double) >= (b['probability'] as double)
          ? a
          : b,
    );
    final diseaseName = top['name'] as String;
    final diseaseConf = _round3(confidence * (top['probability'] as double));

    final resp = diseaseResponse[diseaseName];
    return (
      likelyDisease: diseaseName,
      diseaseConfidence: diseaseConf,
      contagious: top['contagious'] as bool,
      response: resp == null
          ? null
          : DiseaseResponse(
              action: resp['action'] as String,
              temperature: resp['temperature'] as String,
              detail: resp['detail'] as String,
              urgency: resp['urgency'] as String,
              isolate: resp['isolate'] as bool,
            ),
    );
  }

  /// 개별 물고기 위험도. (risk_scorer.score_fish 포팅)
  ({double riskScore, String riskLevel}) scoreFish(
    String symptom,
    double confidence,
  ) {
    final severity = symptomSeverity[symptom] ?? 0;
    final score = _round3(severity * confidence);
    final String level;
    if (score >= immediateThreshold) {
      level = 'immediate';
    } else if (score >= dangerThreshold) {
      level = 'danger';
    } else if (score >= watchThreshold) {
      level = 'watch';
    } else {
      level = 'normal';
    }
    return (riskScore: score, riskLevel: level);
  }

  /// 수조 전체 집계 위험도. (risk_scorer.score_tank 포팅)
  TankResult scoreTank(List<FishResult> fish) {
    final total = fish.length;
    if (total == 0) {
      return const TankResult(
        fishCount: 0,
        diseasedCount: 0,
        diseaseRatio: 0.0,
        tankRiskLevel: 'normal',
        symptomSummary: {},
        hasContagious: false,
        fish: [],
      );
    }

    final diseased = fish.where((f) => f.riskLevel != 'normal').length;
    final ratio = diseased / total;
    final maxScore = fish
        .map((f) => f.riskScore)
        .fold<double>(0, (a, b) => b > a ? b : a);

    final symptomCounts = <String, int>{};
    for (final f in fish) {
      symptomCounts[f.symptom] = (symptomCounts[f.symptom] ?? 0) + 1;
    }

    final hasContagious = fish.any((f) => f.contagious);

    final String tankLevel;
    if (ratio >= tankRatioImmediate ||
        (hasContagious && maxScore >= dangerThreshold)) {
      tankLevel = 'immediate';
    } else if (ratio >= tankRatioDanger || maxScore >= dangerThreshold) {
      tankLevel = 'danger';
    } else if (diseased > 0) {
      tankLevel = 'watch';
    } else {
      tankLevel = 'normal';
    }

    return TankResult(
      fishCount: total,
      diseasedCount: diseased,
      diseaseRatio: _round3(ratio),
      tankRiskLevel: tankLevel,
      symptomSummary: symptomCounts,
      hasContagious: hasContagious,
      fish: fish,
    );
  }
}
