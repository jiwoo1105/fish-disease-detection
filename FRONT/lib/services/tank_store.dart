// 등록된 수조 목록을 기기에 저장/로드한다 (shared_preferences, JSON).
// 단순한 단일 키 저장 — 수조 수가 많지 않으므로 통째로 읽고 쓴다.

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/tank.dart';

class TankStore {
  static const _key = 'tanks_v1';

  Future<List<TankProfile>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    final list = (json.decode(raw) as List).cast<Map>();
    return list
        .map((m) => TankProfile.fromJson(m.cast<String, dynamic>()))
        .toList();
  }

  Future<void> save(List<TankProfile> tanks) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _key,
      json.encode(tanks.map((t) => t.toJson()).toList()),
    );
  }
}
