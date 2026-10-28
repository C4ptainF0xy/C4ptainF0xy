"""Fail if an asset would break or bloat on GitHub. Run: py check.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MAX_FILE, MAX_TOTAL = 1_500_000, 5_000_000
# On a phone the README column is 278 CSS px (360 viewport minus GitHub's margins and padding);
# contact buttons sit two per line, 49 % each. Text drawn smaller than this is unreadable there.
PHONE_COLUMN, MIN_TEXT_PX = 278, 10
SHARE = {"contact-": .49}
EXTERNAL = re.compile(r"""(?:\bhref|xlink:href)\s*=\s*["']https?:|url\(\s*["']?https?:|@import""", re.I)


def violations(assets: Path) -> list[str]:
    found, total = [], 0
    for f in sorted(assets.glob("*.svg")):
        text = f.read_text("utf-8")
        total += f.stat().st_size
        if f.stat().st_size > MAX_FILE:
            found.append(f"{f.name}: {f.stat().st_size:,} bytes > {MAX_FILE:,}")
        if re.search(r"<script", text, re.I):
            found.append(f"{f.name}: contains <script>")
        if m := EXTERNAL.search(text):
            found.append(f"{f.name}: external resource {m[0]!r}")
        if vb := re.search(r'viewBox="0 0 ([\d.]+)', text):
            share = next((s for prefix, s in SHARE.items() if f.name.startswith(prefix)), 1)
            scale = PHONE_COLUMN * share / float(vb[1])
            for size in sorted({float(s) for s in re.findall(r'<text[^>]*font-size="([\d.]+)"', text)}):
                if size * scale < MIN_TEXT_PX:
                    found.append(f"{f.name}: font-size {size:g} is {size * scale:.1f}px on a phone (< {MIN_TEXT_PX})")
    if total > MAX_TOTAL:
        found.append(f"assets total {total:,} bytes > {MAX_TOTAL:,}")
    return found


def readme_violations(readme: str, assets: Path) -> list[str]:
    found = []
    for src in re.findall(r'<img[^>]*\bsrc="([^"]+)"', readme):
        if not src.startswith("https://") and not (assets / Path(src.split("?")[0]).name).exists():
            found.append(f"README: missing asset {src}")
    found += [f"README: non-https link {h}" for h in re.findall(r'href="([^"]+)"', readme) + re.findall(r"\]\(([^)]+)\)", readme)
              if not h.startswith("https://")]
    found += ["README: style attribute is stripped by GitHub" for _ in re.findall(r"<[^>]*\bstyle=", readme)]
    found += [f"README: image without alt {tag[:60]}" for tag in re.findall(r"<img\b[^>]*>", readme) if " alt=" not in tag]
    return found


if __name__ == "__main__":
    assets = ROOT / "assets"
    found = violations(assets) + readme_violations((ROOT / "README.md").read_text("utf-8"), assets)
    print("\n".join(found) or f"OK {len(list(assets.glob('*.svg')))} files, total {sum(f.stat().st_size for f in assets.glob('*.svg')):,} bytes")
    sys.exit(1 if found else 0)
