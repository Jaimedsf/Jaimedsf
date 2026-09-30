"""Build the font atlases the generator draws text with.

Development tool: needs fonttools and uharfbuzz (requirements-dev.txt). The
generator itself only reads the JSON files this writes, so producing SVGs
never needs a font library.

    python tools/build_font_atlas.py

Each atlas is one style of Spectral:

    {"family", "style", "upm", "ascent", "descent",
     "glyphs": {char: [advance, d]}, "kern": {"AV": delta}}

`d` is the glyph outline in font units with the y axis already flipped for
SVG (baseline at y=0, ascenders negative), written in relative commands
(tools/pathdata.py), which takes a quarter less room. Kerning comes from HarfBuzz: the
difference between a pair's shaped advance and the sum of its two advances.

Spectral has no Greek lowercase, which the featured-projects plate uses for
its α, β, γ designations. Those come from a subset of Noto Serif Italic and
go into the italic atlas only.
"""

from __future__ import annotations

import json
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from pathdata import relative          # this file runs as a script, so its folder is on the path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "assets" / "fonts"
OUT = ROOT / "generator" / "fonts"

STYLES = {
    "light": "Spectral-Light.ttf",
    "regular": "Spectral-Regular.ttf",
    "medium": "Spectral-Medium.ttf",
    "italic": "Spectral-Italic.ttf",
}
GREEK_DONOR = "NotoSerif-Italic-greek.ttf"

COVERAGE = (
    list(range(0x20, 0x7F))            # Basic Latin
    + list(range(0xA0, 0x100))         # Latin-1 Supplement
    + list(range(0x100, 0x180))        # Latin Extended-A
    + list(range(0x400, 0x460))        # Cyrillic
    + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2022]
)
GREEK = list(range(0x3B1, 0x3CA))
KERN_SET = list(range(0x20, 0x7F)) + list(range(0xC0, 0x100))
MIN_KERN = 4  # font units; smaller adjustments are not worth their bytes


def _outlines(font: TTFont, codepoints: list[int]) -> dict[str, list]:
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    glyphs = {}
    for cp in codepoints:
        name = cmap.get(cp)
        if name is None:
            continue
        pen = SVGPathPen(glyph_set, ntos=lambda v: str(int(round(v))))
        glyph_set[name].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
        glyphs[chr(cp)] = [hmtx[name][0], relative(pen.getCommands())]
    return glyphs


def _kerning(path: Path, glyphs: dict[str, list]) -> dict[str, int]:
    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
    chars = [chr(cp) for cp in KERN_SET if chr(cp) in glyphs]
    kern = {}
    for a in chars:
        for b in chars:
            buf = hb.Buffer()
            buf.add_str(a + b)
            buf.guess_segment_properties()
            hb.shape(hb_font, buf, {"kern": True, "liga": False, "clig": False})
            positions = buf.glyph_positions
            if len(positions) != 2:
                continue
            delta = positions[0].x_advance + positions[1].x_advance - glyphs[a][0] - glyphs[b][0]
            if abs(delta) >= MIN_KERN:
                kern[a + b] = int(delta)
    return kern


def build(style: str) -> dict:
    path = SOURCES / STYLES[style]
    font = TTFont(path)
    glyphs = _outlines(font, COVERAGE)
    if style == "italic":
        glyphs.update(_outlines(TTFont(SOURCES / GREEK_DONOR), GREEK))
    hhea = font["hhea"]
    return {
        "family": "Spectral",
        "style": style,
        "upm": font["head"].unitsPerEm,
        "ascent": hhea.ascent,
        "descent": -hhea.descent,
        "glyphs": glyphs,
        "kern": _kerning(path, glyphs),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for style in STYLES:
        atlas = build(style)
        target = OUT / f"spectral-{style}.json"
        target.write_text(
            json.dumps(atlas, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
        print(f"{target.name}: {len(atlas['glyphs'])} glyphs, {len(atlas['kern'])} kern pairs, "
              f"{target.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
