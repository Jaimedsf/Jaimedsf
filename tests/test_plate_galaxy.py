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


def test_each_arm_has_three_layers_each_behind_a_mask():
    _geo, _mo, defs, body = make_dust()
    assert body.count('mask="url(#') == 6
    assert defs.count("<mask ") == 5          # the inner layer ends at the same radius on both arms


def test_a_short_arm_skips_the_layer_that_would_lie_beyond_its_cut():
    _geo, _mo, _defs, body = make_dust(cuts=(196.0, 60.0))
    assert body.count('mask="url(#') == 5


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
    # five frames: 0, 15, 30, 45 and 60 degrees, each with the scale the spiral has grown by at that angle
    assert frames == "".join(
        f"{25 * q}%{{transform:rotate({15 * q}deg) scale({num(geo.k ** (q / 4), 4)})}}" for q in range(5))
    assert frames.startswith("0%{transform:rotate(0deg) scale(1)}")


def test_the_bulge_swirls():
    _geo, mo, _defs, body = make_dust()
    assert 'class="swirl"' in body and "@keyframes swirl" in mo.css()


def test_without_motion_the_dust_is_the_same_but_still():
    _geo, mo, defs, body = make_dust(motion=False)
    assert "class=" not in body and mo.css() == ""
    assert body.count("<use ") > 20 and body.count('mask="url(#') == 6


def test_same_seed_same_dust_and_another_seed_another_dust():
    assert make_dust()[2:] == make_dust()[2:]
    assert make_dust(seed="ada")[2] != make_dust(seed="babbage")[2]


def test_arms_beyond_the_third_reuse_the_particle_tiles_of_the_first_three():
    _geo, _mo, defs, body = make_dust(cuts=(196.0,) * 6)
    assert len(re.findall(r'<g id="t\d+">', defs)) == 9          # three variants of three layers
    assert body.count('class="flow"') == 18                     # and still three flowing layers per arm
    assert set(re.findall(r'<use href="#(t\d+)"', body)) == set(re.findall(r'<g id="(t\d+)">', defs))


def test_arms_sharing_a_tile_never_flow_in_step():
    _geo, _mo, _defs, body = make_dust(cuts=(196.0,) * 6)
    delays = re.findall(r'class="flow" style="animation-delay:(-?[\d.]+)s', body)
    assert len(delays) == 18 and len(set(delays)) == 18


@pytest.mark.parametrize("arms", [7, 9, 12, 18])
def test_many_arms_flow_in_fewer_layers_so_the_animated_groups_stay_bounded(arms):
    _geo, _mo, _defs, body = make_dust(cuts=(196.0,) * arms)
    assert arms <= body.count('class="flow"') <= 18


def drawn_particles(arms):
    """How many particles the flowing layers put on screen: each tile's count times its copies."""
    _geo, _mo, defs, body = make_dust(cuts=(196.0,) * arms)
    per_tile = {tile: content.count("h.01") for tile, content in re.findall(
        r'<g id="(t\d+)">(.*?)</g>(?=<g id="t\d+">|<radialGradient|<mask|$)', defs)}
    # a bright particle is written once and drawn through five layers; count it once
    return sum(per_tile[tile] for tile in re.findall(r'<use href="#(t\d+)"', body))


def test_with_few_arms_every_arm_has_the_full_amount_of_dust():
    assert drawn_particles(2) == pytest.approx(2 * drawn_particles(1), rel=0.1)
    assert drawn_particles(4) == pytest.approx(4 * drawn_particles(1), rel=0.1)


@pytest.mark.parametrize("arms", [6, 9, 12, 18])
def test_with_many_arms_the_dust_thins_so_the_galaxy_never_gets_heavier(arms):
    assert drawn_particles(arms) <= 1.1 * drawn_particles(4)
    assert drawn_particles(arms) >= 0.6 * drawn_particles(4)


def test_layers_of_the_same_reach_share_one_mask():
    _geo, _mo, defs, body = make_dust(cuts=(196.0,) * 6)
    assert defs.count("<mask ") == 3 and body.count('mask="url(#') == 18


