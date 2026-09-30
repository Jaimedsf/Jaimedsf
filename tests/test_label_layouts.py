"""Star names against everything else written on the galaxy, over many random profiles.

A single fixture cannot tell whether names collide: that depends on where the
stars fall. So these tests draw a few hundred galaxies with seeded random
repositories and count the layouts where a star's name runs into another
name, into the identity column or into a focus area's name.
"""

import math
import random
import re
from collections import Counter
from datetime import date, timedelta

import pytest

from generator.data import Repo
from generator.model import Arm, GalaxyModel
from generator.plates import galaxy
from generator.themes import get_theme
from tests.svgread import text_runs

SKY = get_theme("deep-sky", "dark")
TODAY = date(2026, 9, 30)
PROFILE = {"name": "Nyx Orion", "tagline": "Full Stack Developer & Open Source Explorer",
           "philosophy": '"The best code is the code that empowers others."'}
NAMES = ["awesome-kubernetes-operators", "dotfiles", "advent-of-code-2025", "galaxy-profile",
         "react-native-starter-kit", "ml-from-scratch", "blog", "competitive-programming", "terraform-aws-modules",
         "rust-raytracer", "my-portfolio-website", "data-structures-and-algorithms", "cli-tool", "neovim-config",
         "spring-boot-microservices", "leetcode-solutions"]
AREAS = ["Frontend", "Backend", "DevOps", "Machine Learning", "Mobile", "Data Engineering"]
TRIALS = 40
SEEDS = (99, 107)                 # two unrelated streams, so the numbers below are not fitted to one


def random_model(rng, arm_count):
    pool = rng.sample(NAMES, len(NAMES)) + [f"repo-{i}" for i in range(60)]
    day, arms, used = date(2019, 1, 1), [], 0
    for a in range(arm_count):
        count = rng.randint(1, 7)
        arms.append(Arm(AREAS[a], tuple(
            Repo(name=pool[used + q], owner="ada", stars=int(1.35 ** rng.randint(0, 25)),
                 created=day + timedelta(days=30 * (used + q)), pushed=TODAY - timedelta(days=rng.choice((0, 100, 500))),
                 description="", primary_language="Python", languages={"Python": 1}, topics=(), is_fork=False)
            for q in range(count))))
        used += count
    everyone = [r for arm in arms for r in arm.repos]
    named = {r.key for r in rng.sample(everyone, min(3, len(everyone)))} | {max(everyone, key=lambda r: r.stars).key}
    return GalaxyModel(arms=tuple(arms), loose=(), labels=frozenset(named),
                       order=tuple(r.key for r in sorted(everyone, key=lambda r: r.created)), today=TODAY)


def box(run):
    """The ink of a line of text: from a little under the x-height line to the baseline."""
    return run["x"], run["y"] - run["size"] * 0.7, run["width"], run["size"] * 0.95


