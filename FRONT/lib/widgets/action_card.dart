// 질병이 감지된 물고기 한 마리에 대한 "다음 행동" 카드.

import 'package:flutter/material.dart';

import '../labels.dart';
import '../models/results.dart';

class ActionCard extends StatelessWidget {
  final FishResult fish;
  const ActionCard({super.key, required this.fish});

  @override
  Widget build(BuildContext context) {
    final resp = fish.response!;
    final color = riskColor(resp.urgency);
    final theme = Theme.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: color, width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 헤더: 물고기 번호 + 긴급도 배지
            Row(
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: color,
                  child: Text('${fish.fishId}',
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    '${fish.likelyDisease ?? '-'} 의심',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.bold),
                  ),
                ),
                _Badge(text: urgencyLabel(resp.urgency), color: color),
              ],
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                _chip('증상: ${symptomLabel(fish.symptom)}'),
                _chip('신뢰도 ${(fish.symptomConfidence * 100).round()}%'),
                if (fish.contagious)
                  _chip('전염성', bg: color.withValues(alpha: 0.15), fg: color),
              ],
            ),
            const Divider(height: 20),
            // 핵심: 다음 행동
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(actionIcon[resp.action] ?? Icons.task_alt, color: color),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(actionLabel(resp.action),
                          style: theme.textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.bold)),
                      if (resp.temperature.isNotEmpty &&
                          resp.temperature != '유지')
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text('🌡 수온: ${resp.temperature}',
                              style: theme.textTheme.bodyMedium),
                        ),
                      if (resp.isolate)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text('⚠ 감염 개체 즉시 격리',
                              style: theme.textTheme.bodyMedium
                                  ?.copyWith(color: color)),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            if (resp.detail.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(resp.detail,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: Colors.black87)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _chip(String text, {Color? bg, Color? fg}) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: bg ?? Colors.black.withValues(alpha: 0.06),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(text,
            style: TextStyle(fontSize: 12, color: fg ?? Colors.black87)),
      );
}

class _Badge extends StatelessWidget {
  final String text;
  final Color color;
  const _Badge({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(text,
          style: const TextStyle(
              color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
    );
  }
}
