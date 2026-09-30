"""Text as outlines, measured exactly.

The plates never emit <text>. Each string becomes a run of <use> elements
pointing at glyph outlines defined once per SVG, so the result looks the same
in every browser and rasteriser, and the generator knows how wide it is.

Outlines, advances and kerning come from generator/fonts/*.json (built by
tools/build_font_atlas.py). A string with a character outside that coverage
falls back, whole, to a <text> element in a system serif, and its width is
estimated.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from generator.svg import esc, num

FONTS = Path(__file__).resolve().parent / "fonts"
STYLES = ("light", "regular", "medium", "italic")
FALLBACK_FAMILY = "Georgia, 'Times New Roman', serif"
ELLIPSIS = "…"

_PREFIX = {"light": "l", "regular": "r", "medium": "m", "italic": "i"}
_FALLBACK_WEIGHT = {"light": ' font-weight="300"', "medium": ' font-weight="500"'}


@lru_cache(maxsize=None)
def font(style: str) -> dict:
    """The atlas for one style, with the average advance used to estimate uncovered text."""
    if style not in STYLES:
        raise ValueError(f"unknown text style '{style}'")
    atlas = json.loads((FONTS / f"spectral-{style}.json").read_text(encoding="utf-8"))
    lower = [atlas["glyphs"][c][0] for c in "abcdefghijklmnopqrstuvwxyz"]
    atlas["avg"] = sum(lower) / len(lower)
    return atlas


def covers(text: str, style: str = "regular") -> bool:
    glyphs = font(style)["glyphs"]
    return all(ch in glyphs for ch in text)


def _layout(text: str, atlas: dict) -> tuple[list[tuple[str, int]], int]:
    """Pen position of every character, and the total advance, in font units."""
    glyphs, kern = atlas["glyphs"], atlas["kern"]
    pens, pen, prev = [], 0, None
    for ch in text:
        if prev is not None:
            pen += kern.get(prev + ch, 0)
        pens.append((ch, pen))
        pen += glyphs[ch][0]
        prev = ch
    return pens, pen


def measure(text: str, size: float, style: str = "regular") -> float:
    """Width of text in pixels at the given size."""
    atlas = font(style)
    if covers(text, style):
        units = _layout(text, atlas)[1]
    else:
        glyphs = atlas["glyphs"]
        units = sum(glyphs[ch][0] if ch in glyphs else atlas["avg"] for ch in text)
    return units * size / atlas["upm"]


def _ellipsize(line: str, size: float, style: str, max_width: float) -> str:
    line = line.rstrip()
    while line and measure(line + ELLIPSIS, size, style) > max_width:
        line = line[:-1].rstrip()
    return line + ELLIPSIS


def wrap(text: str, size: float, style: str, max_width: float, max_lines: int = 2) -> list[str]:
    """Break text into lines no wider than max_width; the last line ends in an ellipsis if text was cut."""
    words = text.split()
    if not words:
        return []
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        if not current or measure(candidate, size, style) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    cut = len(lines) > max_lines
    lines = lines[:max_lines]
    for i, line in enumerate(lines):
        if measure(line, size, style) > max_width or (cut and i == len(lines) - 1):
            lines[i] = _ellipsize(line, size, style, max_width)
    return lines


def _fallback(x: float, y: float, text: str, size: float, fill: str, style: str, anchor: str,
              attrs: str, transform: str = "") -> str:
    anchor_attr = "" if anchor == "start" else f' text-anchor="{anchor}"'
    italic = ' font-style="italic"' if style == "italic" else ""
    position = f' transform="{transform}"' if transform else f' x="{num(x)}" y="{num(y)}"'
    return (f'<text{position} font-family="{FALLBACK_FAMILY}" font-size="{num(size)}"'
            f'{_FALLBACK_WEIGHT.get(style, "")}{italic} fill="{fill}"{anchor_attr}{attrs}>{esc(text)}</text>')


class Typesetter:
    """Sets text for one SVG and remembers which glyph outlines it used."""

    def __init__(self) -> None:
        self._defs: dict[str, str] = {}

    def _glyph(self, style: str, ch: str, outline: str) -> str:
        gid = f"{_PREFIX[style]}{ord(ch):x}"
        self._defs.setdefault(gid, outline)
        return gid

    def line(self, x: float, y: float, text: str, size: float, fill: str, style: str = "regular",
             anchor: str = "start", attrs: str = "") -> str:
        """One line of text with its baseline at y. anchor is start, middle or end."""
        if not text:
            return ""
        if not covers(text, style):
            return _fallback(x, y, text, size, fill, style, anchor, attrs)
        atlas = font(style)
        pens, total = _layout(text, atlas)
        scale = size / atlas["upm"]
        width = total * scale
        origin = x - (width if anchor == "end" else width / 2 if anchor == "middle" else 0)
        uses = []
        for ch, pen in pens:
            outline = atlas["glyphs"][ch][1]
            if not outline:
                continue
            gid = self._glyph(style, ch, outline)
            uses.append(f'<use href="#{gid}" x="{num(pen)}"/>' if pen else f'<use href="#{gid}"/>')
        return (f'<g transform="translate({num(origin)} {num(y)}) scale({num(scale, 4)})" '
                f'fill="{fill}"{attrs}>{"".join(uses)}</g>')

    def on_curve(self, points: list[tuple[float, float]], text: str, size: float, fill: str,
                 style: str = "italic", attrs: str = "") -> str:
        """Text set glyph by glyph along a polyline, centred on its length."""
        if not text or len(points) < 2:
            return ""
        lengths = [0.0]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            lengths.append(lengths[-1] + math.hypot(bx - ax, by - ay))

        def at(s: float) -> tuple[float, float, float]:
            """Point and tangent angle (degrees) at arc length s, extended straight past either end."""
            i = 1
            while i < len(lengths) - 1 and lengths[i] < s:
                i += 1
            (ax, ay), (bx, by) = points[i - 1], points[i]
            seg = lengths[i] - lengths[i - 1] or 1.0
            t = (s - lengths[i - 1]) / seg
            return ax + (bx - ax) * t, ay + (by - ay) * t, math.degrees(math.atan2(by - ay, bx - ax))

        if not covers(text, style):
            mx, my, angle = at(lengths[-1] / 2)
            transform = f"translate({num(mx)} {num(my)}) rotate({num(angle)})"
            return _fallback(0, 0, text, size, fill, style, "middle", attrs, transform)

        atlas = font(style)
        pens, total = _layout(text, atlas)
        scale = size / atlas["upm"]
        start = (lengths[-1] - total * scale) / 2
        uses = []
        for ch, pen in pens:
            advance, outline = atlas["glyphs"][ch]
            if not outline:
                continue
            px, py, angle = at(start + (pen + advance / 2) * scale)
            gid = self._glyph(style, ch, outline)
            uses.append(f'<use href="#{gid}" transform="translate({num(px)} {num(py)}) rotate({num(angle)}) '
                        f'scale({num(scale, 4)}) translate({num(-advance / 2)} 0)"/>')
        return f'<g fill="{fill}"{attrs}>{"".join(uses)}</g>'

    def defs(self) -> str:
        """The outlines of every glyph used so far; goes inside the SVG's <defs>."""
        return "".join(f'<path id="{gid}" d="{outline}"/>' for gid, outline in self._defs.items())
