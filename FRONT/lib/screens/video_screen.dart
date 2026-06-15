// 수조에 올린 영상을 진단하는 화면 (CCTV 영상 확인 컨셉).
//
// 박스 정합 + 끊김 최소화를 위해 "추출 프레임을 직접 그리는" 방식으로 동작한다:
//   영상에서 위치별 프레임을 추출(video_thumbnail) → 그 프레임을 화면에 표시 +
//   같은 프레임으로 det→cls 추론 → 박스 오버레이 → 다음 위치로 진행.
// 표시 프레임 == 분석 프레임 이라 탐지된 모든 넙치가 항상 박스로 보인다.
// (영상 seek 를 따로 하지 않아 디코딩 중복이 없고, 다음 스텝을 프레임 렌더 이후로
//  미뤄 UI 가 끊기지 않는다. video_player 는 영상 길이 측정에만 잠깐 쓴다.)

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';
import 'package:video_player/video_player.dart';
import 'package:video_thumbnail/video_thumbnail.dart';

import '../labels.dart';
import '../models/results.dart';
import '../models/tank.dart';
import '../services/pipeline_service.dart';
import '../services/session_stats.dart';
import '../widgets/summary_dialog.dart';

class VideoScreen extends StatefulWidget {
  final TankProfile tank;
  const VideoScreen({super.key, required this.tank});

  @override
  State<VideoScreen> createState() => _VideoScreenState();
}

class _VideoScreenState extends State<VideoScreen> {
  final _pipeline = PipelineService();
  final _picker = ImagePicker();
  final _stats = SessionStats();

  // 프레임 진행 간격(ms). 작을수록 촘촘하지만 처리 프레임 수가 늘어 오래 걸린다.
  static const int _stepMs = 200;

  String? _videoPath;
  int _durationMs = 0;
  int _posMs = 0;

  bool _modelReady = false;
  bool _picked = false;
  bool _running = false; // 진행(분석) 중인가
  bool _busy = false; // 한 프레임 처리 중
  bool _finishing = false;
  String? _error;

