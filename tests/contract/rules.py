"""The robustness contract, as checks that take an SVG string and raise AssertionError.

Each rule exists because breaking it produced a defect that could only be seen
by running the image: an empty first frame, particles that fall apart under
pinch zoom, a frame rate cut to a third.
"""

import re
import xml.etree.ElementTree as ET

from generator.motion import GUARD
from tests.svgread import text_runs

SMIL_TAGS = {"animate", "animateTransform", "animateMotion", "set"}
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)


def _elements(svg):
    for element in ET.fromstring(svg).iter():
        yield element.tag.split("}")[-1], element.attrib


def _classes(attrib):
    return attrib.get("class", "").split()


def viewbox(svg):
    width, height = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups()
    return int(width), int(height)


def rest_state_is_complete(svg):
    """T1. Without the animation CSS, nothing is hidden except elements that exist only for motion."""
    for tag, attrib in _elements(_STYLE.sub("", svg)):
        hidden, motion_only = attrib.get("opacity") == "0", "mo" in _classes(attrib)
        assert not hidden or motion_only, f"<{tag}> is invisible at rest but not marked as motion-only"
        assert not motion_only or hidden, f"<{tag}> is motion-only but visible at rest"


def no_forbidden_techniques(svg):
    """T2. No non-scaling strokes, no SMIL, no group opacity on particle paths."""
    assert "vector-effect" not in svg, "vector-effect breaks under pinch zoom"
    for tag, attrib in _elements(svg):
        assert tag not in SMIL_TAGS, f"<{tag}>: SMIL cannot be switched off by a media query"
        if tag == "path" and attrib.get("d", "").count("h.01") >= 5:
            assert "opacity" not in attrib, "particle paths use stroke-opacity, never opacity"


def motion_is_guarded(svg):
    """T3a. Every animation lives inside the reduced-motion media query."""
    outside = _STYLE.sub("", svg)
    assert "@keyframes" not in outside and "animation:" not in outside, "animation declared outside <style>"
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
    """T4. Every outlined text line sits inside the viewBox."""
    width, height = viewbox(svg)
    for run in text_runs(svg):
        assert run["x"] >= 0 and run["x"] + run["width"] <= width, f"'{run['text']}' leaves the plate sideways"
        assert run["size"] * 0.7 <= run["y"] <= height, f"'{run['text']}' leaves the plate vertically"


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
