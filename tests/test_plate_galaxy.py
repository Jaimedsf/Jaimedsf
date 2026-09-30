"""The galaxy plate: geometry, dust, stars, labels and the whole image."""

import math
import random
import re

import pytest

from generator.motion import Motion
from generator.plates import galaxy
from generator.plates.galaxy import PHI, R0, TURNS, Geometry, dust
from generator.svg import num
from generator.themes import get_theme

SKY = get_theme("deep-sky", "dark")


def transform(point, degrees, scale):
    a = math.radians(degrees)
    x, y = point[0] * scale, point[1] * scale
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


# ── geometry ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mobile", [False, True])
def test_the_spiral_reaches_the_rim_after_one_and_a_half_turns(mobile):
    geo = Geometry(mobile, 2)
    assert R0 * math.exp(geo.b * TURNS * 2 * math.pi) == pytest.approx(geo.radius)


def test_desktop_and_mobile_frames():
    desktop, mobile = Geometry(False, 2), Geometry(True, 2)
    assert (desktop.width, desktop.height, desktop.cx, desktop.cy, desktop.radius) == (850, 430, 630, 215, 196)
    assert (mobile.width, mobile.height, mobile.cx, mobile.cy, mobile.radius) == (390, 478, 195, 282, 172)


def test_a_point_on_an_arm_is_at_the_asked_distance_from_the_core():
    geo = Geometry(False, 3)
    for r in (20, 77.7, 196):
        x, y = geo.point(1, r)
        assert math.hypot(x - geo.cx, y - geo.cy) == pytest.approx(r)


@pytest.mark.parametrize("arms", [1, 2, 3, 6])
def test_arms_are_evenly_spaced(arms):
    geo = Geometry(False, arms)
    steps = {round(geo.angle(i + 1) - geo.angle(i), 9) for i in range(arms)}
    assert steps == {round(2 * math.pi / arms, 9)}


def test_flow_starts_at_the_identity():
    assert Geometry(False, 2).flow(0) == (0, 1)


def test_one_flow_cycle_carries_every_tile_copy_onto_the_next_one():
    """T11. The loop has no seam: copy j, after a full cycle, is exactly where copy j+1 started."""
    geo = Geometry(False, 2)
    base = geo.plane(0, 150.0)
    for j in (-6, -3, -1):
        moved = transform(transform(base, *geo.copy(j)), *geo.flow(1))
        target = transform(base, *geo.copy(j + 1))
        assert math.hypot(moved[0] - target[0], moved[1] - target[1]) < 0.01


def test_every_copy_of_a_point_on_the_arm_is_still_on_the_arm():
    geo = Geometry(False, 2)
    for j in (-5, -2, 0):
        copied = transform(geo.plane(1, 170.0), *geo.copy(j))
        on_arm = geo.plane(1, 170.0 * geo.k ** j)
        assert math.hypot(copied[0] - on_arm[0], copied[1] - on_arm[1]) < 0.01


def test_half_a_cycle_is_half_the_rotation_and_the_square_root_of_the_scale():
    geo = Geometry(False, 2)
    degrees, scale = geo.flow(0.5)
    assert degrees == pytest.approx(math.degrees(PHI) / 2) and scale == pytest.approx(math.sqrt(geo.k))


# ── dust ─────────────────────────────────────────────────────────────────────

def make_dust(cuts=(196.0, 171.5), mobile=False, motion=True, seed="ada"):
    geo = Geometry(mobile, len(cuts))
    mo = Motion(motion)
    defs, body = dust(geo, list(cuts), SKY, random.Random(seed), mo)
    return geo, mo, defs, body


def test_each_arm_has_three_layers_each_behind_its_own_mask():
    _geo, _mo, defs, body = make_dust()
    assert defs.count("<mask ") == 6 and body.count('mask="url(#') == 6


def test_a_short_arm_skips_the_layer_that_would_lie_beyond_its_cut():
    _geo, _mo, defs, _body = make_dust(cuts=(196.0, 60.0))
    assert defs.count("<mask ") == 5


def test_tile_copies_reach_from_the_rim_down_into_the_core():
    geo, _mo, _defs, body = make_dust(cuts=(196.0,))
    scales = sorted(float(v) for v in re.findall(r"scale\(([\d.]+)\)", body))
    assert scales[-1] == 1                                    # the tile itself, at the rim
    assert geo.radius * scales[0] < R0                         # the innermost copy is inside the core


def test_particles_carry_no_group_opacity_and_no_fixed_pixel_size_tricks():
    _geo, _mo, defs, body = make_dust()
    assert " opacity=" not in defs + body and "vector-effect" not in defs + body


def test_flow_is_one_class_with_exact_keyframes_for_a_sixty_degree_step():
    geo, mo, _defs, body = make_dust()
    frames = re.search(r"@keyframes flow\{(.*?\})\}", mo.css()).group(1)
    assert body.count('class="flow"') == 6
    assert f"100%{{transform:rotate(60deg) scale({num(geo.k, 4)})}}" in frames
    assert frames.count("rotate(") == 5                        # 0, 15, 30, 45 and 60 degrees


def test_the_bulge_swirls():
    _geo, mo, _defs, body = make_dust()
    assert 'class="swirl"' in body and "@keyframes swirl" in mo.css()


def test_without_motion_the_dust_is_the_same_but_still():
    _geo, mo, defs, body = make_dust(motion=False)
    assert "class=" not in body and mo.css() == ""
    assert body.count("<use ") > 20 and defs.count("<mask ") == 6


def test_same_seed_same_dust_and_another_seed_another_dust():
    assert make_dust()[2:] == make_dust()[2:]
    assert make_dust(seed="ada")[2] != make_dust(seed="babbage")[2]


def test_large_particles_stay_on_the_axis_of_the_arm():
    geo = Geometry(False, 2)
    tile = galaxy._tile(geo, 0, 4000, 1.0, SKY, random.Random("ada"))
    start = TURNS * 2 * math.pi - PHI
    small = sorted({width for (_c, width, _o, _b) in tile})[:2]
    strays = 0
    for (_colour, width, _opacity, _bloom), points in tile.items():
        for x, y in points:
            s = (math.atan2(y, x) - geo.angle(0) - start) % (2 * math.pi)
            off_axis = abs(math.hypot(x, y) / (R0 * math.exp(geo.b * (start + s))) - 1)
            if off_axis > galaxy.OFF_AXIS + 1e-6:
                strays += 1
                assert width in small, f"a {width}px particle sits {off_axis:.0%} off the arm"
    assert strays > 100          # the test must actually have seen off-axis particles