def test_bright_particles_of_one_size_share_their_bloom_layers_whatever_their_colour():
    _geo, _mo, defs, _body = make_dust(cuts=(196.0,))
    tiles = re.findall(r'<g id="t\d+">.*?(?=<g id="t\d+">|<radialGradient)', defs)
    assert len(tiles) == 3
    for tile in tiles:
        colours = set(re.findall(r'stroke="(#[0-9a-f]{6})"', tile))
        assert len(colours) == 3
        assert 0 < tile.count("<use ") <= 10                    # five layers for each of the two bright sizes


def test_large_particles_stay_on_the_axis_of_the_arm():
    geo = Geometry(False, 2)
    tile = galaxy._tile(geo, 4000, 1.0, SKY, random.Random("ada"))
    start = TURNS * 2 * math.pi - PHI
    small = sorted({width for (_c, width, _o, _b) in tile})[:2]
    strays = 0
    for (_colour, width, _opacity, _bloom), points in tile.items():
        for x, y in points:
            s = (math.atan2(y, x) - start) % (2 * math.pi)
            off_axis = abs(math.hypot(x, y) / (R0 * math.exp(geo.b * (start + s))) - 1)
            if off_axis > galaxy.OFF_AXIS + 1e-6:
                strays += 1
                assert width in small, f"a {width}px particle sits {off_axis:.0%} off the arm"
    assert strays > 100          # the test must actually have seen off-axis particles


# ── repository stars ─────────────────────────────────────────────────────────

from dataclasses import replace
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
    positions = place_stars(model, geo, "galaxy-dev")
    assert set(positions) == set(model.order)
    assert all(0 <= x <= geo.width and 0 <= y <= geo.height for x, y in positions.values())


def test_stars_on_an_arm_sit_on_its_curve_further_out_the_newer_they_are():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, "galaxy-dev")
    for index, arm in enumerate(model.arms):
        radii = [distance(positions[r.key], (geo.cx, geo.cy)) for r in arm.repos]
        assert radii == sorted(radii)
        for r, radius in zip(arm.repos, radii):
            assert distance(positions[r.key], geo.point(index, radius)) < 0.01


def test_stars_on_an_arm_are_evenly_spaced_from_the_core_to_the_arms_end():
    day = date(2020, 1, 1)
    arm = Arm("Backend", tuple(repo(f"r{i}", day + timedelta(days=30 * i)) for i in range(5)))
    model = GalaxyModel(arms=(arm,), loose=(), labels=frozenset(), order=tuple(r.key for r in arm.repos))
    geo = Geometry(False, 1)
    positions = place_stars(model, geo, "x")
    radii = [distance(positions[r.key], (geo.cx, geo.cy)) for r in arm.repos]
    inner, outer = 196 * 0.26, 196 * 0.95
    assert radii == pytest.approx([inner + (outer - inner) * (q + 0.5) / 5 for q in range(5)], abs=0.01)


def test_stars_on_an_arm_stay_between_the_core_and_the_arms_cut():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, "galaxy-dev")
    for arm, cut in zip(model.arms, arm_cuts(model, geo)):
        for r in arm.repos:
            assert geo.radius * 0.26 <= distance(positions[r.key], (geo.cx, geo.cy)) <= cut * 0.95 + 0.01


def crowd_of_loose_stars(count=30):
    day = date(2020, 1, 1)
    loose = tuple(repo(f"loose-{i:02d}", day + timedelta(days=i)) for i in range(count))
    return GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=loose, labels=frozenset(),
                       order=tuple(r.key for r in loose))


@pytest.mark.parametrize("seed", ["ada", "babbage", "galaxy-dev"])
def test_loose_stars_keep_their_distance_from_every_other_star(seed):
    model = crowd_of_loose_stars()
    spots = list(place_stars(model, Geometry(False, 2), seed).values())
    assert len(spots) == 30
    closest = min(distance(a, b) for i, a in enumerate(spots) for b in spots[i + 1:])
    assert closest >= 14          # thirty stars in the band: without retries some pair always ends up closer


