"""
정적 이미지 → 테스트 영상 변환
- 카메라 패닝 효과
- 수면 물결/일렁임 효과
- 줌인 효과

사용법: venv/bin/python scripts/make_test_video.py
"""

import cv2
import numpy as np
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = PROJECT_ROOT / "data/fish_det_roboflow/train/images"
OUT_DIR = PROJECT_ROOT / "test_videos"
OUT_DIR.mkdir(exist_ok=True)

FPS = 30
DURATION = 10  # 초
OUT_W, OUT_H = 1280, 720
TOTAL_FRAMES = FPS * DURATION


def water_ripple(frame, t):
    """수면 물결 효과 (sin wave distortion)"""
    rows, cols = frame.shape[:2]
    map_x = np.zeros((rows, cols), dtype=np.float32)
    map_y = np.zeros((rows, cols), dtype=np.float32)

    for y in range(rows):
        for x in range(cols):
            # 수평 물결
            map_x[y, x] = x + 3.0 * np.sin(2 * np.pi * y / 120 + t * 2)
            # 수직 물결
            map_y[y, x] = y + 2.0 * np.sin(2 * np.pi * x / 150 + t * 1.5)

    return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def water_ripple_fast(frame, t):
    """수면 물결 효과 (벡터화 - 빠른 버전)"""
    rows, cols = frame.shape[:2]
    y_coords, x_coords = np.mgrid[0:rows, 0:cols].astype(np.float32)

    map_x = x_coords + 3.0 * np.sin(2 * np.pi * y_coords / 120 + t * 2)
    map_y = y_coords + 2.0 * np.sin(2 * np.pi * x_coords / 150 + t * 1.5)

    return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def add_caustics(frame, t):
    """수면 빛 반사 효과 (caustics)"""
    rows, cols = frame.shape[:2]
    y_coords, x_coords = np.mgrid[0:rows, 0:cols].astype(np.float32)

    pattern = (
        np.sin(x_coords / 40 + t * 1.2) *
        np.cos(y_coords / 35 + t * 0.8) *
        np.sin((x_coords + y_coords) / 60 + t * 0.5)
    )
    pattern = ((pattern + 1) / 2 * 25).astype(np.uint8)

    caustic_layer = np.stack([pattern, pattern, pattern], axis=-1)
    result = cv2.add(frame, caustic_layer)
    return result


def add_particles(frame, particles, t):
    """물속 떠다니는 입자 효과"""
    overlay = frame.copy()
    for px, py, size, speed, brightness in particles:
        cx = int((px + t * speed * 5) % frame.shape[1])
        cy = int((py + np.sin(t * 0.5 + px) * 3) % frame.shape[0])
        cv2.circle(overlay, (cx, cy), size, (brightness, brightness, brightness), -1)
    return cv2.addWeighted(frame, 0.95, overlay, 0.05, 0)


def generate_video(img_path, out_path, effect="pan_ripple"):
    """이미지에서 영상 생성"""
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"  이미지 읽기 실패: {img_path}")
        return False

    h, w = img.shape[:2]
    print(f"  원본 크기: {w}x{h}")

    # 이미지가 출력보다 작으면 업스케일
    scale = max(OUT_W * 1.3 / w, OUT_H * 1.3 / h)
    if scale > 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]

    # 패닝 범위 계산
    pan_range_x = max(0, w - OUT_W)
    pan_range_y = max(0, h - OUT_H)

    # 랜덤 입자 생성
    np.random.seed(42)
    particles = [
        (np.random.randint(0, OUT_W), np.random.randint(0, OUT_H),
         np.random.randint(1, 3), np.random.uniform(2, 8),
         np.random.randint(180, 240))
        for _ in range(30)
    ]

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(out_path), fourcc, FPS, (OUT_W, OUT_H))

    for i in range(TOTAL_FRAMES):
        t = i / FPS  # 현재 시간 (초)
        progress = i / TOTAL_FRAMES  # 0~1 진행도

        # 패닝: 좌→우 + 약간 상→하 (ease-in-out)
        ease = (1 - np.cos(progress * np.pi)) / 2
        x_off = int(ease * pan_range_x)
        y_off = int(ease * pan_range_y * 0.3)

        # 줌: 서서히 줌인 (1.0 → 1.08)
        zoom = 1.0 + progress * 0.08
        crop_w = int(OUT_W / zoom)
        crop_h = int(OUT_H / zoom)

        # 크롭 영역 계산
        cx = min(x_off + (OUT_W - crop_w) // 2, w - crop_w)
        cy = min(y_off + (OUT_H - crop_h) // 2, h - crop_h)
        cx = max(0, cx)
        cy = max(0, cy)

        crop = img[cy:cy + crop_h, cx:cx + crop_w]
        frame = cv2.resize(crop, (OUT_W, OUT_H), interpolation=cv2.INTER_LINEAR)

        # 물결 효과
        frame = water_ripple_fast(frame, t)

        # 수면 빛 반사
        frame = add_caustics(frame, t)

        # 떠다니는 입자
        frame = add_particles(frame, particles, t)

        # 약간 녹색 틴트 (수중 느낌)
        green_tint = np.zeros_like(frame)
        green_tint[:, :, 1] = 8  # Green channel
        frame = cv2.add(frame, green_tint)

        writer.write(frame)

        if (i + 1) % (FPS * 2) == 0:
            print(f"    {t:.0f}s / {DURATION}s 완료")

    writer.release()
    print(f"  저장: {out_path}")
    return True


def main():
    print("=" * 50)
    print("  넙치 테스트 영상 생성")
    print(f"  설정: {OUT_W}x{OUT_H}, {FPS}fps, {DURATION}초")
    print("=" * 50)

    # 이미지 5개 선택
    images = sorted(IMG_DIR.glob("*.jpg"))[:5]
    if not images:
        print("이미지 없음!")
        return

    for idx, img_path in enumerate(images):
        print(f"\n[{idx + 1}/{len(images)}] {img_path.name}")
        out_name = f"tank_video_{idx + 1:02d}.mp4"
        out_path = OUT_DIR / out_name
        generate_video(img_path, out_path)

    print(f"\n완료! {OUT_DIR} 에 영상 {len(images)}개 생성됨")


if __name__ == "__main__":
    main()
