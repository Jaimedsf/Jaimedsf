"""Text as outlines: measurement, line setting, wrapping and text on a curve."""

import math
import re

import pytest

from generator import typeset
from generator.svg import num
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


def test_a_cut_at_a_word_that_would_waste_the_line_goes_on_into_the_next_word():
    name = "Maximiliana Wolfeschlegelsteinhausenbergerdorff the Third"
    line = wrap(name, 30, "light", 380, max_lines=1)[0]
    assert line.startswith("Maximiliana Wolfeschl") and line.endswith("…")
    assert 380 - 30 < measure(line, 30, "light") <= 380


def test_a_cut_near_the_end_of_the_line_stays_between_words():
    lines = wrap(LONG, 14.5, "italic", 300, max_lines=2)
    kept = " ".join(lines)[:-1]
    assert lines[-1].endswith("…") and clean_spaces(LONG).startswith(kept)
    assert clean_spaces(LONG)[len(kept)] == " "                   # the text goes on with a new word
    assert measure(lines[-1], 14.5, "italic") > 300 * 2 / 3


def test_a_cut_line_is_never_left_less_than_two_thirds_full():
    for width in range(80, 320, 7):
        for text in (LONG, "Maximiliana Wolfeschlegelsteinhausenbergerdorff the Third", "one two " + "w" * 60):
            line = wrap(text, 14.5, "italic", width, max_lines=1)[0]
            assert line.endswith("…")
            assert width * 2 / 3 - 14.5 < measure(line, 14.5, "italic") <= width


def test_a_cut_never_leaves_a_space_before_the_ellipsis():
    for width in range(60, 300, 7):
        line = wrap(LONG, 14.5, "italic", width, max_lines=1)[0]
        assert not line.endswith(" …") and measure(line, 14.5, "italic") <= width


def clean_spaces(text):
    return " ".join(text.split())


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


# ── review fixes: fallback width for wide scripts, and control characters ────

import xml.etree.ElementTree as ET


def test_wide_characters_are_estimated_at_one_em_each():
    assert measure("日本語", 16) >= 3 * 16 * 0.95


def test_emoji_is_estimated_at_one_em():
    assert measure("🚀", 16) >= 16 * 0.95


def test_latin_inside_a_fallback_string_gets_a_margin_because_the_system_serif_is_wider():
    spectral = measure("Deploy rockets", 20)
    assert measure("Deploy rockets 🚀", 20) >= spectral * 1.1 + 20 * 0.95


def test_wrapped_cjk_lines_hold_no_more_characters_than_fit():
    lines = wrap("日本語の説明" * 12, 14.5, "italic", 230, max_lines=2)
    assert len(lines) == 2
    assert all(len(line) <= 230 / 14.5 + 1 for line in lines)


def test_control_characters_never_reach_the_svg():
    svg = "<svg xmlns='http://www.w3.org/2000/svg'>" + Typesetter().line(0, 20, "a\x08b\x00 日本", 16, "#fff") + "</svg>"
    assert "\x08" not in svg and "\x00" not in svg
    ET.fromstring(svg)


def test_control_characters_do_not_count_as_width():
    assert measure("ab", 20) == measure("a\x08b", 20)


# ── balanced two-line wrapping ───────────────────────────────────────────────

PHRASE = "Solving one problem at a time, with code and creativity."


def test_balanced_wrap_breaks_at_the_comma_instead_of_leaving_one_word_behind():
    assert wrap(PHRASE, 14.5, "italic", 320) == ["Solving one problem at a time, with code and", "creativity."]
    assert wrap(PHRASE, 14.5, "italic", 320, balance=True) == ["Solving one problem at a time,",
                                                              "with code and creativity."]


def test_balanced_wrap_keeps_one_line_when_one_line_is_enough():
    assert wrap("AI Engineer", 14.5, "italic", 320, balance=True) == ["AI Engineer"]


def test_balanced_wrap_never_exceeds_the_width():
    text = "Building tools that make developers' lives easier and their deploys boring"
    for line in wrap(text, 14.5, "italic", 260, balance=True):
        assert measure(line, 14.5, "italic") <= 260


# ── an outline behind the letters ────────────────────────────────────────────

def test_a_halo_is_as_wide_as_asked_whatever_the_size_of_the_text():
    svg = Typesetter().line(10, 20, "Halo", 20, "#fff", halo=("#000", 3, 0.5))
    scale = 20 / 1000
    assert f'stroke="#000" stroke-width="{num(3 / scale)}" stroke-opacity=".5"' in svg
    assert 'paint-order="stroke"' in svg and 'stroke-linejoin="round"' in svg


def test_a_halo_on_fallback_text_is_in_pixels_not_in_font_units():
    svg = Typesetter().line(10, 20, "銀河", 20, "#fff", halo=("#000", 3, 0.5))
    assert svg.startswith("<text") and 'stroke-width="3"' in svg and 'paint-order="stroke"' in svg


def test_a_halo_on_curve_text_follows_the_same_rule():
    curve = [(0, 0), (100, 0), (200, 0)]
    outlined = Typesetter().on_curve(curve, "Halo", 10, "#fff", halo=("#000", 3.5, 1))
    assert f'stroke-width="{num(3.5 / (10 / 1000))}"' in outlined and "stroke-opacity" not in outlined
    fallback = Typesetter().on_curve(curve, "銀河", 10, "#fff", halo=("#000", 3.5, 1))
    assert fallback.startswith("<text") and 'stroke-width="3.5"' in fallback


def test_without_a_halo_there_is_no_stroke():
    assert "stroke" not in Typesetter().line(10, 20, "Plain", 20, "#fff")
