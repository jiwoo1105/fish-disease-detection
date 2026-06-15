// 분석 결과를 이미지 위에 박스로 시각화 (Python draw_results 포팅).
// image 패키지 기본 폰트는 ASCII 만 지원하므로 박스 라벨은 영문/숫자만 사용한다.

import 'dart:typed_data';

import 'package:image/image.dart' as img;

import '../models/results.dart';

const _colors = <String, List<int>>{
  'normal': [0, 200, 0],
  'watch': [255, 210, 0],
  'danger': [255, 140, 0],
  'immediate': [255, 0, 0],
};

/// 원본 이미지에 물고기 박스 + 라벨을 그려 JPEG 바이트로 반환.
Uint8List annotateImage(Uint8List bytes, List<FishResult> fish) {
  final image = img.decodeImage(bytes);
  if (image == null) return bytes;
  return annotateDecoded(image, fish);
}

/// 이미 디코딩된 이미지에 박스를 그려 JPEG 바이트로 반환 (라이브용).
Uint8List annotateDecoded(img.Image image, List<FishResult> fish) {
  final thickness = (image.width / 300).clamp(2, 8).round();

  for (final f in fish) {
    final c = _colors[f.riskLevel] ?? const [255, 255, 255];
    final color = img.ColorRgb8(c[0], c[1], c[2]);
    final x1 = f.bbox.left.round();
    final y1 = f.bbox.top.round();
    final x2 = f.bbox.right.round();
    final y2 = f.bbox.bottom.round();

    img.drawRect(image,
        x1: x1, y1: y1, x2: x2, y2: y2, color: color, thickness: thickness);

    final pct = (f.symptomConfidence * 100).round();
    final label = '#${f.fishId} ${f.symptom} $pct%';
    final ty = (y1 - 28).clamp(0, image.height - 1);
    img.drawString(image, label, font: img.arial24, x: x1 + 2, y: ty, color: color);
  }

  return Uint8List.fromList(img.encodeJpg(image, quality: 85));
}