def test_a_loose_star_stays_where_it_is_when_the_galaxy_around_it_changes():
    """Its place comes from its own name, not from how many random numbers were drawn before it."""
    few, many = crowd_of_loose_stars(3), crowd_of_loose_stars(9)
    geo = Geometry(False, 2)
    before, after = place_stars(few, geo, "ada"), place_stars(many, geo, "ada")
    assert all(before[key] == after[key] for key in before)
    assert place_stars(few, geo, "ada") != place_stars(few, geo, "babbage")
    # and a repository joining an arm does not shake the loose ones either
    arm = Arm(None, (repo("on-the-arm", date(2019, 1, 1)), repo("also-on-the-arm", date(2019, 2, 1))))
    with_arm = replace(few, arms=(arm, Arm(None, ())), order=tuple(r.key for r in arm.repos) + few.order)
    joined = place_stars(with_arm, geo, "ada")
    assert all(before[key] == joined[key] for key in before)


def test_thinning_the_dust_does_not_move_a_single_star():
    model = demo_model()

    def star_spots(keep):
        svg = galaxy._compose(model, PROFILE, SKY, False, False, "galaxy-dev", keep)
        return re.findall(r'<g transform="translate\(([\d.]+ [\d.]+)\)"><g><circle', svg)

    assert len(star_spots(1.0)) == 15 and star_spots(1.0) == star_spots(0.4)


def test_forty_repositories_on_one_arm_are_all_drawn_inside_its_cut():
    day = date(2020, 1, 1)
    arm = Arm("Backend", tuple(repo(f"r{i:02d}", day + timedelta(days=30 * i)) for i in range(40)))
    model = GalaxyModel(arms=(arm,), loose=(), labels=frozenset(), order=tuple(r.key for r in arm.repos))
    geo = Geometry(False, 1)
    positions = place_stars(model, geo, "x")
    assert len(positions) == 40
    assert max(distance(p, (geo.cx, geo.cy)) for p in positions.values()) <= 196 * 0.95 + 0.01
    assert all(0 <= x <= geo.width and 0 <= y <= geo.height for x, y in positions.values())


def test_empty_galaxy_has_no_stars():
    model = GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=())
    assert place_stars(model, Geometry(False, 2), "x") == {}


def test_same_seed_same_sky():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    assert place_stars(model, geo, "s") == place_stars(model, geo, "s")
    assert place_stars(model, geo, "s") != place_stars(model, geo, "t")


# ── labels and arm names ─────────────────────────────────────────────────────

from generator.plates.galaxy import arm_name_paths, place_labels
from generator.typeset import measure


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def labels_for(positions, stars, names=None, mobile=False):
    geo = Geometry(mobile, 2)
    return geo, place_labels(names or list(positions), positions, stars, geo)


def test_label_goes_to_the_right_of_its_star_when_nothing_is_in_the_way():
    _geo, placed = labels_for({"engine": (500, 200)}, {"engine": 10})
    x, baseline, anchor, _box = placed["engine"]
    assert anchor == "start" and x > 500 and baseline == pytest.approx(204.5)


def test_label_near_the_right_edge_goes_to_the_left():
    geo, placed = labels_for({"galaxy-profile": (830, 200)}, {"galaxy-profile": 480})
    x, _baseline, anchor, box = placed["galaxy-profile"]
    assert anchor == "end" and x < 830
    assert box[0] >= 0 and box[0] + box[2] <= geo.width


def test_label_avoids_a_neighbouring_star():
    _geo, placed = labels_for({"alpha-centauri": (500, 200), "b": (540, 201)}, {"alpha-centauri": 5, "b": 1},
                              names=["alpha-centauri"])
    _x, baseline, anchor, box = placed["alpha-centauri"]
    assert not (box[0] <= 540 <= box[0] + box[2] and box[1] <= 201 <= box[1] + box[3])
    assert anchor == "end" or baseline != pytest.approx(204.5)


