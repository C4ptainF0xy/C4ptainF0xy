"""Self-check for the card tooling. Run: py -I test_tools.py"""
import base64
import io
import tempfile
from pathlib import Path

from PIL import Image

import build
import check
import preview


def test_embed_replaces_img_token_with_resized_webp():
    with tempfile.TemporaryDirectory() as d:
        Image.new("RGBA", (32, 16), (255, 0, 0, 255)).save(Path(d) / "p.png")
        out = build.embed('<image href="{{img:p.png@8}}"/>', img_dir=Path(d))
        assert "{{" not in out
        uri = out.split('"')[1]
        assert uri.startswith("data:image/webp;base64,")
        im = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
        assert im.size == (8, 4)


def test_embed_inlines_svg_markup_without_xml_declaration():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "logo.svg").write_text('<?xml version="1.0"?>\n<svg viewBox="0 0 1 1"><g id="Up-arrow"/></svg>\n')
        out = build.embed("<g>{{inline:logo.svg}}</g>", img_dir=Path(d))
        assert out == '<g><svg viewBox="0 0 1 1"><g id="Up-arrow"/></svg></g>', out


def test_check_flags_script_and_external_href():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bad.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script/><image href="https://x/y.png"/></svg>')
        (Path(d) / "good.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/webp;base64,AA"/></svg>')
        found = check.violations(Path(d))
        assert len(found) == 2, found
        assert all("bad.svg" in v for v in found)


def test_check_flags_oversize_file():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "big.svg").write_text("<svg>" + "A" * check.MAX_FILE + "</svg>")
        assert any("big.svg" in v and "bytes" in v for v in check.violations(Path(d)))


def test_readme_check_flags_missing_asset_http_link_and_style():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "echo.svg").write_text("<svg/>")
        readme = ('<a href="https://ok.example"><img src="assets/echo.svg?v=1" alt="a"></a>\n'
                  '<img src="assets/gone.svg?v=1" alt="b">\n'
                  '<a href="http://plain.example">x</a>\n'
                  '<img src="assets/echo.svg" style="width:1px" alt="c">\n'
                  '<img src="assets/echo.svg">\n')
        found = check.readme_violations(readme, Path(d))
        assert any("gone.svg" in v for v in found), found
        assert any("http://plain.example" in v for v in found), found
        assert any("style" in v for v in found), found
        assert any("alt" in v for v in found), found
        assert len(found) == 4, found


def test_differs_measures_changed_pixel_ratio():
    a = Image.new("RGB", (10, 10), "black")
    b = a.copy()
    assert preview.differs(a, b) == 0
    b.paste("white", (0, 0, 10, 5))
    assert preview.differs(a, b) == 0.5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
