"""The robustness contract, as checks that take an SVG string and raise AssertionError.

Each rule exists because breaking it produced a defect that could only be seen
by running the image: an empty first frame, particles that fall apart under
pinch zoom, a frame rate cut to a third.
"""

import math
import re
import xml.etree.ElementTree as ET

from generator import typeset
from generator.motion import GUARD
from tests.svgread import text_runs

SMIL_TAGS = {"animate", "animateTransform", "animateMotion", "set"}
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)
_INLINE_ZERO = re.compile(r"(?:^|;)\s*opacity\s*:\s*0*\.?0*\s*(?:;|$)")
_TRANSLATE = re.compile(r"^translate\((-?[\d.]+)[ ,](-?[\d.]+)\)")
_ROTATE = re.compile(r"rotate\((-?[\d.]+)\)")
_PARTICLES = 5          # a path with this many dots is a particle field


def _tree(svg):
    """(tag, attributes, ancestors' attributes) for every element, root first."""
    def walk(element, ancestors):
        yield element.tag.split("}")[-1], element.attrib, ancestors
        for child in element:
            yield from walk(child, ancestors + [element.attrib])
    yield from walk(ET.fromstring(svg), [])


def _is_zero(value) -> bool:
    try:
        return value is not None and float(value) == 0
    except ValueError:
        return False


def _without_keyframes(css: str) -> str:
    """CSS with every @keyframes block removed."""
    out, i = [], 0
    while i < len(css):
        if css.startswith("@keyframes", i):
            depth, i = 0, css.index("{", i)
            while True:
                depth += (css[i] == "{") - (css[i] == "}")
                i += 1
                if depth == 0:
                    break
        else:
            out.append(css[i])
            i += 1
    return "".join(out)


def _elements(svg):
    for element in ET.fromstring(svg).iter():
        yield element.tag.split("}")[-1], element.attrib


def _classes(attrib):
    return attrib.get("class", "").split()


def viewbox(svg):
    width, height = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
    return int(width), int(height)


def rest_state_is_complete(svg):
    """T1. At rest nothing is hidden except elements that exist only for motion.

    Rest means two things: the image with no animation CSS at all, and the
    image once every animation has played. So hiding by attribute, by inline
    style or by a CSS rule outside @keyframes all count.
    """
    for css in _STYLE.findall(svg):
        assert not re.search(r"opacity\s*:\s*0*\.?0*\s*[;}]", _without_keyframes(css)), \
            "a CSS rule hides an element outside @keyframes"
    for tag, attrib in _elements(_STYLE.sub("", svg)):
        hidden = _is_zero(attrib.get("opacity")) or bool(_INLINE_ZERO.search(attrib.get("style", "")))
        motion_only = "mo" in _classes(attrib)
        assert not hidden or motion_only, f"<{tag}> is invisible at rest but not marked as motion-only"
        assert not motion_only or hidden, f"<{tag}> is motion-only but visible at rest"


def no_forbidden_techniques(svg):
    """T2. No non-scaling strokes, no SMIL, no group opacity on or around particle paths."""
    assert "vector-effect" not in svg, "vector-effect breaks under pinch zoom"
    for tag, attrib, ancestors in _tree(svg):
        assert tag not in SMIL_TAGS, f"<{tag}>: SMIL cannot be switched off by a media query"
        if tag == "path" and attrib.get("d", "").count("h.01") >= _PARTICLES:
            layered = [a for a in [attrib] + ancestors if "opacity" in a and "mo" not in _classes(a)]
            assert not layered, "particle paths use stroke-opacity, never opacity (nor inside a group with opacity)"


def motion_is_guarded(svg):
    """T3a. Every animation lives inside the reduced-motion media query."""
    outside = _STYLE.sub("", svg)
    assert "@keyframes" not in outside, "keyframes declared outside <style>"
    for _tag, attrib in _elements(outside):
        style = attrib.get("style", "")
        assert "animation-name" not in style and not re.search(r"(?:^|;)\s*animation\s*:", style), \
            "an inline style names an animation; only delay, duration and custom properties may be inline"
    for css in _STYLE.findall(svg):
        assert css.startswith(GUARD + "{"), "CSS must open with the reduced-motion guard"
        depth = 0
        for index, char in enumerate(css):
            depth += (char == "{") - (char == "}")
            if depth == 0 and char == "}":
                assert index == len(css) - 1, "CSS found after the reduced-motion guard closed"
                break


