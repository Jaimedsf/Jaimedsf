"""Text as outlines: measurement, line setting, wrapping and text on a curve."""

import math
import re

import pytest

from generator import typeset
from generator.typeset import Typesetter, measure, wrap


def atlas(style="regular"):
    return typeset.font(style)


def group_origin(svg):
    """(x, y, scale) of the first text group in an SVG fragment."""
    m = re.search(r'<g transform="translate\(([-\d.]+) ([-\d.]+)\) scale\(([\d.]+)\)"', svg)
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def use_offsets(svg):
    """[(glyph id, x in font units)] for every glyph of a text group."""
    return [(gid, float(x or 0)) for gid, x in re.findall(r'<use href="#(\w+)"(?: x="(-?[\d.]+)")?/>', svg)]


# ── measure ──────────────────────────────────────────────────────────────────

def test_kerned_pair_is_narrower_than_its_two_letters():
    assert measure("AV", 100) < measure("A", 100) + measure("V", 100)


def test_width_is_advances_plus_kerning_scaled_by_size():
    glyphs, kern, upm = atlas()["glyphs"], atlas()["kern"], atlas()["upm"]
    expected = (glyphs["A"][0] + glyphs["V"][0] + kern["AV"]) * 50 / upm
    assert measure("AV", 50) == pytest.approx(expected)


def test_width_scales_linearly_with_size():
    assert measure("galaxy-profile", 27) == pytest.approx(2 * measure("galaxy-profile", 13.5))


def test_styles_measure_differently():
    assert measure("Vinícius Melo", 48, "light") != measure("Vinícius Melo", 48, "medium")


def test_empty_text_has_no_width():
    assert measure("", 20) == 0


# ── line ─────────────────────────────────────────────────────────────────────

def test_line_places_each_glyph_at_its_pen_position():
    glyphs, kern = atlas()["glyphs"], atlas()["kern"]
    svg = Typesetter().line(10, 20, "AV", 16, "#fff")
    assert use_offsets(svg) == [("r41", 0), ("r56", glyphs["A"][0] + kern["AV"])]


def test_line_starts_at_x_by_default():
    x, y, scale = group_origin(Typesetter().line(10, 20, "Web", 16, "#fff"))
    assert (x, y) == (10, 20)
    assert scale == pytest.approx(16 / 1000)


def test_end_anchor_finishes_at_x():
    x, _y, _s = group_origin(Typesetter().line(300, 20, "galaxy-profile", 13.5, "#fff", anchor="end"))
    assert x + measure("galaxy-profile", 13.5) == pytest.approx(300, abs=0.06)


def test_middle_anchor_is_centred_on_x():
    x, _y, _s = group_origin(Typesetter().line(300, 20, "Oct", 11.5, "#fff", anchor="middle"))
    assert x + measure("Oct", 11.5) / 2 == pytest.approx(300, abs=0.06)


def test_space_advances_the_pen_without_drawing():
    glyphs = atlas()["glyphs"]
    offsets = use_offsets(Typesetter().line(0, 0, "a b", 16, "#fff"))
    assert [gid for gid, _ in offsets] == ["r61", "r62"]
    assert offsets[1][1] >= glyphs["a"][0] + glyphs[" "][0] - 40


def test_line_carries_fill_and_extra_attributes():
    svg = Typesetter().line(0, 0, "a", 16, "#9fbcff", attrs=' class="soft"')
    assert 'fill="#9fbcff"' in svg and 'class="soft"' in svg


def test_empty_line_draws_nothing():
    assert Typesetter().line(0, 0, "", 16, "#fff") == ""


# ── defs ─────────────────────────────────────────────────────────────────────

def test_each_used_glyph_is_defined_once():
    ts = Typesetter()
    ts.line(0, 0, "aa", 16, "#fff")
    ts.line(0, 20, "a", 12, "#fff")
    assert ts.defs().count('id="r61"') == 1


def test_same_letter_in_two_styles_gets_two_definitions():
    ts = Typesetter()
    ts.line(0, 0, "a", 16, "#fff")
    ts.line(0, 20, "a", 16, "#fff", style="italic")
    defs = ts.defs()
    assert 'id="r61"' in defs and 'id="i61"' in defs


