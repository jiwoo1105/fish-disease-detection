// 영문 코드 → 한글 표시 라벨 / 색상 매핑 (UI 전용)

import 'package:flutter/material.dart';

const symptomKo = <String, String>{
  'normal': '정상',
  'hemorrhage': '출혈',
  'white_spot': '백점',
  'tumor': '반점/결절',
  'color_change': '체색변화',
  'emaciation': '여윔',
  'ulcer': '궤양',
};

const actionKo = <String, String>{
  'LOWER_TEMPERATURE': '수온 낮추기',
  'RAISE_TEMPERATURE': '수온 올리기',
  'ISOLATE_AND_TREAT': '격리 후 치료',
  'TREAT': '치료(약욕)',
  'IMPROVE_NUTRITION': '영양 개선',
  'MONITOR': '관찰',
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
  'immediate': '즉시 조치',
  'danger': '위험',
  'watch': '주의',
  'normal': '정상',
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
