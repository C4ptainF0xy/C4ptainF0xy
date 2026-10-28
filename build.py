"""Build assets/*.svg from src/*.svg by inlining every {{kind:file[@width]}} token as a data URI.

GitHub shows SVGs through <img>, which loads nothing external, so images and fonts must be inside the file.
  {{img:name.png@640}}  -> WebP, downscaled to 640 px wide
  {{svg:name.svg}}      -> the SVG file as is
  {{font:name.woff2}}   -> the font file as is
Run: py build.py
"""
import base64
import io
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
SRC, OUT = ROOT / "src", ROOT / "assets"
IMG = SRC / "img"
FONTS = SRC / "fonts"
TOKEN = re.compile(r"\{\{(img|svg|font):([^@}]+)(?:@(\d+))?\}\}")
MIME = {"svg": "image/svg+xml", "font": "font/woff2"}


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def data_uri(kind: str, name: str, width: int | None, img_dir: Path, font_dir: Path) -> str:
    if kind != "img":
        path = (font_dir if kind == "font" else img_dir) / name
        return f"data:{MIME[kind]};base64,{_b64(path.read_bytes())}"
    im = Image.open(img_dir / name)
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82, method=6)
    return f"data:image/webp;base64,{_b64(buf.getvalue())}"


def embed(template: str, img_dir: Path = IMG, font_dir: Path = FONTS) -> str:
    return TOKEN.sub(lambda m: data_uri(m[1], m[2], int(m[3]) if m[3] else None, img_dir, font_dir), template)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for f in sorted(SRC.glob("*.svg")):
        (OUT / f.name).write_text(embed(f.read_text("utf-8")), "utf-8")
        print(f"{f.name}: {(OUT / f.name).stat().st_size:,} bytes")