  // 현재 표시/분석 중인 프레임과 박스
  Uint8List? _frameBytes;
  List<FishResult> _boxes = const [];
  double _imgW = 0;
  double _imgH = 0;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      await _pipeline.init();
      if (!mounted) return;
      setState(() => _modelReady = true);
      _pick();
    } catch (e) {
      if (mounted) setState(() => _error = '모델 로드 실패: $e');
    }
  }

  @override
  void dispose() {
    _running = false;
    _pipeline.dispose();
    super.dispose();
  }

  // 영상 길이(ms)만 잠깐 측정하고 컨트롤러는 바로 정리.
  Future<int> _readDurationMs(String path) async {
    final c = VideoPlayerController.file(File(path));
    try {
      await c.initialize();
      return c.value.duration.inMilliseconds;
    } finally {
      await c.dispose();
    }
  }

  Future<void> _pick() async {
    if (!_modelReady) return;
    final file = await _picker.pickVideo(source: ImageSource.gallery);
    if (file == null || !mounted) return;
    try {
      final dur = await _readDurationMs(file.path);
      if (!mounted) return;
      setState(() {
        _videoPath = file.path;
        _durationMs = dur;
        _posMs = 0;
        _picked = true;
        _running = true;
        _frameBytes = null;
        _boxes = const [];
      });
      _step();
    } catch (e) {
      if (mounted) setState(() => _error = '영상을 열 수 없습니다: $e');
    }
  }

  // 현재 위치 프레임 추출 → 추론 → 표시/박스 갱신 → (렌더 후) 다음 위치로.
  Future<void> _step() async {
    if (!_running || _busy || _finishing || !mounted) return;
    final path = _videoPath;
    if (path == null) return;
    if (_durationMs > 0 && _posMs >= _durationMs) {
      await _finish();
      return;
    }

    _busy = true;
    try {
      final bytes = await VideoThumbnail.thumbnailData(
        video: path,
        imageFormat: ImageFormat.JPEG,
        maxWidth: 720,
        timeMs: _posMs,
        quality: 80,
      );
      if (bytes != null && bytes.isNotEmpty && mounted) {
        final decoded = img.decodeImage(bytes);
        if (decoded != null) {
          final tank = await _pipeline.analyzeDecoded(decoded, bytes);
          _stats.add(tank);
          if (mounted) {
            setState(() {
              _frameBytes = bytes;
              _boxes = tank.fish;
              _imgW = decoded.width.toDouble();
              _imgH = decoded.height.toDouble();
            });
          }
        }
      }
    } catch (_) {
      // 프레임 단위 오류는 무시
    } finally {
      _busy = false;
      _posMs += _stepMs;
      // 다음 스텝은 이번 프레임이 화면에 그려진 뒤 실행 → UI 가 끊기지 않음.
      if (_running && !_finishing && mounted) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_running && !_finishing && mounted) _step();
        });
      }
    }
  }

  void _togglePlay() {
    setState(() => _running = !_running);
    if (_running) _step();
  }

  Future<void> _finish() async {
    if (_finishing || !mounted) return;
    _finishing = true;
    _running = false;

    final summary = _stats.build(DateTime.now());
    if (!mounted) return;
    await showTankSummaryDialog(context, widget.tank.name, summary);
    if (!mounted) return;
    Navigator.of(context).pop(summary);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        if (_picked) {
          _finish();
        } else {
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(
          title: Text('영상 분석 · ${widget.tank.name}'),
          backgroundColor: Colors.black,
          foregroundColor: Colors.white,
        ),
        body: _buildBody(),
        bottomNavigationBar: _picked ? SafeArea(child: _controls()) : null,
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!,
                  style: const TextStyle(color: Colors.redAccent),
                  textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () {
                  setState(() => _error = null);
                  _pick();
                },
                icon: const Icon(Icons.video_library),
                label: const Text('영상 다시 선택'),
              ),
            ],
          ),
        ),
      );
    }

    if (!_modelReady) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 12),
            Text('모델 준비 중...', style: TextStyle(color: Colors.white70)),
          ],
        ),
      );
    }

    if (!_picked) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.video_library, size: 56, color: Colors.white24),
            const SizedBox(height: 12),
            const Text('분석할 영상을 선택하세요.',
                style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _pick,
              icon: const Icon(Icons.video_library),
              label: const Text('영상 선택'),
            ),
          ],
        ),
      );
    }

    final frame = _frameBytes;
    if (frame == null || _imgW == 0 || _imgH == 0) {
      return const Center(child: CircularProgressIndicator());
    }

    return Center(
      child: AspectRatio(
        aspectRatio: _imgW / _imgH,
        child: Stack(
          children: [
            Positioned.fill(
              child: Image.memory(frame,
                  gaplessPlayback: true, fit: BoxFit.fill),
            ),
            Positioned.fill(
              child: CustomPaint(
                painter: _VideoBoxPainter(_boxes, _imgW, _imgH),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _controls() {
    final progress =
        _durationMs <= 0 ? 0.0 : (_posMs / _durationMs).clamp(0.0, 1.0);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LinearProgressIndicator(value: progress),
          const SizedBox(height: 8),
          Row(
            children: [
              IconButton(
                iconSize: 34,
                color: Colors.white,
                icon:
                    Icon(_running ? Icons.pause_circle : Icons.play_circle),
                onPressed: _finishing ? null : _togglePlay,
              ),
              const SizedBox(width: 4),
              Text('${(progress * 100).round()}%',
                  style: const TextStyle(color: Colors.white70)),
              const Spacer(),
              FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFD32F2F),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 12),
                ),
                onPressed: _finishing ? null : _finish,
                icon: const Icon(Icons.stop_circle),
                label: const Text('종료 · 요약',
                    style:
                        TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _VideoBoxPainter extends CustomPainter {
  final List<FishResult> fish;
  final double imgW;
  final double imgH;

  _VideoBoxPainter(this.fish, this.imgW, this.imgH);

  @override
  void paint(Canvas canvas, Size size) {
    if (imgW == 0 || imgH == 0 || fish.isEmpty) return;
    final scale = size.width / imgW;

    for (final f in fish) {
      final b = f.bbox;
      final rect = Rect.fromLTRB(
        b.left * scale,
        b.top * scale,
        b.right * scale,
        b.bottom * scale,
      );
      final color = riskColor(f.riskLevel);
      canvas.drawRect(
        rect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..color = color,
      );

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
  bool shouldRepaint(covariant _VideoBoxPainter old) =>
      old.fish != fish || old.imgW != imgW || old.imgH != imgH;
}
