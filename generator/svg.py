"""SVG primitives shared by every plate."""

from __future__ import annotations

from xml.sax.saxutils import escape as _xml_escape


def num(value: float, places: int = 1) -> str:
    """Format a number for SVG: rounded, no trailing zeros, no leading zero, never "-0"."""
    text = f"{round(value, places):.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("-0", "-", ""):
        return "0"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def esc(text) -> str:
    """Escape text for an SVG text node or a double-quoted attribute."""
    return _xml_escape(str(text), {'"': "&quot;"})
