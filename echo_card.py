"""Build assets/echo.webp: the Echo card as one animated WebP at 1.5x, mascot straight from Spine's PNG export.

A sprite sheet stepped by CSS lands on a different sub-pixel every frame, so every outline shimmered. Here each
frame is composed once at a fixed position: the card (rendered from cards/echo.svg, which has no mascot), then the
Spine frame, then the card's bottom line again, which sits over the mascot in the SVG too.

  py echo_card.py D:/Projects/echo-spine/work/frames [--quality 85]
"""
import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

import build

ROOT = Path(__file__).parent
FPS, LOOP, SCALE = 20, 4, 1.5                   # 1.5x matches the drawing's own resolution
FIRST = 80                                         # second loop of idle_x2: the first second of an export fades in


def card_frames(out: Path) -> list[Path]:
    """The card without its mascot, at 1.5x, transparent outside the rounded corners."""
    svg = build.embed((ROOT / "cards" / "echo.svg").read_text("utf-8"))
    html = f"<body style='margin:0;background:transparent'><div style='width:1280px'>{svg}</div>" \
           "<style>svg{width:100%;height:auto;display:block}</style></body>"
    paths = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 1280, "height": 400}, device_scale_factor=SCALE)
        page.set_content(html)
        page.wait_for_timeout(300)
        box = page.locator("div").first
        for i in range(FPS * LOOP):
            page.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {i * 1000 / FPS}; }})")
            path = out / f"card{i:03d}.png"
            box.screenshot(path=str(path), omit_background=True)
            paths.append(path)
        b.close()
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spine_frames", type=Path)
    ap.add_argument("--quality", type=int, default=85)
    a = ap.parse_args()
    meta = json.loads((ROOT / "src" / "img" / "echo-spine.json").read_text())
    S = 0.44
    TX, TY = 1012 - 397 * S, 20 - 97 * S
    x, y = (TX + S * meta["ref_x"]) * SCALE, (TY + S * meta["ref_y"]) * SCALE
    w, h = S * meta["ref_w"] * SCALE, S * meta["ref_h"] * SCALE
    spine = [Image.open(a.spine_frames / f"f_{FIRST + i:03d}.png").convert("RGBA") for i in range(FPS * LOOP)]
    union = tuple(meta["crop"])
    line_top = round(394 * SCALE)
    frames = []
    with tempfile.TemporaryDirectory() as d:
        for card_path, sp in zip(card_frames(Path(d)), spine):
            card = Image.open(card_path).convert("RGBA")
            line = card.crop((0, line_top, card.width, card.height))
            mascot = sp.crop(union).resize((round(w), round(h)), Image.LANCZOS)
            card.alpha_composite(mascot, (round(x), round(y)))
            card.paste(line, (0, line_top))              # the bottom line stays in front, as in the SVG
            frames.append(card)
    out = ROOT / "assets" / "echo.webp"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0,
                   quality=a.quality, method=6, minimize_size=True)
    print(f"{out.name}: {len(frames)} frames {frames[0].size}, {out.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
