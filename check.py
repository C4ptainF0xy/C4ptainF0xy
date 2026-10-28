"""Fail if an asset would break or bloat on GitHub. Run: py check.py"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MAX_FILE, MAX_TOTAL = 1_500_000, 5_000_000
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
