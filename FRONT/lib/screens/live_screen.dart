// 실시간 라이브 카메라 모니터링.
// 배경은 CameraPreview 를 그대로 띄워 영상이 끊기지 않게 하고(플랫폼이 30fps 로 렌더),
// 탐지 결과(박스/라벨)는 그 위에 CustomPainter 오버레이로만 그린다.
// 추론(det→크롭→cls)은 프레임마다(처리 중에는 스킵) 백그라운드로 돌고, 박스는 추론 속도로 갱신된다.

import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;

import '../labels.dart';
import '../models/results.dart';
import '../models/tank.dart';
import '../services/camera_utils.dart';
import '../services/pipeline_service.dart';
import '../services/session_stats.dart';
import '../widgets/summary_dialog.dart';

class LiveScreen extends StatefulWidget {
  /// 모니터링 대상 수조. 종료 시 이 수조의 요약을 만들어 돌려준다.
  final TankProfile tank;

  const LiveScreen({super.key, required this.tank});

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> with WidgetsBindingObserver {
  final _pipeline = PipelineService();
  CameraController? _controller;
  int _sensorRotation = 90;

  bool _busy = false;
  bool _ready = false;
  bool _streaming = false;
  String? _error;
  CameraImage? _latest;

  // 추론이 처리한 이미지 크기 (박스 좌표계 기준). 오버레이 매핑에 사용.
  double _imgW = 0;
  double _imgH = 0;
  TankResult? _result;

  // 프레임 단위 결과를 시간 창(window) 안에서 다수결로 안정화한다.
  // (프레임마다 결과가 "왔다갔다" 깜빡이는 현상 방지)
  final List<({DateTime t, TankResult r})> _history = [];
  static const Duration _smoothWindow = Duration(milliseconds: 1200);

  // 초당 최대 추론 횟수 상한 (20 FPS = 50ms 간격). 발열/배터리 절약.
  // 추론이 이보다 빠르게 끝나면 남는 시간만큼 다음 프레임을 미룬다.
  static const Duration _minInterval = Duration(milliseconds: 50);
  DateTime? _lastInferenceStart;

  // 세션(이번 모니터링) 누적 통계 — 종료 시 요약에 사용.
  final _stats = SessionStats();
  bool _finishing = false; // 종료 요약 진행 중 중복 방지

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _setup();
  }

  Future<void> _setup() async {
    try {
      await _pipeline.init();

      final cameras = await availableCameras();
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      _sensorRotation = back.sensorOrientation;

      final controller = CameraController(
        back,
        // 프리뷰는 고해상도로 선명하게(1280x720). 추론 입력은 isolate 에서
        // 640 폭으로 축소(camera_utils.convertFrame)하므로 속도는 유지된다.
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.yuv420,
      );
      await controller.initialize();
      // 초점/노출 자동 (흐릿한 프레임은 탐지 신뢰도를 떨어뜨림)
      try {
        await controller.setFocusMode(FocusMode.auto);
        await controller.setExposureMode(ExposureMode.auto);
      } catch (_) {
        // 일부 기기 미지원 시 무시
      }
      _controller = controller;

      await controller.startImageStream(_onFrame);
      _streaming = true;

      if (mounted) setState(() => _ready = true);
    } catch (e) {
      if (mounted) setState(() => _error = '카메라/모델 초기화 실패: $e');
    }
  }

  void _onFrame(CameraImage image) {
    _latest = image;
    _process();
  }

  Future<void> _process() async {
    if (_busy || !mounted) return;
    final frame = _latest;
    if (frame == null) return;

    // 추론 빈도 상한(20 FPS): 직전 추론 시작으로부터 최소 간격이 안 지났으면
    // 남은 시간만큼 미뤘다가 다시 시도한다.
    final last = _lastInferenceStart;
    if (last != null) {
      final wait = _minInterval - DateTime.now().difference(last);
      if (wait > Duration.zero) {
        Future.delayed(wait, () {
          if (mounted) _process();
        });
        return;
      }
    }
    _lastInferenceStart = DateTime.now();

    _busy = true;
    _latest = null;

    try {
      // 무거운 YUV→RGB 변환 + 인코딩은 백그라운드 isolate 에서 (UI 블로킹 방지)
      final payload = extractYuvPayload(frame, rotationDegrees: _sensorRotation);
      final conv = await convertFrame(payload);
      if (!mounted) return;
      final image = img.Image.fromBytes(
        width: conv.width,
        height: conv.height,
        bytes: conv.rgb.buffer,
        numChannels: 3,
        order: img.ChannelOrder.rgb,
      );
      final tank = await _pipeline.analyzeDecoded(image, conv.jpeg);
      if (mounted) {
        final now = DateTime.now();
        _history.add((t: now, r: tank));
        _history.removeWhere((e) => now.difference(e.t) > _smoothWindow);
        setState(() {
          _result = _stabilized();
          _imgW = image.width.toDouble();
          _imgH = image.height.toDouble();
        });
        _stats.add(_result);
      }
    } catch (_) {
      // 프레임 단위 오류는 무시하고 다음 프레임 진행
    } finally {
      _busy = false;
      if (mounted && _latest != null) _process();
    }
  }