def test_labels_do_not_overlap_each_other():
    positions = {"alpha": (500, 200), "beta": (506, 212), "gamma": (498, 188), "delta": (510, 204)}
    _geo, placed = labels_for(positions, {name: 3 for name in positions})
    boxes = [box for _x, _y, _a, box in placed.values()]
    assert not any(overlap(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


@pytest.mark.parametrize("mobile", [False, True])
def test_every_label_box_stays_inside_the_frame(mobile):
    model = demo_model()
    geo = Geometry(mobile, len(model.arms))
    positions = place_stars(model, geo, "galaxy-dev")
    stars = {r.key: r.stars for arm in model.arms for r in arm.repos}
    stars.update({r.key: r.stars for r in model.loose})
    placed = place_labels(sorted(model.labels), positions, stars, geo)
    assert set(placed) == set(model.labels)
    for _x, _y, _anchor, (left, top, width, height) in placed.values():
        assert left >= 0 and top >= 0 and left + width <= geo.width and top + height <= geo.height


def test_a_label_in_a_corner_is_pushed_back_into_the_frame():
    geo, placed = labels_for({"corner-case": (845, 6)}, {"corner-case": 2})
    left, top, width, height = placed["corner-case"][3]
    assert left >= 0 and top >= 0 and left + width <= geo.width and top + height <= geo.height


def test_an_endless_repository_name_is_cut_in_the_label():
    _geo, placed = labels_for({"x" * 90: (500, 200)}, {"x" * 90: 2})
    box = placed["x" * 90][3]
    assert measure("x" * 90, 13.5, "medium") > 400                 # the whole name would be this wide
    assert 150 <= box[2] - 8 <= 170                               # what is written fills the limit and stops there


def test_each_named_arm_gets_a_path_for_its_name_and_unnamed_arms_get_none():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    paths = arm_name_paths(model, geo)
    assert [name for name, _points in paths] == ["Frontend", "Backend", "DevOps"]
    unnamed = GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=())
    assert arm_name_paths(unnamed, Geometry(False, 2)) == []


def test_arm_name_paths_read_left_to_right_run_just_outside_the_arm_and_are_long_enough():
    model = demo_model()
    geo = Geometry(False, len(model.arms))
    cuts = arm_cuts(model, geo)
    for (name, points), cut in zip(arm_name_paths(model, geo), cuts):
        assert points[0][0] < points[-1][0]
        middle = points[len(points) // 2]
        assert cut * 0.6 < distance(middle, (geo.cx, geo.cy)) < cut * 1.25
        length = sum(distance(a, b) for a, b in zip(points, points[1:]))
        assert length >= measure(name, 13.5, "italic") + 16
        assert all(0 <= x <= geo.width and 0 <= y <= geo.height for x, y in points)


# ── the whole plate ──────────────────────────────────────────────────────────

import xml.etree.ElementTree as ET

from tests.contract import rules
from tests.svgread import text_runs, texts

PROFILE = {"name": "Nyx Orion", "tagline": "Full Stack Developer & Open Source Explorer",
           "philosophy": '"The best code is the code that empowers others."'}
EMPTY = GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=())


def plate(model=None, profile=PROFILE, mobile=False, motion=True, seed="galaxy-dev", theme=SKY):
    return galaxy.render(model or demo_model(), profile, theme, mobile=mobile, motion=motion, seed=seed)


def star_count(svg):
    lit = len(re.findall(r'<circle r="[\d.]+" fill="url\(#c[ny]\)"/>', svg))
    dormant = len(re.findall(r'<circle r="[\d.]+" fill="none" stroke="#[0-9a-f]{6}" stroke-opacity=".8"/>', svg))
    return lit + dormant


def animated(svg):
    return sum(1 for element in ET.fromstring(svg).iter() if "class" in element.attrib)


def test_plate_sizes():
    assert rules.viewbox(plate()) == (850, 430)
    assert rules.viewbox(plate(mobile=True)) == (390, 478)


def test_one_star_per_repository():
    assert star_count(plate()) == 15
    assert star_count(plate(mobile=True)) == 15


def test_featured_and_brightest_repositories_are_named():
    names = texts(plate())
    assert "nebula-ui" in names and "stargate-api" in names
    assert plate().count('filter="url(#lb)"') == 2


def test_arm_names_are_set_along_their_curves():
    curved = len(re.findall(r'<use href="#i[0-9a-f]+" transform="translate', plate()))
    assert curved == len("Frontend") + len("Backend") + len("DevOps")


def test_identity_is_never_animated():
    svg = plate()
    runs = [run for run in text_runs(svg) if run["text"] in ("NyxOrion",)]
    assert runs and runs[0]["size"] == pytest.approx(48)
    # name, tagline and philosophy are the only straight lines in the light and italic styles
    lines = re.findall(r'<g transform="translate\([\d. ]+\) scale\([\d.]+\)"([^>]*)><use href="#[li]', svg)
    assert len(lines) == 3
    assert all("class" not in attributes and "style" not in attributes for attributes in lines)


def test_a_long_name_shrinks_to_fit_beside_the_galaxy_and_is_cut_if_it_must():
    long = dict(PROFILE, name="Maximiliana Wolfeschlegelsteinhausenbergerdorff the Third of Somewhere")
    run = next(r for r in text_runs(plate(profile=long)) if r["text"].startswith("Maximiliana"))
    assert run["size"] < 48 and run["x"] + run["width"] <= 630 - 196 - 10
    assert run["text"].endswith("…")


def test_mobile_shows_name_and_tagline_only():
    names = texts(plate(mobile=True))
    assert "NyxOrion" in names and not any(t.startswith("“The") or t.startswith('"The') for t in names)


def test_missing_tagline_and_philosophy_leave_no_empty_lines():
    svg = plate(profile={"name": "Nyx Orion", "tagline": "", "philosophy": ""})
    assert "<g transform" in svg and 'scale(.02)" fill' not in svg
    ET.fromstring(svg)


def test_entrance_actors_are_the_only_motion_only_elements_and_vanish_without_motion():
    moving, still = plate(), plate(motion=False)
    marked = re.findall(r'class="([^"]*\bmo\b[^"]*)"', moving)
    assert marked == ["leave mo"]
    assert "leave" not in still and moving.count("h.01") > still.count("h.01")


def test_empty_profile_is_a_galaxy_of_dust_with_no_star_and_no_label():
    svg = plate(model=EMPTY)
    ET.fromstring(svg)
    assert star_count(svg) == 0 and 'filter="url(#lb)"' not in svg
    assert "No public repositories yet" in svg


def test_description_tells_what_the_galaxy_holds():
    svg = plate()
    assert ">Galaxy of Nyx Orion</title>" in svg
    assert "15 repositories" in svg and "Frontend 5" in svg and "nebula-ui" in svg


def test_same_profile_same_galaxy_and_another_login_another_galaxy():
    assert plate() == plate()
    assert plate(seed="ada") != plate(seed="babbage")


def big_model(stars=48, arms=6):
    """Every star slot taken, across many focus areas, with every brightness and state."""
    day = date(2019, 1, 1)
    repos = [Repo(name=f"repo-{i:02d}", owner="ada", stars=int(1.22 ** i), created=day + timedelta(days=40 * i),
                  pushed=date(2026, 9, 20) - timedelta(days=(i % 5) * 110), description="", primary_language="Python",
                  languages={"Python": 1}, topics=(), is_fork=False) for i in range(stars)]
    per = stars // arms
    built = tuple(Arm(f"Area {a}", tuple(repos[a * per:(a + 1) * per])) for a in range(arms))
    return GalaxyModel(arms=built, loose=(), labels=frozenset(r.key for r in repos[-4:]),
                       order=tuple(r.key for r in repos), today=date(2026, 9, 30))


@pytest.mark.parametrize("arms", [3, 6, 12])
@pytest.mark.parametrize("mobile", [False, True])
@pytest.mark.parametrize("theme", [SKY, get_theme("cyanotype", "light")], ids=["deep-sky", "cyanotype-light"])
def test_a_crowded_galaxy_still_respects_the_contract(mobile, arms, theme):
    long = {"name": "Maximiliana Wolfeschlegelsteinhausen", "tagline": "Staff Engineer, Platform & Developer Experience",
            "philosophy": "Every slot is taken, every arm is full, and the page still has to hold sixty frames."}
    svg = plate(model=big_model(arms=arms), profile=long, mobile=mobile, theme=theme)
    assert star_count(svg) == 48
    rules.within_budget(svg, 110_000, 100)
    rules.rest_state_is_complete(svg)
    rules.no_forbidden_techniques(svg)
    rules.motion_is_guarded(svg)
    rules.placements_are_inside(svg)
    rules.svg_is_sound(svg)


def wordy_model():
    """The crowded galaxy again, with names that use as many different letters as they can."""
    base = big_model(arms=6)
    areas = ("Quartz & Jam", "Vex-Blowfish", "Czech Dwarf", "Glyph/Myth", "Sphinx: Judo", "Waltz (BKQ)")
    names = {"repo-47": "JACKDAWS_love.my", "repo-46": "big-SPHINX-of-qtz", "repo-45": "Zephyr.Vow-Quick", "repo-44": "0123456789-xyz"}
    arms = tuple(Arm(area, tuple(replace(r, name=names.get(r.name, r.name)) for r in arm.repos))
                 for area, arm in zip(areas, base.arms))
    renamed_repos = [r for arm in arms for r in arm.repos]
    return GalaxyModel(arms=arms, loose=(), labels=frozenset(r.key for r in renamed_repos if r.name in names.values()),
                       order=tuple(r.key for r in sorted(renamed_repos, key=lambda r: r.created)), today=base.today)


WORDY = {"name": "Žofie Ångström-Queißer", "tagline": "Jived fox nymph grabs quick waltz; BLOWZY & VEXED?",
         "philosophy": "“Sphinx of black quartz, judge my vow” — 0123456789 (WALTZ, BAD NYMPH, FOR QUICK JIGS VEX!)"}


@pytest.mark.parametrize("mobile", [False, True])
def test_the_header_fits_its_budget_even_when_the_text_uses_every_letter(mobile):
    svg = plate(model=wordy_model(), profile=WORDY, mobile=mobile)
    assert len(re.findall(r'<path id="[lrmi][0-9a-f]+" ', svg)) > (60 if mobile else 100)   # the text really is heavy
    assert star_count(svg) == 48
    rules.within_budget(svg, 110_000, 100)
    rules.svg_is_sound(svg)


def test_a_header_over_budget_sheds_dust_never_stars_or_text():
    heavy, light = plate(model=wordy_model(), profile=WORDY), plate(model=big_model(arms=6), profile=WORDY)
    assert star_count(heavy) == 48
    assert {"ŽofieÅngström-Queißer", "JACKDAWS_love.my", "big-SPHINX-of-qtz", "Zephyr.Vow-Quick"} <= set(texts(heavy))
    assert 0 < heavy.count("h.01") < light.count("h.01")


def test_a_stars_state_is_judged_against_the_day_of_the_snapshot():
    pushed = date(2026, 8, 1)
    one = Repo(name="solo", owner="ada", stars=3, created=date(2024, 1, 1), pushed=pushed, description="",
               primary_language="Python", languages={"Python": 1}, topics=(), is_fork=False)

    def model_on(today):
        return GalaxyModel(arms=(Arm("Backend", (one,)),), loose=(), labels=frozenset(), order=("ada/solo",), today=today)

    assert "url(#hn)" in plate(model=model_on(pushed + timedelta(days=5)))
    assert "url(#hn)" not in plate(model=model_on(pushed + timedelta(days=60)))
    assert "url(#hy)" in plate(model=model_on(pushed + timedelta(days=60)))


def test_the_galaxy_model_carries_the_snapshots_day():
    assert demo_model().today == date(2026, 9, 30)


def test_entrance_actors_share_one_set_of_keyframes():
    css = re.search(r"<style>(.*?)</style>", plate()).group(1)
    assert css.count("@keyframes act{") == 1 and len(re.findall(r"@keyframes a\d", css)) == 0
    starts = re.findall(r'class="act" style="([^"]*)"', plate())
    assert len(starts) == 14 and len(set(starts)) == 14          # each group comes in from its own angle


def test_entrance_actors_are_plain_dots_without_bloom():
    moving, still = plate(), plate(motion=False)
    assert moving.count("<use ") == still.count("<use ")          # the actors add no <use> at all


def test_particle_paths_inherit_their_stroke_attributes_from_one_group():
    svg = plate()
    particle_paths = re.findall(r'<path d="M[^"]*h\.01[^"]*"[^>]*>', svg)
    assert len(particle_paths) > 50
    assert not any("stroke-linecap" in p or 'fill="none"' in p for p in particle_paths)
    rules.no_forbidden_techniques(svg)


def test_a_label_keeps_off_whatever_is_already_written_there():
    geo = Geometry(False, 2)
    free = place_labels(["engine"], {"engine": (500, 200)}, {"engine": 10}, geo)["engine"]
    blocked = place_labels(["engine"], {"engine": (500, 200)}, {"engine": 10}, geo, obstacles=[free[3]])["engine"]
    assert not overlap(blocked[3], free[3])


def test_star_names_never_cover_an_arms_name():
    for mobile in (False, True):
        svg = plate(mobile=mobile)
        chips = [tuple(float(v) for v in m) for m in re.findall(
            r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" rx="8"', svg)]
        letters = [(float(x), float(y)) for x, y in re.findall(
            r'<use href="#i[0-9a-f]+" transform="translate\(([\d.]+) ([\d.]+)\)', svg)]
        assert chips and letters
        assert not any(left <= x <= left + w and top <= y <= top + h
                       for left, top, w, h in chips for x, y in letters)


def renamed(model, name):
    return replace(model, arms=tuple(Arm(name, arm.repos) for arm in model.arms))


@pytest.mark.parametrize("arms", [2, 6])
@pytest.mark.parametrize("mobile", [False, True])
def test_an_endless_arm_name_is_cut_and_stays_inside_the_plate(mobile, arms):
    svg = plate(model=renamed(big_model(arms=arms), "Distributed Systems, Observability & Platform " * 2), mobile=mobile)
    rules.placements_are_inside(svg)
    assert svg.count('<use href="#i2026" transform="translate') == arms        # each name ends in an ellipsis
    letters = len(re.findall(r'<use href="#i[0-9a-f]+" transform="translate', svg))
    assert letters < 40 * arms


@pytest.mark.parametrize("arms", [2, 6])
@pytest.mark.parametrize("mobile", [False, True])
def test_an_arm_name_outside_the_font_is_kept_short_and_inside_the_plate(mobile, arms):
    svg = plate(model=renamed(big_model(arms=arms), "フロントエンドとデザインシステムの研究開発"), mobile=mobile)
    rules.text_stays_inside(svg)
    names = [e for e in ET.fromstring(svg).iter() if e.tag.endswith("text")]
    assert len(names) == arms and all(e.text.endswith("…") and len(e.text) <= 9 for e in names)


def test_an_arm_name_of_ordinary_length_is_whole():
    svg = plate(model=renamed(big_model(arms=2), "Web, Cloud & Infrastructure"))
    assert "#i2026" not in svg


@pytest.mark.parametrize("name", ["\U0001F3A8 Frontend", "Học máy", "Ελληνικά", "データ基盤"])
def test_an_arm_name_outside_the_font_does_not_paint_over_the_galaxy(name):
    for mobile in (False, True):
        svg = plate(model=renamed(big_model(arms=3), name), mobile=mobile)
        rules.text_strokes_are_thin(svg)
        widths = [float(e.attrib["stroke-width"]) for e in ET.fromstring(svg).iter() if e.tag.endswith("text")]
        assert widths == [3.5, 3.5, 3.5]


def test_a_featured_upstream_and_the_users_own_repository_of_the_same_name_are_two_different_stars():
    own = Repo(name="linux", owner="ada", stars=0, created=date(2020, 1, 1), pushed=date(2022, 1, 1), description="",
               primary_language="C", languages={"C": 1}, topics=(), is_fork=False)
    upstream = replace(own, owner="torvalds", stars=150000, created=date(2011, 1, 1), pushed=date(2026, 9, 29))
    model = GalaxyModel(arms=(Arm("Systems", (upstream, own)),), loose=(), labels=frozenset({"torvalds/linux"}),
                        order=("torvalds/linux", "ada/linux"), today=date(2026, 9, 30))
    svg = plate(model=model)
    spots = re.findall(r'<g transform="translate\(([\d.]+ [\d.]+)\)"><g[^>]*><circle', svg)
    assert len(spots) == 2 and len(set(spots)) == 2               # two stars, in two places
    assert star_count(svg) == 2
    assert len(re.findall(r'fill="url\(#cn\)"', svg)) == 1        # the upstream one, pushed yesterday, is lit
    assert len(re.findall(r'stroke-opacity=".8"/>', svg)) == 1     # the old one is a dormant ring
    assert texts(svg).count("linux") == 1                          # and only the featured one is named


def test_a_label_moved_back_into_the_frame_never_lands_on_its_own_star():
    """A wide name beside a star at the right edge. Moved back into the frame at the star's own height it
    would cover the star; with the nearer lines taken, it goes three lines up instead."""
    geo = Geometry(True, 2)
    name, star_at = "data-structures-and-algorithms-in-rust", (380, 240)
    taken = [(150, 0, 55, 478),          # something written all the way down, to the left
             (206, 208, 184, 21),        # the two lines above the star's
             (206, 252, 184, 60)]        # and everything below it
    _x, _baseline, _anchor, (left, top, width, height) = place_labels(
        [name], {name: star_at}, {name: 0}, geo, obstacles=taken)[name]
    assert not any(left < x + w and x < left + width and top < y + h and y < top + height for x, y, w, h in taken)
    assert not (left - 3 < star_at[0] < left + width + 3 and top - 3 < star_at[1] < top + height + 3)



# ── the entrance, star by star ───────────────────────────────────────────────

def entrance(svg):
    """(x y, delay) of every star that ignites on its own, in document order."""
    return [(spot, float(delay)) for spot, delay in re.findall(
        r'<g transform="translate\(([\d.]+ [\d.]+)\)"><g class="pop" style="animation-delay:([\d.]+)s">', svg)]


def test_stars_ignite_in_the_order_their_repositories_were_created():
    model = demo_model()
    svg = plate(model=model)
    geo = Geometry(False, len(model.arms))
    positions = place_stars(model, geo, "galaxy-dev")
    seen = entrance(svg)
    assert [spot for spot, _delay in seen] == [f"{num(positions[key][0])} {num(positions[key][1])}" for key in model.order]
    delays = [delay for _spot, delay in seen]
    assert delays == sorted(delays) and delays[0] == pytest.approx(4.5) and delays[-1] == pytest.approx(6.4)
    assert len(set(delays)) == 15                                 # one by one, not all at once


def test_a_stars_name_appears_a_moment_after_the_star():
    model = demo_model()
    svg = plate(model=model)
    positions = place_stars(model, Geometry(False, len(model.arms)), "galaxy-dev")
    ignites = dict(entrance(svg))
    names = re.findall(r'<g class="soft" style="animation-delay:([\d.]+)s"><rect [^>]*filter="url\(#lb\)"/>'
                       r'<g transform="translate\(([-\d.]+) ([-\d.]+)\)', svg)
    assert len(names) == 2
    for key, (delay, _x, _y) in zip(sorted(model.labels, key=lambda k: -max(
            r.stars for arm in model.arms for r in arm.repos if r.key == k)), names):
        x, y = positions[key]
        assert float(delay) == pytest.approx(ignites[f"{num(x)} {num(y)}"] + 0.35, abs=0.011)


def test_the_core_ignites_before_the_galaxy_arrives():
    svg = plate()
    assert re.search(r'<circle class="ignite" r="98" fill="url\(#cg\)"/>', svg)
    css = re.search(r"<style>(.*?)</style>", svg).group(1)
    assert ".ignite{animation:ignite 1.9s ease-out 2.52s both}" in css
    assert ".arrive{animation:arrive 1.2s ease-out 3.7s both}" in css


def test_only_named_stars_and_the_eight_brightest_active_ones_have_a_breathing_halo():
    model = big_model(arms=6)                                     # 48 stars, 10 of them pushed this month
    svg = plate(model=model)
    breathing = len(re.findall(r'<circle r="[\d.]+" fill="url\(#hn\)" class="tw"', svg))
    active = len(re.findall(r'fill="url\(#hn\)"', svg))
    named_and_active = sum(1 for arm in model.arms for r in arm.repos
                           if r.key in model.labels and (date(2026, 9, 30) - r.pushed).days <= 30)
    assert active == 10 and 0 < breathing <= 8 + named_and_active < active + 1
    assert breathing == min(active, 8 + named_and_active) or breathing == 8


@pytest.mark.parametrize("profile", [
    {"name": "\x7f"}, {"name": "Nyx", "tagline": "\x00\x1f"}, {"name": "Nyx", "philosophy": "\x7f \x01"},
    {"name": "   "}, {"name": 42, "tagline": None, "philosophy": ["a", "list"]},
])
def test_identity_text_that_is_empty_once_cleaned_draws_nothing_and_breaks_nothing(profile):
    for mobile in (False, True):
        svg = plate(profile=profile, mobile=mobile)
        ET.fromstring(svg)
        rules.svg_is_sound(svg)
