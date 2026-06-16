// 결과 탭: 이상 탐지 결과를 시간대별(최신순)로 보여준다.
// 수조 영상 종료 후 "확인" 을 누르면 ResultsStore 에 1건 추가되고 자동 반영된다.

import 'package:flutter/material.dart';

import '../labels.dart';
import '../models/detection_record.dart';
import '../services/results_store.dart';
import '../widgets/summary_dialog.dart';

class ResultsScreen extends StatelessWidget {
  const ResultsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Detection Results'),
        backgroundColor: const Color(0xFF0277BD),
        foregroundColor: Colors.white,
      ),
      body: ValueListenableBuilder<List<DetectionRecord>>(
        valueListenable: ResultsStore.instance.records,
        builder: (context, records, _) {
          if (records.isEmpty) {
            return const Center(
              child: Text('No detection results yet.',
                  style: TextStyle(color: Colors.black54)),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: records.length,
            separatorBuilder: (_, _) => const SizedBox(height: 8),
            itemBuilder: (context, i) => _RecordTile(record: records[i]),
          );
        },
      ),
    );
  }
}

class _RecordTile extends StatelessWidget {
  final DetectionRecord record;
  const _RecordTile({required this.record});

  @override
  Widget build(BuildContext context) {
    final color = riskColor(record.riskLevel);
    final symptomText =
        record.symptoms.map(symptomLabel).join(', ');
    return Card(
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: color.withValues(alpha: 0.5)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => showSymptomGuideDialog(
            context, record.tankName, record.symptoms),
        child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 10,
              height: 10,
              margin: const EdgeInsets.only(top: 5, right: 10),
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(record.tankName,
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 15)),
                      const SizedBox(width: 8),
                      _badge(urgencyLabel(record.riskLevel), color),
                      const Spacer(),
                      Text(_fmtTime(record.time),
                          style: const TextStyle(
                              color: Colors.black54, fontSize: 12)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text('Symptom: $symptomText',
                      style: const TextStyle(fontSize: 13)),
                  if (record.disease.isNotEmpty)
                    Text('Suspected: ${record.disease}',
                        style: TextStyle(
                            fontSize: 13,
                            color: color,
                            fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ],
        ),
        ),
      ),
    );
  }

  Widget _badge(String text, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Text(text,
            style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 11)),
      );

  static String _fmtTime(DateTime t) {
    String two(int n) => n.toString().padLeft(2, '0');
    return '${t.month}/${t.day} ${two(t.hour)}:${two(t.minute)}';
  }
}
