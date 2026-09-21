#!/usr/bin/env python3
"""
텍스트 카드 스타일 캐러셀 이미지 생성기 (Pillow 기반, 심플한 텍스트 카드)

나중에 디자인 템플릿을 정하면 이 파일의 render_slide() 만 교체하면 됩니다.

사용법 (단독 실행 테스트):
  python3 generate_carousel.py --title "주제 제목" --out output/test

파이프라인에서는 check_selection.py 가 함수로 직접 호출합니다.
"""

import argparse
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350  # 인스타그램 4:5 비율

# GitHub Actions(ubuntu-latest)에서는 apt로 fonts-noto-cjk 설치 후 아래 경로 사용
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

BG_COLOR = (18, 18, 20)
ACCENT_COLOR = (255, 209, 70)
TEXT_COLOR = (245, 245, 245)
SUB_COLOR = (190, 190, 190)


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=0)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text: str, width_chars: int) -> list[str]:
    return textwrap.wrap(text, width=width_chars, break_long_words=True)


def render_slide(
    headline: str,
    body: str = "",
    slide_no: int = 1,
    total: int = 1,
    is_cover: bool = False,
) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    bold_size = 76 if is_cover else 58
    body_size = 40
    bold_font = _load_font(FONT_CANDIDATES, bold_size)
    body_font = _load_font(FONT_REGULAR_CANDIDATES, body_size)
    small_font = _load_font(FONT_REGULAR_CANDIDATES, 32)

    margin_x = 90
    y = 140 if is_cover else 110

    # 상단 라벨
    if is_cover:
        draw.text((margin_x, 80), "오늘의 이야기", font=small_font, fill=ACCENT_COLOR)
    else:
        draw.text((margin_x, 60), f"{slide_no} / {total}", font=small_font, fill=SUB_COLOR)

    # 헤드라인
    wrap_width = 13 if is_cover else 16
    for line in wrap_text(headline, wrap_width):
        draw.text((margin_x, y), line, font=bold_font, fill=TEXT_COLOR)
        y += bold_size + 18

    # 본문
    if body:
        y += 30
        for line in wrap_text(body, 24):
            draw.text((margin_x, y), line, font=body_font, fill=SUB_COLOR)
            y += body_size + 14

    # 하단 액센트 바
    draw.rectangle([(0, HEIGHT - 14), (WIDTH, HEIGHT)], fill=ACCENT_COLOR)

    return img


def build_carousel(title: str, bullets: list[str], out_dir: Path) -> list[Path]:
    """
    표지 1장 + 본문 슬라이드(불릿당 1장) + 마무리(CTA) 1장을 생성.
    반환값: 생성된 이미지 경로 리스트 (업로드 순서대로)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    total_slides = 1 + len(bullets) + 1

    cover = render_slide(title, is_cover=True)
    cover_path = out_dir / "slide_1_cover.png"
    cover.save(cover_path)
    paths.append(cover_path)

    for i, bullet in enumerate(bullets, start=2):
        img = render_slide(f"포인트 {i - 1}", body=bullet, slide_no=i, total=total_slides)
        p = out_dir / f"slide_{i}.png"
        img.save(p)
        paths.append(p)

    cta = render_slide("저장하고 다시보기 👍", body="더 많은 이야기는 팔로우!", slide_no=total_slides, total=total_slides)
    cta_path = out_dir / f"slide_{total_slides}_cta.png"
    cta.save(cta_path)
    paths.append(cta_path)

    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--out", default="output/test")
    args = parser.parse_args()

    sample_bullets = [
        "핵심 내용을 짧고 임팩트 있게 정리합니다.",
        "두 번째 포인트도 한두 문장으로 설명합니다.",
        "세 번째 포인트로 마무리 인사이트를 전달합니다.",
    ]
    result = build_carousel(args.title, sample_bullets, Path(args.out))
    print(f"{len(result)}장 생성 완료:")
    for p in result:
        print(f"  - {p}")
