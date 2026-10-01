"""Test helper: read text back out of a generated SVG.

Text is drawn as glyph outlines, so there are no strings to grep for. Each
text line is a <g translate scale> of <use> elements whose ids name the style
and the character; this rebuilds the characters and the line's box.
"""

import re

from generator import typeset

_STYLE = {"l": "light", "r": "regular", "m": "medium", "i": "italic"}
_GROUP = re.compile(
    r'<g transform="translate\(([-\d.]+) ([-\d.]+)\) scale\(([\d.]+)\)"[^>]*>'
    r'((?:<use href="#[lrmi][0-9a-f]+"(?: x="-?[\d.]+")?/>)+)</g>')
_USE = re.compile(r'<use href="#([lrmi])([0-9a-f]+)"(?: x="(-?[\d.]+)")?/>')


def text_runs(svg):
    """[{x, y, size, width, text}] for every outlined text line. Spaces are not in `text`."""
    runs = []
    for x, y, scale, body in _GROUP.findall(svg):
        uses = _USE.findall(body)
        style = _STYLE[uses[-1][0]]
        atlas = typeset.font(style)
        last_char = chr(int(uses[-1][1], 16))
        end = float(uses[-1][2] or 0) + atlas["glyphs"][last_char][0]
        runs.append({
            "x": float(x), "y": float(y), "size": float(scale) * atlas["upm"],
            "width": end * float(scale), "style": style,
            "text": "".join(chr(int(code, 16)) for _s, code, _x in uses),
        })
    return runs


def texts(svg):
    return [run["text"] for run in text_runs(svg)]
