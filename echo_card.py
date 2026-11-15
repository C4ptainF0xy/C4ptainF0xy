"""Build assets/echo.webp: the Echo card as one animated WebP at 1.5x, mascot straight from Spine's PNG export.

A sprite sheet stepped by CSS lands on a different sub-pixel every frame, so every outline shimmered. Here each
frame is composed once at a fixed position: the card (rendered from cards/echo.svg, which has no mascot), then the
Spine frame, then the card's bottom line again, which sits over the mascot in the SVG too.

  py echo_card.py D:/Projects/echo-spine/work/frames [--quality 85] [--gif gif/echo.gif]
"""
import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops
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


def compose(spine_frames: Path) -> list[Image.Image]:
    """The 80 frames of the loop, uncompressed."""
    meta = json.loads((ROOT / "src" / "img" / "echo-spine.json").read_text())
    S = 0.44
    TX, TY = 1012 - 397 * S, 20 - 97 * S
    x, y = (TX + S * meta["ref_x"]) * SCALE, (TY + S * meta["ref_y"]) * SCALE
    w, h = S * meta["ref_w"] * SCALE, S * meta["ref_h"] * SCALE
    spine = [Image.open(spine_frames / f"f_{FIRST + i:03d}.png").convert("RGBA") for i in range(FPS * LOOP)]
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
    return frames


def save_gif(frames: list[Image.Image], out: Path, dither_box: tuple[int, int, int, int] | None = None) -> None:
    """The loop as a GIF: one palette for the whole loop, fit to frame 0 and to every region that moves.

    No dithering: on this flat art over dark gradients it looked noisier and weighed twice as much
    (7.8 MB against 4.0 MB, and 42.5 dB against 43.0 dB, the WebP being 38.4). Except in `dither_box`:
    the button's gleam is a gradient that banded into five steps; it moves anyway, so no noise shows.
    Index 255 is transparent: the rounded corners, and (Pillow's optimize) every pixel that did not change since
    the previous frame, which took the Twitch banner from 9.8 MB to 6.2 MB with the exact same frames.
    """
    rgb = [f.convert("RGB") for f in frames]
    parts = [rgb[0]] + [im.crop(b) for prev, im in zip(rgb, rgb[1:]) if (b := ImageChops.difference(im, prev).getbbox())]
    sample = Image.new("RGB", (rgb[0].width, sum(p.height for p in parts)))
    y = 0
    for p in parts:
        sample.paste(p, (0, y)); y += p.height
    first = sample.quantize(colors=231, method=Image.Quantize.MEDIANCUT, kmeans=4)
    colours = first.getpalette()[:3 * 231]
    # median cut sacrifices small, distinct colours (the Yandere's yellow buttons came out pink): 24 entries for them
    s = np.asarray(sample).astype(int)
    err = np.abs(np.asarray(sample.quantize(palette=first, dither=Image.Dither.NONE).convert("RGB")).astype(int) - s).max(axis=2)
    if (far := s[err > 24].astype(np.uint8)).size:
        more = Image.fromarray(far[None]).quantize(colors=24, method=Image.Quantize.MEDIANCUT, kmeans=2)
        colours += more.getpalette()[:3 * min(24, len(np.unique(far, axis=0)))]
    colours += colours[:3] * (256 - len(colours) // 3)        # copies of colour 0: no pixel picks 255 by itself
    palette = Image.new("P", (1, 1))
    palette.putpalette(colours)
    clear = np.asarray(frames[0].getchannel("A")) < 128
    gif = []
    for im in rgb:
        q = np.asarray(im.quantize(palette=palette, dither=Image.Dither.NONE)).copy()
        if dither_box:
            x0, y0, x1, y1 = dither_box
            q[y0:y1, x0:x1] = np.asarray(im.crop(dither_box).quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG))
        q[clear] = 255
        f = Image.fromarray(q)
        f.putpalette(palette.getpalette())
        gif.append(f)
    gif[0].save(out, save_all=True, append_images=gif[1:], duration=1000 // FPS, loop=0, disposal=1,
                transparency=255, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spine_frames", type=Path)
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--gif", type=Path, help="also write the loop as a GIF here")
    a = ap.parse_args()
    frames = compose(a.spine_frames)
    out = ROOT / "assets" / "echo.webp"
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0,
                   quality=a.quality, method=6, minimize_size=True)
    print(f"{out.name}: {len(frames)} frames {frames[0].size}, {out.stat().st_size:,} bytes")
    if a.gif:
        save_gif(frames, a.gif, dither_box=tuple(round(v * SCALE) for v in (56, 240, 466, 336)))   # the button
        print(f"{a.gif}: {a.gif.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
