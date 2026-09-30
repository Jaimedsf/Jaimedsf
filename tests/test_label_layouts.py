"""Star names against everything else written on the galaxy, over many random profiles.

A single fixture cannot tell whether names collide: that depends on where the
stars fall. So these tests draw a few hundred galaxies with seeded random
repositories and count the layouts where a star's name runs into another
name, into the identity column or into a focus area's name.
"""

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
    """{(arms, width, kind): layouts with that collision} over TRIALS random galaxies per number of arms."""
    rng, found = random.Random(99), Counter()
    for arm_count in (2, 3, 4, 5, 6):
        for trial in range(TRIALS):
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
    assert total(collisions, "label over identity") == 0


def test_star_names_never_run_into_each_other(collisions):
    assert total(collisions, "label over label") == 0                 # of 400 layouts


def test_with_up_to_three_arms_star_names_keep_off_the_arm_names(collisions):
    assert total(collisions, "label over arm name", arms=(2, 3)) == 0       # of 160 layouts


def test_with_many_arms_star_names_rarely_cross_an_arm_name(collisions):
    assert total(collisions, "label over arm name", arms=(4, 5, 6)) <= 8    # of 240 layouts; 5 when written


def test_a_star_name_is_always_drawn_over_an_arm_name_never_under_it():
    """Where they do meet, the star's name stays whole: arm names are drawn first."""
    svg = galaxy.render(random_model(random.Random(5), 6), PROFILE, SKY, motion=False, seed="s")
    first_label = svg.index('filter="url(#lb)"')
    last_arm_letter = max(match.start() for match in re.finditer(r'<use href="#i[0-9a-f]+" transform="translate', svg))
    assert last_arm_letter < first_label
