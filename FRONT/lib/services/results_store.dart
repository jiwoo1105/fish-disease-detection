// 이상 탐지 결과 저장소 (결과 탭).
// shared_preferences 에 JSON 리스트로 저장하고, ValueNotifier 로 결과 탭을 자동 갱신한다.
// 최초 실행 시 임의 샘플 몇 건을 미리 채운다.

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/detection_record.dart';

class ResultsStore {
  ResultsStore._();
  static final ResultsStore instance = ResultsStore._();

  static const _key = 'results_v2';

  /// 최신순(시간 내림차순) 결과 목록.
  final ValueNotifier<List<DetectionRecord>> records = ValueNotifier([]);
  bool _loaded = false;

  Future<void> ensureLoaded() async {
    if (_loaded) return;
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key);
    if (raw == null) {
      records.value = _seed();
      await _persist();
    } else {
      records.value = raw
          .map((s) =>
              DetectionRecord.fromJson(jsonDecode(s) as Map<String, dynamic>))
          .toList()
        ..sort((a, b) => b.time.compareTo(a.time));
    }
    _loaded = true;
  }

  Future<void> add(DetectionRecord r) async {
    records.value = [r, ...records.value]
      ..sort((a, b) => b.time.compareTo(a.time));
    await _persist();
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(
        _key, records.value.map((r) => jsonEncode(r.toJson())).toList());
  }

  // 데모용 임의 샘플 (최초 1회). 현재 시각 기준 과거로 분포.
  List<DetectionRecord> _seed() {
    final now = DateTime.now();
    final list = [
      DetectionRecord(
        tankId: 'tank2',
        tankName: 'Tank 2',
        time: now.subtract(const Duration(minutes: 18)),
        symptoms: ['ulcer'],
        disease: 'Vibriosis',
        riskLevel: 'danger',
      ),
      DetectionRecord(
        tankId: 'tank1',
        tankName: 'Tank 1',
        time: now.subtract(const Duration(hours: 3, minutes: 25)),
        symptoms: ['hemorrhage'],
        disease: 'VHS (Viral Hemorrhagic Septicemia)',
        riskLevel: 'immediate',
      ),
      DetectionRecord(
        tankId: 'tank4',
        tankName: 'Tank 4',
        time: now.subtract(const Duration(hours: 20)),
        symptoms: ['hemorrhage', 'white_spot'],
        disease: 'Scuticociliatosis',
        riskLevel: 'immediate',
      ),
      DetectionRecord(
        tankId: 'tank3',
        tankName: 'Tank 3',
        time: now.subtract(const Duration(days: 1, hours: 6)),
        symptoms: ['tumor'],
        disease: 'Lymphocystis disease',
        riskLevel: 'watch',
      ),
      DetectionRecord(
        tankId: 'tank2',
        tankName: 'Tank 2',
        time: now.subtract(const Duration(days: 2, hours: 2)),
        symptoms: ['ulcer'],
        disease: 'Edwardsiellosis',
        riskLevel: 'danger',
      ),
    ];
    return list..sort((a, b) => b.time.compareTo(a.time));
  }
}