def test_defs_only_holds_what_was_used():
    ts = Typesetter()
    ts.line(0, 0, "a", 16, "#fff")
    assert ts.defs().count("<path") == 1


# ── wrap ─────────────────────────────────────────────────────────────────────

LONG = ("A component library with cosmic design tokens, dark-first theming and an "
        "absurdly long description that keeps going well past what any card could hold")


def test_wrap_keeps_short_text_on_one_line():
    assert wrap("Short text", 14.5, "italic", 300) == ["Short text"]


def test_wrapped_lines_never_exceed_the_width():
    for line in wrap(LONG, 14.5, "italic", 300):
        assert measure(line, 14.5, "italic") <= 300


def test_wrap_cuts_with_an_ellipsis_when_lines_run_out():
    lines = wrap(LONG, 14.5, "italic", 300, max_lines=2)
    assert len(lines) == 2 and lines[-1].endswith("…")


def test_wrap_cuts_a_single_word_that_is_too_wide():
    lines = wrap("a" * 80, 23, "medium", 200, max_lines=1)
    assert len(lines) == 1 and lines[0].endswith("…")
    assert measure(lines[0], 23, "medium") <= 200


def test_wrap_of_nothing_is_no_lines():
    assert wrap("", 14, "regular", 100) == []


# ── text on a curve ──────────────────────────────────────────────────────────

def arc(n=60, r=120, cx=200, cy=200):
    return [(cx + r * math.cos(math.pi + math.pi * k / n), cy + r * math.sin(math.pi + math.pi * k / n))
            for k in range(n + 1)]


def dist_to_polyline(p, pts):
    best = float("inf")
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy))
    return best


def curve_anchors(svg):
    return [(float(x), float(y)) for x, y in re.findall(r'transform="translate\(([-\d.]+) ([-\d.]+)\) rotate', svg)]


def test_glyphs_on_a_curve_sit_on_the_curve():
    pts = arc()
    anchors = curve_anchors(Typesetter().on_curve(pts, "Web & Cloud", 13.5, "#fff"))
    assert len(anchors) == len("Web&Cloud")
    assert max(dist_to_polyline(a, pts) for a in anchors) < 0.5


def test_text_on_a_curve_reads_left_to_right_and_is_centred():
    pts = arc()
    anchors = curve_anchors(Typesetter().on_curve(pts, "AI & Data", 13.5, "#fff"))
    xs = [a[0] for a in anchors]
    assert xs == sorted(xs)
    assert (xs[0] + xs[-1]) / 2 == pytest.approx(200, abs=6)


def test_glyphs_on_a_curve_follow_its_tangent():
    svg = Typesetter().on_curve(arc(), "AI & Data", 13.5, "#fff")
    angles = [float(a) for a in re.findall(r"rotate\((-?[\d.]+)\)", svg)]
    assert angles[0] < 0 < angles[-1]


# ── outside the font's coverage ──────────────────────────────────────────────

def test_text_outside_the_coverage_falls_back_to_a_system_serif():
    svg = Typesetter().line(10, 20, "日本語 repo", 16, "#fff", anchor="end")
    assert svg.startswith("<text") and "Georgia" in svg and 'text-anchor="end"' in svg
    assert "日本語 repo" in svg


def test_fallback_text_is_escaped():
    svg = Typesetter().line(0, 0, "R&D <日本>", 16, "#fff")
    assert "R&amp;D &lt;日本&gt;" in svg


def test_fallback_keeps_the_style():
    svg = Typesetter().line(0, 0, "日本", 16, "#fff", style="italic")
    assert 'font-style="italic"' in svg


def test_measure_estimates_uncovered_text_instead_of_failing():
    assert measure("日本語", 16) > 0


def test_curve_text_outside_the_coverage_falls_back_too():
    svg = Typesetter().on_curve(arc(), "日本語", 13.5, "#fff")
    assert svg.startswith("<text") and "rotate(" in svg
