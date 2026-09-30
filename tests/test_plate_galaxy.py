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


# ── repository stars ─────────────────────────────────────────────────────────

from datetime import date, timedelta

import yaml

from generator.config import validate_config
from generator.data import Repo, load_demo
from generator.model import Arm, GalaxyModel
from generator.model import galaxy as galaxy_model
from generator.plates.galaxy import arm_cuts, place_stars


def demo_model():
    with open("config.example.yml", encoding="utf-8") as handle:
        return galaxy_model(load_demo(), validate_config(yaml.safe_load(handle)))


def repo(name, created, stars=0):
    return Repo(name=name, owner="ada", stars=stars, created=created, pushed=created, description="",
                primary_language="Python", languages={"Python": 1}, topics=(), is_fork=False)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def test_the_arm_with_most_repositories_reaches_the_rim_and_the_others_are_shorter():
    model, geo = demo_model(), Geometry(False, 3)
    assert arm_cuts(model, geo) == pytest.approx([196, 196 * (0.5 + 0.5 * 4 / 5), 196 * (0.5 + 0.5 * 1 / 5)])


def test_unnamed_arms_of_an_unmatched_galaxy_have_a_fixed_length():
    model = GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=())
    assert arm_cuts(model, Geometry(False, 2)) == pytest.approx([196 * 0.8, 196 * 0.8])


@pytest.mark.parametrize("mobile", [False, True])
def test_every_star_is_inside_the_frame(mobile):
    model = demo_model()
    geo = Geometry(mobile, len(model.arms))
    positions = place_stars(model, geo, random.Random("galaxy-dev"))
    assert set(positions) == set(model.order)
    assert all(0 <= x <= geo.width and 0 <= y <= geo.height for x, y in positions.values())


def test_stars_on_an_arm_sit_on_its_curve_further_out_the_newer_they_are():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, random.Random("galaxy-dev"))
    for index, arm in enumerate(model.arms):
        radii = [distance(positions[r.name], (geo.cx, geo.cy)) for r in arm.repos]
        assert radii == sorted(radii)
        for r, radius in zip(arm.repos, radii):
            assert distance(positions[r.name], geo.point(index, radius)) < 0.01


def test_stars_on_an_arm_stay_between_the_core_and_the_arms_cut():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, random.Random("galaxy-dev"))
    for arm, cut in zip(model.arms, arm_cuts(model, geo)):
        for r in arm.repos:
            assert geo.radius * 0.26 <= distance(positions[r.name], (geo.cx, geo.cy)) <= cut * 0.95 + 0.01


def test_loose_stars_keep_their_distance_from_every_other_star():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, random.Random("galaxy-dev"))
    for loose in model.loose:
        others = [p for name, p in positions.items() if name != loose.name]
        assert min(distance(positions[loose.name], p) for p in others) >= 14


def test_forty_repositories_on_one_arm_are_all_drawn_inside_its_cut():
    day = date(2020, 1, 1)
    arm = Arm("Backend", tuple(repo(f"r{i:02d}", day + timedelta(days=30 * i)) for i in range(40)))
    model = GalaxyModel(arms=(arm,), loose=(), labels=frozenset(), order=tuple(r.name for r in arm.repos))
    geo = Geometry(False, 1)
    positions = place_stars(model, geo, random.Random("x"))
    assert len(positions) == 40
    assert max(distance(p, (geo.cx, geo.cy)) for p in positions.values()) <= 196 * 0.95 + 0.01
    assert all(0 <= x <= geo.width and 0 <= y <= geo.height for x, y in positions.values())


def test_empty_galaxy_has_no_stars():
    model = GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=())
    assert place_stars(model, Geometry(False, 2), random.Random("x")) == {}


def test_same_seed_same_sky():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    assert place_stars(model, geo, random.Random("s")) == place_stars(model, geo, random.Random("s"))
