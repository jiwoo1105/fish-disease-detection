// 모니터링/영상 분석 종료 요약 다이얼로그 (라이브·영상 공용).
// 세션 요약 + 병별 대응 가이드(하드코딩)를 함께 보여준다.

import 'package:flutter/material.dart';

import '../disease_guide.dart';
import '../labels.dart';
import '../models/tank.dart';

Future<void> showTankSummaryDialog(
  BuildContext context,
  String tankName,
  TankSummary s,
) {
  final color = riskColor(s.riskLevel);
  final hasDisease =
      s.diseasedCount > 0 && s.topSymptom != null && s.topSymptom != 'normal';
  final guide = hasDisease ? diseaseGuide[s.topSymptom] : null;

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
          Expanded(child: Text('$tankName 요약')),
        ],
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('상태: ${urgencyLabel(s.riskLevel)}',
                style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.bold, color: color)),
            const SizedBox(height: 8),
            Text('관측된 넙치: 최대 ${s.maxFish}마리'),
            Text('이상 징후: ${s.diseasedCount}마리'),
            if (guide != null) ...[
              const Divider(height: 22),
              Text(
                '의심 질병: ${s.topDisease ?? guide.disease}',
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('🌡 '),
                  Expanded(
                    child: Text(guide.tempAction,
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text('대응 방안',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 2),
              for (final step in guide.steps)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text('· $step'),
                ),
              if (guide.isolate) ...[
                const SizedBox(height: 8),
                const Text('⚠ 감염 개체 즉시 격리',
                    style: TextStyle(
                        color: Color(0xFFD32F2F),
                        fontWeight: FontWeight.bold)),
              ],
            ] else ...[
              const SizedBox(height: 8),
              const Text('✅ 이상 징후가 관측되지 않았습니다.'),
            ],
          ],
        ),
      ),
      actions: [
        FilledButton(
          onPressed: () => Navigator.of(ctx).pop(),
          child: const Text('확인'),
        ),
      ],
    ),
  );
}
