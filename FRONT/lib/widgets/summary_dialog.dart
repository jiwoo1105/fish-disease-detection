// 모니터링/영상 분석 종료 요약 다이얼로그 (라이브·영상 공용).
// 세션 요약 + 병별 대응 가이드를 보여준다.
// 가이드는 번들된 classes.yaml 을 그대로 읽어 표시한다 (단일 소스).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;

import '../labels.dart';
import '../services/disease_config.dart';
import '../models/tank.dart';

DiseaseConfig? _cachedConfig;

Future<DiseaseConfig> loadDiseaseConfig() async {
  return _cachedConfig ??= DiseaseConfig.fromYaml(
      await rootBundle.loadString('assets/config/classes.yaml'));
}

/// 수조에 지정된 증상들의 대응 방안(classes.yaml)만 보여준다.
/// 모델/분석 없이 영상만 재생하는 데모용 — 종료 시 호출.
/// 증상이 여러 개면 각각의 의심 질병·대응 방안을 차례로 표시한다.
Future<void> showSymptomGuideDialog(
  BuildContext context,
  String tankName,
  List<String> symptoms,
) async {
  final cfg = await loadDiseaseConfig();
  final actual = symptoms.where((s) => s != 'normal').toList();
  // 가장 심각한 증상의 위험도로 헤더 색을 정한다.
  String worst = 'normal';
  for (final s in actual) {
    final u = cfg.symptomGuide(s)?.response?.urgency ?? 'normal';
    if (urgencyRank(u) > urgencyRank(worst)) worst = u;
  }
  final color = riskColor(worst);

  if (!context.mounted) return;

  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Row(
        children: [
          Icon(
            actual.isEmpty ? Icons.check_circle : Icons.warning_amber_rounded,
            color: color,
          ),
          const SizedBox(width: 8),
          Expanded(child: Text('$tankName Diagnosis')),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Observed symptoms: ${actual.map(symptomLabel).join(', ')}',
                style: const TextStyle(fontWeight: FontWeight.w600)),
            if (actual.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text('✅ Normal — no notable symptoms observed.'),
              )
            else
              for (final s in actual) _symptomSection(cfg, s),
          ],
        ),
      ),
      actions: [
        FilledButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('OK'),
        ),
      ],
    ),
  );
}

Widget _symptomSection(DiseaseConfig cfg, String symptom) {
  final guide = cfg.symptomGuide(symptom);
  final resp = guide?.response;
  final color = riskColor(resp?.urgency ?? 'normal');

  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      const Divider(height: 22),
      Text('[${symptomLabel(symptom)}] Suspected disease: ${guide?.disease ?? '-'}',
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
      if ((guide?.pathogen ?? '').isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Text('Pathogen: ${guide!.pathogen}',
              style: const TextStyle(fontSize: 12, color: Colors.black54)),
        ),
      if ((guide?.mortality ?? '').isNotEmpty)
        Text('Mortality: ${guide!.mortality}',
            style: const TextStyle(fontSize: 12, color: Colors.black54)),
      if (resp != null) ...[
        const SizedBox(height: 8),
        if (resp.temperature.isNotEmpty && resp.temperature != 'Maintain')
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('🌡 '),
              Expanded(
                child: Text('Temperature: ${resp.temperature}',
                    style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
            ],
          ),
        const SizedBox(height: 6),
        const Text('Response measures',
            style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 2),
        for (final step in resp.steps)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text('· $step'),
          ),
        if (resp.warning.isNotEmpty) ...[
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text('⚠ ${resp.warning}',
                style: TextStyle(color: color, fontWeight: FontWeight.w600)),
          ),
        ],
        if (resp.isolate) ...[
          const SizedBox(height: 6),
          const Text('⚠ Isolate infected fish immediately',
              style: TextStyle(
                  color: Color(0xFFD32F2F), fontWeight: FontWeight.bold)),
        ],
      ],
    ],
  );
}

Future<void> showTankSummaryDialog(
  BuildContext context,
  String tankName,
  TankSummary s,
) async {
  _cachedConfig ??= DiseaseConfig.fromYaml(
      await rootBundle.loadString('assets/config/classes.yaml'));
  final cfg = _cachedConfig!;

  final hasDisease =
      s.diseasedCount > 0 && s.topSymptom != null && s.topSymptom != 'normal';
  final guide = hasDisease ? cfg.symptomGuide(s.topSymptom!) : null;
  final resp = guide?.response;
  final color = riskColor(s.riskLevel);

  if (!context.mounted) return;

  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Row(
        children: [
          Icon(
            s.riskLevel == 'normal'
                ? Icons.check_circle
                : Icons.warning_amber_rounded,
            color: color,
          ),
          const SizedBox(width: 8),
          Expanded(child: Text('$tankName Summary')),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Status: ${urgencyLabel(s.riskLevel)}',
                style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.bold, color: color)),
            const SizedBox(height: 8),
            Text('Observed flatfish: up to ${s.maxFish}'),
            Text('Abnormal signs: ${s.diseasedCount}'),
            if (guide != null) ...[
              const Divider(height: 22),
              Text('Suspected disease: ${guide.disease}',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold)),
              if (guide.pathogen.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text('Pathogen: ${guide.pathogen}',
                      style: const TextStyle(
                          fontSize: 12, color: Colors.black54)),
                ),
              if (guide.mortality.isNotEmpty)
                Text('Mortality: ${guide.mortality}',
                    style: const TextStyle(
                        fontSize: 12, color: Colors.black54)),
              if (resp != null) ...[
                const SizedBox(height: 8),
                if (resp.temperature.isNotEmpty && resp.temperature != 'Maintain')
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('🌡 '),
                      Expanded(
                        child: Text('Temperature: ${resp.temperature}',
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                      ),
                    ],
                  ),
                const SizedBox(height: 6),
                const Text('Response measures',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 2),
                for (final step in resp.steps)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text('· $step'),
                  ),
                if (resp.warning.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text('⚠ ${resp.warning}',
                        style: TextStyle(
                            color: color, fontWeight: FontWeight.w600)),
                  ),
                ],
                if (resp.isolate) ...[
                  const SizedBox(height: 6),
                  const Text('⚠ Isolate infected fish immediately',
                      style: TextStyle(
                          color: Color(0xFFD32F2F),
                          fontWeight: FontWeight.bold)),
                ],
              ],
            ] else ...[
              const SizedBox(height: 8),
              const Text('✅ No abnormal signs observed.'),
            ],
          ],
        ),
      ),
      actions: [
        FilledButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('OK'),
        ),
      ],
    ),
  );
}
