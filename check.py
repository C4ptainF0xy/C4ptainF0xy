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


if __name__ == "__main__":
    assets = ROOT / "assets"
    found = violations(assets)
    print("\n".join(found) or f"OK {len(list(assets.glob('*.svg')))} files, total {sum(f.stat().st_size for f in assets.glob('*.svg')):,} bytes")
    sys.exit(1 if found else 0)
