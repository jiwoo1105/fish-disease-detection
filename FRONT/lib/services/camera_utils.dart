// 카메라 프레임(YUV420_888) → RGB 변환 + 회전 + JPEG 인코딩.
// 무거운 픽셀 처리는 메인 스레드(UI)를 막지 않도록 Isolate.run 으로 백그라운드에서 돌린다.
// 안드로이드 카메라는 센서 방향(보통 90°)으로 들어오므로 업라이트로 회전한다.

import 'dart:isolate';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:image/image.dart' as img;

/// CameraImage 의 평면(plane) 데이터를 isolate 로 보낼 수 있는 평범한 바이트로 추출.
/// (메인 스레드에서 호출 — 단순 복사라 가볍다.)
typedef YuvPayload = ({
  int width,
  int height,
  Uint8List y,
  Uint8List u,
  Uint8List v,
  int yRowStride,
  int uvRowStride,
  int uvPixelStride,
  int rotation,
});

/// 변환 결과: det 입력용 JPEG, 크롭용 RGB 바이트, 회전 후 크기.
typedef ConvertedFrame = ({Uint8List jpeg, Uint8List rgb, int width, int height});

YuvPayload extractYuvPayload(CameraImage image, {int rotationDegrees = 0}) {
  final y = image.planes[0];
  final u = image.planes[1];
  final v = image.planes[2];
  return (
    width: image.width,
    height: image.height,
    y: y.bytes,
    u: u.bytes,
    v: v.bytes,
    yRowStride: y.bytesPerRow,
    uvRowStride: u.bytesPerRow,
    uvPixelStride: u.bytesPerPixel ?? 1,
    rotation: rotationDegrees,
  );
}

/// 프레임을 백그라운드 isolate 에서 변환한다 (UI 블로킹 방지).
Future<ConvertedFrame> convertFrame(YuvPayload p, {int jpegQuality = 95}) {
  return Isolate.run(() => _convert(p, jpegQuality));
}

ConvertedFrame _convert(YuvPayload p, int jpegQuality) {
  final out = img.Image(width: p.width, height: p.height);

  for (int row = 0; row < p.height; row++) {
    final yRow = row * p.yRowStride;
    final uvRow = (row >> 1) * p.uvRowStride;
    for (int col = 0; col < p.width; col++) {
      final yIndex = yRow + col;
      final uvIndex = uvRow + (col >> 1) * p.uvPixelStride;

      final yv = p.y[yIndex];
      final uv = p.u[uvIndex] - 128;
      final vv = p.v[uvIndex] - 128;

      int r = (yv + 1.402 * vv).round();
      int g = (yv - 0.344136 * uv - 0.714136 * vv).round();
      int b = (yv + 1.772 * uv).round();

      out.setPixelRgb(
        col,
        row,
        r < 0 ? 0 : (r > 255 ? 255 : r),
        g < 0 ? 0 : (g > 255 ? 255 : g),
        b < 0 ? 0 : (b > 255 ? 255 : b),
      );
    }
  }

  img.Image result = out;
  if (p.rotation == 90) {
    result = img.copyRotate(out, angle: 90);
  } else if (p.rotation == 180) {
    result = img.copyRotate(out, angle: 180);
  } else if (p.rotation == 270) {
    result = img.copyRotate(out, angle: 270);
  }

  final jpeg = Uint8List.fromList(img.encodeJpg(result, quality: jpegQuality));
  final rgb = result.getBytes(order: img.ChannelOrder.rgb);
  return (jpeg: jpeg, rgb: rgb, width: result.width, height: result.height);
}