def overlap(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def arm_letters(svg):
    return [(float(x), float(y)) for x, y in re.findall(
        r'<use href="#i[0-9a-f]+" transform="translate\(([\d.]+) ([\d.]+)\)', svg)]


@pytest.fixture(scope="module")
def collisions():
    """{(arms, width, kind): layouts with that collision}, over TRIALS random galaxies per seed and number of arms."""
    found = Counter()
    for rng, arm_count, trial in ((rng, arm_count, trial) for rng in map(random.Random, SEEDS)
                                  for arm_count in (2, 3, 4, 5, 6) for trial in range(TRIALS)):
        if True:
            model = random_model(rng, arm_count)
            for mobile in (False, True):
                svg = galaxy.render(model, PROFILE, SKY, mobile=mobile, motion=False, seed=f"s{trial}")
                runs = text_runs(svg)
                labels = [box(run) for run in runs if run["style"] == "medium"]
                identity = [box(run) for run in runs if run["style"] in ("light", "italic")]
                width = "mobile" if mobile else "desktop"
                assert len(labels) == len(model.labels)                    # every name is written, always
                if any(overlap(a, b) for i, a in enumerate(labels) for b in labels[i + 1:]):
                    found[(arm_count, width, "label over label")] += 1
                if any(overlap(a, b) for a in labels for b in identity):
                    found[(arm_count, width, "label over identity")] += 1
                if any(b[0] - 2 <= x <= b[0] + b[2] + 2 and b[1] - 3 <= y <= b[1] + b[3] + 3
                       for b in labels for x, y in arm_letters(svg)):
                    found[(arm_count, width, "label over arm name")] += 1
    return found


def total(collisions, kind, arms=(2, 3, 4, 5, 6)):
    return sum(count for (arm_count, _width, k), count in collisions.items() if k == kind and arm_count in arms)


def test_star_names_never_run_into_the_name_tagline_or_philosophy(collisions):
    assert total(collisions, "label over identity") == 0                    # of 800 layouts


def test_star_names_never_run_into_each_other(collisions):
    assert total(collisions, "label over label") == 0


def test_with_up_to_three_arms_star_names_keep_off_the_arm_names(collisions):
    assert total(collisions, "label over arm name", arms=(2, 3)) == 0       # of 320 layouts


def test_with_many_arms_star_names_hardly_ever_cross_an_arm_name(collisions):
    """Over twenty other seeds this was 3 layouts in 4,800; a name that does cross is drawn on top, whole."""
    assert total(collisions, "label over arm name", arms=(4, 5, 6)) <= 2    # of 480 layouts


# ── the hard case: four named stars side by side ─────────────────────────────

def cluster(rng, mobile):
    """Four named stars within some 60 pixels of each other, with long names, somewhere in the galaxy."""
    geo = galaxy.Geometry(mobile, 3)
    angle, radius = rng.uniform(0, 2 * math.pi), rng.uniform(0.2, 0.95) * geo.radius
    cx, cy = geo.cx + radius * math.cos(angle), geo.cy + radius * math.sin(angle)
    names, positions = rng.sample(NAMES, 4), {}
    for name in names:
        while True:
            spot = (cx + rng.uniform(-45, 45), cy + rng.uniform(-45, 45))
            if all(math.hypot(spot[0] - x, spot[1] - y) >= 14 for x, y in positions.values()):
                positions[name] = spot
                break
    stars = {name: int(1.35 ** rng.randint(0, 25)) for name in names}
    identity = [] if mobile else [(44, 155, 390, 55), (45, 211, 380, 23), (45, 262, 320, 17), (45, 281, 320, 17)]
    boxes = [placed[3] for placed in galaxy.place_labels(names, positions, stars, geo, identity).values()]
    return geo, boxes, identity


@pytest.mark.parametrize("mobile", [False, True])
def test_four_named_neighbours_with_long_names_each_find_a_place_of_their_own(mobile):
    rng = random.Random(5)
    for _ in range(600):
        geo, boxes, identity = cluster(rng, mobile)
        assert len(boxes) == 4
        assert not any(overlap(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])
        assert not any(overlap(a, b) for a in boxes for b in identity)
        assert all(b[0] >= 0 and b[1] >= 0 and b[0] + b[2] <= geo.width and b[1] + b[3] <= geo.height for b in boxes)


def test_a_star_name_is_always_drawn_over_an_arm_name_never_under_it():
    """Where they do meet, the star's name stays whole: arm names are drawn first."""
    svg = galaxy.render(random_model(random.Random(5), 6), PROFILE, SKY, motion=False, seed="s")
    first_label = svg.index('filter="url(#lb)"')
    first_star = re.search(r'<circle r="[\d.]+" fill="(?:url\(#h[ny]\)|#[0-9a-f]{6}" fill-opacity=".09")', svg).start()
    last_arm_letter = max(match.start() for match in re.finditer(r'<use href="#i[0-9a-f]+" transform="translate', svg))
    assert last_arm_letter < first_star < first_label            # arm names, then stars, then the stars' names
