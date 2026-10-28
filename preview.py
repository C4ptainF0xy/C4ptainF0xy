"""Render an animated SVG at chosen instants, at the width it will be seen.

  py preview.py assets/echo.svg --t 0,1,2 --width 896 --out .superpowers/prev/echo [--bg #ffffff] [--loop-check 4]

--loop-check P compares the frames just before the loop restarts (P - 0.02 s) and at 0 s;
more than 1 % of pixels changed means the animation visibly jumps when it loops.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright


def differs(a: Image.Image, b: Image.Image) -> float:
    """Share of pixels whose colour changed by more than 24 on any channel."""
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB")).convert("L").point(lambda v: 255 if v > 24 else 0)
    return diff.histogram()[255] / (a.width * a.height)


def render(svg: Path, times: list[float], width: int, out: str, bg: str) -> list[Path]:
    html = f"<body style='margin:0;background:{bg}'><div style='width:{width}px'>{svg.read_text('utf-8')}</div>" \
           "<style>svg{width:100%;height:auto;display:block}</style></body>"
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": width, "height": 100})
        page.set_content(html)
        page.wait_for_timeout(300)
        box = page.locator("div").first
        for t in times:
            page.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {t * 1000}; }})")
            page.wait_for_timeout(50)
            path = Path(f"{out}-w{width}-t{t:g}.png")
            path.parent.mkdir(parents=True, exist_ok=True)
            box.screenshot(path=str(path))
            paths.append(path)
        browser.close()
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", type=Path)
    ap.add_argument("--t", default="0")
    ap.add_argument("--width", type=int, default=896)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bg", default="#0d1117")
    ap.add_argument("--loop-check", type=float)
    ap.add_argument("--gif", type=float, metavar="PERIOD", help="also write <out>.gif: one loop at 20 fps (5/100 s per frame, exact in GIF)")
    a = ap.parse_args()
    if a.gif:
        with tempfile.TemporaryDirectory() as d:
            frames = render(a.svg, [i / 20 for i in range(round(a.gif * 20))], a.width, f"{d}/f", a.bg)
            for i, f in enumerate(frames):
                f.rename(f"{d}/{i:04d}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "20", "-i", f"{d}/%04d.png", "-vf",
                            "split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a",
                            "-loop", "0", f"{a.out}.gif"], check=True)
        print(f"{a.out}.gif")
        sys.exit(0)
    times = [float(x) for x in a.t.split(",")]
    for path in render(a.svg, times, a.width, a.out, a.bg):
        print(path)
    if a.loop_check:
        end, start = render(a.svg, [a.loop_check - 0.02, 0], a.width, a.out + "-loop", a.bg)
        ratio = differs(Image.open(end), Image.open(start))
        print(f"loop seam: {ratio:.2%} pixels changed")
        sys.exit(1 if ratio > 0.01 else 0)