  // 최근 창(window) 결과를 다수결로 안정화해 표시할 대표 결과를 고른다.
  // 합성하지 않고 "다수결 판정과 일치하는 가장 최근 실제 프레임"을 그대로 쓴다
  // (박스 좌표가 실제 프레임 값이라 어긋나지 않음).
  TankResult? _stabilized() {
    if (_history.isEmpty) return _result;

    final n = _history.length;
    final withFish = _history.where((e) => e.r.fishCount > 0).length;
    final fishPresent = withFish * 2 >= n; // 과반이 넙치를 봤는가

    // 위험 레벨 다수결 (대표 후보군 = 넙치 유무가 판정과 일치하는 프레임)
    final levelVotes = <String, int>{};
    for (final e in _history) {
      if ((e.r.fishCount > 0) == fishPresent) {
        levelVotes.update(e.r.tankRiskLevel, (v) => v + 1, ifAbsent: () => 1);
      }
    }
    String? majorityLevel;
    var best = -1;
    levelVotes.forEach((k, v) {
      if (v > best) {
        best = v;
        majorityLevel = k;
      }
    });

    // 다수결과 일치하는 프레임 중 "가장 많이 잡은(fishCount 최대)" 프레임을 대표로
    // 사용한다. (여러 마리가 프레임마다 1↔N 으로 출렁여도 가장 충실한 탐지를 유지)
    TankResult? bestMatch;
    for (final e in _history) {
      final r = e.r;
      if ((r.fishCount > 0) == fishPresent &&
          (majorityLevel == null || r.tankRiskLevel == majorityLevel)) {
        // 동률이면 최신 프레임 우선
        if (bestMatch == null || r.fishCount >= bestMatch.fishCount) bestMatch = r;
      }
    }
    return bestMatch ?? _history.last.r;
  }

