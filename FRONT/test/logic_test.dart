// disease_config 포팅 로직이 Python(disease_mapper/risk_scorer)과 일치하는지 검증.

import 'dart:io';

import 'package:test/test.dart';
import 'package:nupchi_doctor/models/results.dart';
import 'package:nupchi_doctor/services/disease_config.dart';

FishResult _fish({
  required int id,
  required String symptom,
  required double conf,
  required DiseaseConfig cfg,
}) {
  final m = cfg.mapSymptomToDisease(symptom, conf);
  final r = cfg.scoreFish(symptom, conf);
  return FishResult(
    fishId: id,
    bbox: BBox.zero,
    detConfidence: 0.9,
    symptom: symptom,
    symptomConfidence: conf,
    likelyDisease: m.likelyDisease,
    diseaseConfidence: m.diseaseConfidence,
    contagious: m.contagious,
    response: m.response,
    riskScore: r.riskScore,
    riskLevel: r.riskLevel,
  );
}

void main() {
  late DiseaseConfig cfg;

  setUpAll(() {
    final yaml = File('assets/config/classes.yaml').readAsStringSync();
    cfg = DiseaseConfig.fromYaml(yaml);
  });

  test('normal 은 질병/행동 없음', () {
    final m = cfg.mapSymptomToDisease('normal', 0.99);
    expect(m.likelyDisease, isNull);
    expect(m.response, isNull);
    expect(m.contagious, false);
    expect(cfg.scoreFish('normal', 0.99).riskLevel, 'normal');
  });

  test('white_spot → 스쿠티카병 + 수온 낮추기 행동', () {
    final m = cfg.mapSymptomToDisease('white_spot', 0.9);
    expect(m.likelyDisease, '스쿠티카병');
    expect(m.diseaseConfidence, 0.63); // round(0.9*0.7)
    expect(m.contagious, true);
    expect(m.response!.action, 'LOWER_TEMPERATURE');
    expect(m.response!.urgency, 'immediate');
    expect(m.response!.isolate, true);
  });

  test('scoreFish 위험도 등급 경계', () {
    expect(cfg.scoreFish('white_spot', 0.9).riskScore, 3.6); // 4*0.9
    expect(cfg.scoreFish('white_spot', 0.9).riskLevel, 'danger');
    expect(cfg.scoreFish('ulcer', 0.9).riskLevel, 'immediate'); // 5*0.9=4.5
    expect(cfg.scoreFish('color_change', 0.5).riskLevel, 'normal'); // 2*0.5=1.0<1.5
    expect(cfg.scoreFish('color_change', 0.8).riskLevel, 'watch'); // 2*0.8=1.6
  });

  test('scoreTank: 전염성 + 고위험 → immediate', () {
    final fish = [
      _fish(id: 1, symptom: 'normal', conf: 0.95, cfg: cfg),
      _fish(id: 2, symptom: 'white_spot', conf: 0.9, cfg: cfg), // danger, contagious
    ];
    final tank = cfg.scoreTank(fish);
    expect(tank.fishCount, 2);
    expect(tank.diseasedCount, 1);
    expect(tank.hasContagious, true);
    // ratio 0.5 >= 0.30 → immediate
    expect(tank.tankRiskLevel, 'immediate');
    expect(tank.alerts.length, 1);
  });

  test('scoreTank: 빈 입력 → normal', () {
    final tank = cfg.scoreTank([]);
    expect(tank.fishCount, 0);
    expect(tank.tankRiskLevel, 'normal');
  });
}
