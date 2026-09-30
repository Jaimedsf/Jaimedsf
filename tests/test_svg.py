"""SVG primitives."""

import pytest

from generator.svg import esc, num


def test_num_drops_a_trailing_zero():
    assert num(12.0) == "12"


def test_num_rounds_to_one_decimal_by_default():
    assert num(3.14159) == "3.1"


def test_num_never_prints_negative_zero():
    assert num(-0.04) == "0"


def test_num_keeps_more_places_when_asked():
    assert num(0.25, 2) == ".25"
    assert num(0.0135, 4) == ".0135"


def test_num_drops_the_leading_zero_of_fractions():
    assert num(0.5) == ".5"
    assert num(-0.5) == "-.5"


def test_esc_escapes_xml_specials_including_quotes():
    assert esc('R&D <"x">') == "R&amp;D &lt;&quot;x&quot;&gt;"


# ── particles ────────────────────────────────────────────────────────────────

import math
import re

from generator.motion import Motion
from generator.svg import comet, dots, frame, path_def, spike_half, star, star_defs
from generator.themes import get_theme

SKY = get_theme("deep-sky", "dark")
INK = get_theme("deep-sky", "light")


def dot_positions(svg):
    """Rebuild absolute dot coordinates from a dots() path."""
    d = re.search(r' d="([^"]+)"', svg).group(1)
    out, x, y = [], 0.0, 0.0
    for cmd, a, b in re.findall(r"([Mm])(-?[\d.]+) (-?[\d.]+)h\.01", d):
        x, y = (float(a), float(b)) if cmd == "M" else (x + float(a), y + float(b))
        out.append((x, y))
        x += 0.01
    return out


def test_dots_keep_every_point_within_a_twentieth_of_a_pixel():
    points = [(10.04, 20.96), (300.26, 5.5), (12.0, 400.123), (11.99, 399.87)] * 40
    rebuilt = dot_positions(dots(points, 1.7, "#a9c7ff", 0.9))
    assert len(rebuilt) == len(points)
    assert max(max(abs(px - rx), abs(py - ry)) for (px, py), (rx, ry) in zip(points, rebuilt)) <= 0.0501


def test_dots_are_round_capped_strokes_that_use_stroke_opacity():
    svg = dots([(1, 2), (3, 4)], 1.7, "#a9c7ff", 0.9)
    assert 'stroke-linecap="round"' in svg and 'stroke-opacity=".9"' in svg and 'stroke-width="1.7"' in svg
    assert " opacity=" not in svg and 'fill="none"' in svg


def test_fully_opaque_dots_carry_no_opacity_at_all():
    assert "opacity" not in dots([(1, 2)], 1, "#fff", 1)


def test_no_points_no_path():
    assert dots([], 1, "#fff", 1) == ""


# ── the repository star ──────────────────────────────────────────────────────

def test_spike_length_grows_with_the_logarithm_of_the_stars():
    assert spike_half(0) == 7
    assert spike_half(9) == pytest.approx(15.5)
    assert spike_half(99) == pytest.approx(24)


def test_active_star_has_a_pulsing_halo_spikes_and_a_small_core():
    svg = star(9, "now", SKY, Motion())
    assert 'fill="url(#hn)"' in svg and 'class="tw"' in svg
    assert "M-15.5 0" in svg                                   # spike half-length for 9 stars
    assert 'r="2.2" fill="url(#cn)"' in svg                     # core: 1.5 + 0.7 * log10(10)


def test_star_pushed_this_year_does_not_pulse():
    svg = star(9, "year", SKY, Motion())
    assert 'fill="url(#hy)"' in svg and 'class="tw"' not in svg


def test_dormant_star_is_a_hollow_ring_without_spikes():
    svg = star(9, "dorm", SKY, Motion())
    assert "<path" not in svg and 'fill="none"' in svg and f'stroke="{SKY.dorm}"' in svg


def test_star_without_motion_carries_no_animation_classes():
    assert "class=" not in star(9, "now", SKY, Motion(False))


def test_star_defs_define_every_gradient_the_glyph_refers_to():
    defs = star_defs(SKY)
    for gid in ("hn", "hy", "cn", "cy", "sn", "sy", "vn", "vy"):
        assert f'id="{gid}"' in defs


def test_dark_stars_have_a_white_hot_core_and_ink_stars_do_not():
    assert "#ffffff" in star_defs(SKY)
    assert "#ffffff" not in star_defs(INK)


# ── the travelling light ─────────────────────────────────────────────────────

def test_comet_is_made_only_of_motion_elements_invisible_at_rest():
    svg = comet("c1", SKY, Motion(), cycle=8, start=3)
    uses = re.findall(r"<use [^>]+>", svg)
    assert len(uses) == 5
    assert all('href="#c1"' in u and "mo" in re.search(r'class="([^"]+)"', u).group(1) and 'opacity="0"' in u
               for u in uses)


def test_comet_does_not_exist_without_motion():
    assert comet("c1", SKY, Motion(False), cycle=8, start=3) == ""


def test_path_def_normalises_the_length_so_dashes_are_fractions_of_the_path():
    assert path_def("c1", "M0 0L10 0") == '<path id="c1" d="M0 0L10 0" pathLength="1" fill="none"/>'


# ── the frame ────────────────────────────────────────────────────────────────

def test_frame_is_an_accessible_image_with_the_themes_background():
    svg = frame(SKY, 850, 214, "<g/>", "Featured projects", "Two projects")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 850 214" width="850" height="214" role="img"')
    assert "<title" in svg and ">Featured projects</title>" in svg and ">Two projects</desc>" in svg
    assert f'<rect width="850" height="214" rx="10" fill="{SKY.bg}"/>' in svg


def test_frame_escapes_title_and_description():
    svg = frame(SKY, 10, 10, "", "R&D <lab>", 'say "hi" & <go>')
    assert "R&amp;D &lt;lab&gt;" in svg and "say &quot;hi&quot; &amp; &lt;go&gt;" in svg


def test_frame_carries_the_motion_css_only_when_there_is_motion():
    moving = Motion()
    moving.cls("pop")
    assert "<style>@media (prefers-reduced-motion: no-preference){" in frame(SKY, 10, 10, "", "t", "d", motion=moving)
    assert "<style>" not in frame(SKY, 10, 10, "", "t", "d", motion=Motion(False))
    assert "<style>" not in frame(SKY, 10, 10, "", "t", "d")
