// 영문 코드 → 한글 표시 라벨 / 색상 매핑 (UI 전용)

import 'package:flutter/material.dart';

const symptomKo = <String, String>{
  'normal': 'Normal',
  'hemorrhage': 'Hemorrhage',
  'white_spot': 'White spot',
  'tumor': 'Spot/Nodule',
  'color_change': 'Color change',
  'emaciation': 'Emaciation',
  'ulcer': 'Ulcer',
};

const actionKo = <String, String>{
  'LOWER_TEMPERATURE': 'Lower temperature',
  'RAISE_TEMPERATURE': 'Raise temperature',
  'ISOLATE_AND_TREAT': 'Isolate & treat',
  'TREAT': 'Treat (bath)',
  'IMPROVE_NUTRITION': 'Improve nutrition',
  'MONITOR': 'Monitor',
};

const actionIcon = <String, IconData>{
  'LOWER_TEMPERATURE': Icons.ac_unit,
  'RAISE_TEMPERATURE': Icons.local_fire_department,
  'ISOLATE_AND_TREAT': Icons.medical_services,
  'TREAT': Icons.medication,
  'IMPROVE_NUTRITION': Icons.restaurant,
  'MONITOR': Icons.visibility,
};

const urgencyKo = <String, String>{
  'immediate': 'Immediate',
  'danger': 'Danger',
  'watch': 'Watch',
  'normal': 'Normal',
};

Color riskColor(String level) {
  switch (level) {
    case 'immediate':
      return const Color(0xFFD32F2F);
    case 'danger':
      return const Color(0xFFF57C00);
    case 'watch':
      return const Color(0xFFFBC02D);
    default:
      return const Color(0xFF2E7D32);
  }
}

String symptomLabel(String s) => symptomKo[s] ?? s;
String actionLabel(String a) => actionKo[a] ?? a;
String urgencyLabel(String u) => urgencyKo[u] ?? u;

/// 위험도 등급 정렬용 순위 (높을수록 심각).
int urgencyRank(String u) => switch (u) {
      'immediate' => 3,
      'danger' => 2,
      'watch' => 1,
      _ => 0,
    };