  // 영상 종료 → 요약 다이얼로그 표시 → 요약을 결과로 들고 홈으로 복귀.
  Future<void> _finish() async {
    if (_finishing || !mounted) return;
    _finishing = true;

    final c = _controller;
    if (c != null && _streaming) {
      await c.stopImageStream();
      _streaming = false;
    }

    final summary = _stats.build(DateTime.now());
    if (!mounted) return;
    await showTankSummaryDialog(context, widget.tank.name, summary);
    if (!mounted) return;
    Navigator.of(context).pop(summary);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final c = _controller;
    if (c == null || !c.value.isInitialized) return;
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      if (_streaming) {
        c.stopImageStream();
        _streaming = false;
      }
    } else if (state == AppLifecycleState.resumed) {
      if (!_streaming) {
        c.startImageStream(_onFrame);
        _streaming = true;
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    final c = _controller;
    if (c != null) {
      if (_streaming) c.stopImageStream();
      c.dispose();
    }
    _pipeline.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        _finish();
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(
          title: Text('실시간 · ${widget.tank.name}'),
          backgroundColor: Colors.black,
          foregroundColor: Colors.white,
        ),
        body: _buildBody(),
        bottomNavigationBar: _ready
            ? SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xFFD32F2F),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: _finishing ? null : _finish,
                      icon: const Icon(Icons.stop_circle),
                      label: const Text('모니터링 종료',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ),
              )
            : null,
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!,
              style: const TextStyle(color: Colors.redAccent),
              textAlign: TextAlign.center),
        ),
      );
    }
    final c = _controller;
    if (!_ready || c == null) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('카메라 · 모델 준비 중...',
                style: TextStyle(color: Colors.white70)),
          ],
        ),
      );
    }

    return Stack(
      children: [
        // 부드러운 라이브 프리뷰 (화면을 꽉 채우도록 cover)
        Positioned.fill(child: _cameraFill(c)),
        // 탐지 박스 오버레이 (추론 속도로만 갱신, 영상 프레임과 독립)
        Positioned.fill(
          child: CustomPaint(
            painter: _BoxPainter(_result?.fish ?? const [], _imgW, _imgH),
          ),
        ),
        // 클로즈업 사용 안내 (넙치가 안 잡힐 때만)
        if (_result == null || _result!.fishCount == 0)
          Positioned(
            top: 14,
            left: 16,
            right: 16,
            child: Center(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.6),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  '💡 진단할 넙치 한 마리에 가까이(화면 가득) 비추세요',
                  style: TextStyle(color: Colors.white, fontSize: 13),
                ),
              ),
            ),
          ),
        if (_result != null) _alertOverlay(_result!),
        if (_busy)
          const Positioned(
            top: 8,
            right: 8,
            child: SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: Colors.white70),
            ),
          ),
      ],
    );
  }

  // CameraPreview 를 화면 전체에 cover 로 채운다 (세로 모드 표준 방식).
  Widget _cameraFill(CameraController c) {
    final mq = MediaQuery.of(context).size;
    var scale = mq.aspectRatio * c.value.aspectRatio;
    if (scale < 1) scale = 1 / scale;
    return ClipRect(
      child: Transform.scale(
        scale: scale,
        child: Center(child: CameraPreview(c)),
      ),
    );
  }

  Widget _alertOverlay(TankResult r) {
    final color = riskColor(r.tankRiskLevel);
    final alerts = r.alerts;
    // 가장 위험한 물고기의 행동을 대표로 표시
    FishResult? top;
    for (final f in alerts) {
      if (top == null || f.riskScore > top.riskScore) top = f;
    }

    return Positioned(
      left: 0,
      right: 0,
      bottom: 0,
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 18),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.transparent, Colors.black.withValues(alpha: 0.85)],
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  r.tankRiskLevel == 'normal'
                      ? Icons.check_circle
                      : Icons.warning_amber_rounded,
                  color: color,
                ),
                const SizedBox(width: 8),
                Text(
                  '${urgencyLabel(r.tankRiskLevel)} · 넙치 ${r.fishCount}마리'
                  '${r.diseasedCount > 0 ? ' / 이상 ${r.diseasedCount}' : ''}',
                  style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.bold,
                      fontSize: 16),
                ),
              ],
            ),
            if (top != null) ...[
              const SizedBox(height: 6),
              Text(
                '${top.likelyDisease ?? symptomLabel(top.symptom)} 의심  →  '
                '${actionLabel(top.response!.action)}',
                style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 18),
              ),
              if (top.response!.temperature.isNotEmpty &&
                  top.response!.temperature != '유지')
                Text('🌡 ${top.response!.temperature}',
                    style: const TextStyle(color: Colors.white70)),
              if (top.response!.isolate)
                const Text('⚠ 감염 개체 즉시 격리',
                    style: TextStyle(color: Colors.orangeAccent)),
            ],
          ],
        ),
      ),
    );
  }
}

// 추론이 처리한 이미지(imgW×imgH) 좌표계의 박스를, 화면(canvas)에 cover 로
// 매핑해 그린다. 배경 CameraPreview 도 동일한 cover 방식으로 채우므로 정렬이 맞는다.
class _BoxPainter extends CustomPainter {
  final List<FishResult> fish;
  final double imgW;
  final double imgH;

  _BoxPainter(this.fish, this.imgW, this.imgH);

  @override
  void paint(Canvas canvas, Size size) {
    if (imgW == 0 || imgH == 0 || fish.isEmpty) return;

    final scale = math.max(size.width / imgW, size.height / imgH);
    final dx = (size.width - imgW * scale) / 2;
    final dy = (size.height - imgH * scale) / 2;

    for (final f in fish) {
      final b = f.bbox;
      final rect = Rect.fromLTRB(
        b.left * scale + dx,
        b.top * scale + dy,
        b.right * scale + dx,
        b.bottom * scale + dy,
      );
      final color = riskColor(f.riskLevel);
      canvas.drawRect(
        rect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = color,
      );

      // 탐지 전용/정상: 넙치 + 탐지 신뢰도, 질병: 질병명
      final label = f.isDiseased
          ? (f.likelyDisease ?? symptomLabel(f.symptom))
          : '넙치 ${(f.detConfidence * 100).round()}%';
      final tp = TextPainter(
        text: TextSpan(
          text: ' $label ',
          style: TextStyle(
            color: Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.bold,
            backgroundColor: color,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final ty = (rect.top - tp.height).clamp(0.0, size.height - tp.height);
      tp.paint(canvas, Offset(rect.left.clamp(0.0, size.width), ty));
    }
  }

  @override
  bool shouldRepaint(covariant _BoxPainter old) =>
      old.fish != fish || old.imgW != imgW || old.imgH != imgH;
}