def no_motion_at_all(svg):
    """T3b. With motion switched off there is no CSS, no animation and no motion-only element."""
    assert "<style" not in svg and "@keyframes" not in svg and "animation" not in svg
    for tag, attrib in _elements(svg):
        assert "class" not in attrib, f"<{tag}> still carries an animation class"


def text_stays_inside(svg):
    """T4a. Every line of text sits inside the viewBox: outlined runs and <text> fallbacks alike."""
    width, height = viewbox(svg)
    for run in text_runs(svg):
        assert run["x"] >= 0 and run["x"] + run["width"] <= width, f"'{run['text']}' leaves the plate sideways"
        assert run["size"] * 0.7 <= run["y"] <= height, f"'{run['text']}' leaves the plate vertically"
    for element in ET.fromstring(svg).iter():
        if element.tag.split("}")[-1] != "text":
            continue
        attrib, content = element.attrib, "".join(element.itertext())
        size = float(attrib.get("font-size", 16))
        style = "italic" if attrib.get("font-style") == "italic" else "regular"
        span = typeset.measure(content, size, style)
        moved = _TRANSLATE.match(attrib.get("transform", ""))
        x = float(moved.group(1)) if moved else float(attrib.get("x", 0))
        y = float(moved.group(2)) if moved else float(attrib.get("y", 0))
        anchor = attrib.get("text-anchor", "start")
        turned = _ROTATE.search(attrib.get("transform", ""))
        angle = math.radians(float(turned.group(1))) if turned else 0.0
        # the line runs from `begin` to `begin + span` along its own direction
        begin = -(span if anchor == "end" else span / 2 if anchor == "middle" else 0)
        ends = [(x + s * math.cos(angle), y + s * math.sin(angle)) for s in (begin, begin + span)]
        assert all(-0.01 <= ex <= width + 0.01 for ex, _ey in ends), f"fallback text '{content}' leaves the plate sideways"
        assert all(-0.01 <= ey <= height + 0.01 for _ex, ey in ends), f"fallback text '{content}' leaves the plate vertically"


def text_strokes_are_thin(svg):
    """T4c. An outline behind fallback text is a few pixels wide, never wide enough to paint over the plate."""
    for element in ET.fromstring(svg).iter():
        if element.tag.split("}")[-1] != "text" or "stroke-width" not in element.attrib:
            continue
        size = float(element.attrib.get("font-size", 16))
        width = float(element.attrib["stroke-width"])
        assert width <= size / 2, f"fallback text '{''.join(element.itertext())}' has a {width} px outline"


def placements_are_inside(svg):
    """T4b. Every element placed by translate(x y) in the plate's own coordinates is inside the viewBox.

    That covers stars, labels, glyphs set along a curve and anything else
    positioned absolutely. Coordinates inside an already transformed group are
    in another space and are not judged.
    """
    width, height = viewbox(svg)
    for tag, attrib, ancestors in _tree(svg):
        moved = _TRANSLATE.match(attrib.get("transform", ""))
        if not moved or any("transform" in a for a in ancestors):
            continue
        x, y = float(moved.group(1)), float(moved.group(2))
        assert 0 <= x <= width and 0 <= y <= height, f"<{tag}> is placed outside the plate at ({x}, {y})"


def within_budget(svg, max_bytes, max_animated):
    """T6. File size and number of animated elements."""
    size = len(svg.encode("utf-8"))
    assert size <= max_bytes, f"{size} bytes, over the {max_bytes} budget"
    animated = sum(1 for _tag, attrib in _elements(svg) if "class" in attrib)
    assert animated <= max_animated, f"{animated} animated elements, over the {max_animated} budget"


def svg_is_sound(svg):
    """T10. Well-formed XML, unique ids, every reference resolves."""
    ids = [attrib["id"] for _tag, attrib in _elements(svg) if "id" in attrib]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicated ids: {sorted(duplicates)}"
    wanted = set(re.findall(r'href="#([^"]+)"', svg)) | set(re.findall(r"url\(#([^)]+)\)", svg))
    wanted |= {ref for group in re.findall(r'aria-labelledby="([^"]+)"', svg) for ref in group.split()}
    missing = wanted - set(ids)
    assert not missing, f"references to undefined ids: {sorted(missing)}"


def is_accessible(svg):
    """T12. An image role with a title and a description."""
    root = ET.fromstring(svg)
    assert root.attrib.get("role") == "img"
    texts = {child.tag.split("}")[-1]: (child.text or "").strip() for child in root}
    assert texts.get("title") and texts.get("desc"), "title and desc must both say something"
