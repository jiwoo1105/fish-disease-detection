// 홈: 양식장 수조 6개를 CCTV 처럼 한눈에 보는 대시보드.
// 각 수조는 현장에 설치된 카메라라고 가정한다. 수조를 누르면 그 수조 영상을 올려
// 진단하고(VideoScreen), 종료 시 받은 요약을 해당 수조 카드에 표시·저장한다.
// (수조는 6개 고정 — 추가/삭제 없음)

import 'package:flutter/material.dart';

import '../labels.dart';
import '../models/tank.dart';
import '../services/tank_store.dart';
import 'photo_screen.dart';
import 'video_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const int _tankCount = 6;

  final _store = TankStore();
  List<TankProfile> _tanks = List.generate(
    _tankCount,
    (i) => TankProfile(id: 'tank${i + 1}', name: '수조 ${i + 1}'),
  );
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  // 저장된 요약을 고정 수조 6개에 병합한다.
  Future<void> _load() async {
    final stored = await _store.load();
    final byId = {for (final t in stored) t.id: t};
    if (!mounted) return;
    setState(() {
      _tanks = List.generate(_tankCount, (i) {
        final id = 'tank${i + 1}';
        return TankProfile(
          id: id,
          name: '수조 ${i + 1}',
          lastSummary: byId[id]?.lastSummary,
        );
      });
      _loading = false;
    });
  }

  Future<void> _openTank(TankProfile tank) async {
    final summary = await Navigator.of(context).push<TankSummary>(
      MaterialPageRoute(builder: (_) => VideoScreen(tank: tank)),
    );
    if (summary == null || !mounted) return;
    final i = _tanks.indexWhere((t) => t.id == tank.id);
    if (i < 0) return;
    setState(() => _tanks[i] = _tanks[i].copyWith(lastSummary: summary));
    await _store.save(_tanks);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('넙치닥터 · 수조 모니터링'),
        backgroundColor: const Color(0xFF0277BD),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: '사진 1장 분석',
            icon: const Icon(Icons.photo_camera),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const PhotoScreen()),
            ),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : GridView.count(
              padding: const EdgeInsets.all(12),
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 0.92,
              children: _tanks.map(_tankCard).toList(),
            ),
    );
  }

  Widget _tankCard(TankProfile tank) {
    final s = tank.lastSummary;
    final color = s == null ? Colors.black45 : riskColor(s.riskLevel);
    return InkWell(
      onTap: () => _openTank(tank),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.black87,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color, width: 2),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // CCTV "화면" 영역
            Expanded(
              child: Stack(
                fit: StackFit.expand,
                children: [
                  const ColoredBox(color: Color(0xFF101418)),
                  Center(
                    child: Icon(
                      s == null
                          ? Icons.videocam_off
                          : (s.riskLevel == 'normal'
                              ? Icons.videocam
                              : Icons.warning_amber_rounded),
                      color: color,
                      size: 40,
                    ),
                  ),
                  Positioned(
                    top: 6,
                    left: 8,
                    child: Text(
                      tank.name,
                      style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 15),
                    ),
                  ),
                  const Positioned(
                    top: 8,
                    right: 8,
                    child: Icon(Icons.upload, color: Colors.white54, size: 18),
                  ),
                ],
              ),
            ),
            // 상태 바
            Container(
              width: double.infinity,
              color: color.withValues(alpha: 0.18),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Text(
                s == null
                    ? '영상 업로드'
                    : '${urgencyLabel(s.riskLevel)} · 최대 ${s.maxFish}마리'
                        '${s.diseasedCount > 0 ? ' · 이상 ${s.diseasedCount}' : ''}',
                style: TextStyle(
                    color: s == null ? Colors.white70 : color,
                    fontWeight: FontWeight.w600,
                    fontSize: 13),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
