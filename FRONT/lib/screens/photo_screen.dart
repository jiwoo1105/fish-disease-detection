// 사진 1장 분석 화면 (촬영/갤러리 → det→cls 파이프라인 1회 실행 후 결과 표시).
// 기존 홈 화면의 단일 사진 분석 기능을 그대로 옮긴 것. (수조 기록과는 무관한 단발 도구)

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../labels.dart';
import '../models/results.dart';
import '../services/annotate.dart';
import '../services/pipeline_service.dart';
import '../widgets/action_card.dart';

class PhotoScreen extends StatefulWidget {
  const PhotoScreen({super.key});

  @override
  State<PhotoScreen> createState() => _PhotoScreenState();
}

class _PhotoScreenState extends State<PhotoScreen> {
  final _pipeline = PipelineService();
  final _picker = ImagePicker();

  bool _modelReady = false;
  bool _busy = false;
  String? _error;
  Uint8List? _annotated;
  TankResult? _result;

  @override
  void initState() {
    super.initState();
    _initModel();
  }

  Future<void> _initModel() async {
    try {
      await _pipeline.init();
      if (mounted) setState(() => _modelReady = true);
    } catch (e) {
      if (mounted) setState(() => _error = 'Model load failed: $e');
    }
  }

  @override
  void dispose() {
    _pipeline.dispose();
    super.dispose();
  }

  Future<void> _run(ImageSource source) async {
    if (!_modelReady || _busy) return;
    final file = await _picker.pickImage(source: source, maxWidth: 1920);
    if (file == null) return;

    setState(() {
      _busy = true;
      _error = null;
      _result = null;
      _annotated = null;
    });

    try {
      final bytes = await file.readAsBytes();
      final tank = await _pipeline.analyze(bytes);
      final annotated = annotateImage(bytes, tank.fish);
      if (!mounted) return;
      setState(() {
        _result = tank;
        _annotated = annotated;
      });
    } catch (e) {
      if (mounted) setState(() => _error = 'Analysis failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Photo Analysis'),
        backgroundColor: const Color(0xFF0277BD),
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          if (!_modelReady && _error == null) const LinearProgressIndicator(),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: (_modelReady && !_busy)
                        ? () => _run(ImageSource.camera)
                        : null,
                    icon: const Icon(Icons.camera_alt),
                    label: const Text('Camera'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: (_modelReady && !_busy)
                        ? () => _run(ImageSource.gallery)
                        : null,
                    icon: const Icon(Icons.photo_library),
                    label: const Text('Gallery'),
                  ),
                ),
              ],
            ),
          ),
          if (!_modelReady && _error == null)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Text('Loading model...'),
            ),
          if (_busy) const LinearProgressIndicator(minHeight: 2),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!, style: const TextStyle(color: Colors.red)),
        ),
      );
    }
    final result = _result;
    if (result == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Take or pick a flatfish photo.\nIf a disease is detected, response actions will be shown.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ),
      );
    }

    final alerts = result.alerts;
    return ListView(
      children: [
        _tankBanner(result),
        if (_annotated != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.memory(_annotated!, fit: BoxFit.contain),
            ),
          ),
        if (result.fishCount == 0)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Text('No flatfish found. Try shooting again from closer up.',
                textAlign: TextAlign.center),
          )
        else if (alerts.isEmpty)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Text('✅ All detected flatfish appear normal.',
                textAlign: TextAlign.center, style: TextStyle(fontSize: 16)),
          )
        else ...[
          const Padding(
            padding: EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: Text('Recommended actions',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
          for (final f in alerts) ActionCard(fish: f),
        ],
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _tankBanner(TankResult r) {
    final color = riskColor(r.tankRiskLevel);
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color, width: 1.5),
      ),
      child: Row(
        children: [
          Icon(
            r.tankRiskLevel == 'normal'
                ? Icons.check_circle
                : Icons.warning_amber_rounded,
            color: color,
            size: 36,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Tank status: ${urgencyLabel(r.tankRiskLevel)}',
                    style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: color)),
                const SizedBox(height: 2),
                Text(
                  '${r.diseasedCount} of ${r.fishCount} flatfish show abnormal signs'
                  '${r.hasContagious ? ' · contagious suspected' : ''}',
                  style: const TextStyle(color: Colors.black87),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
