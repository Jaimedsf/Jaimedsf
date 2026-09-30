"""The robustness contract, applied to every plate in every palette, variant and motion setting."""

import copy
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from generator import build
from generator.config import validate_config
from generator.data import load_demo
from generator.plates import VARIANTS
from generator.themes import PALETTES, get_theme
from tests.contract import rules

ROOT = Path(__file__).resolve().parent.parent.parent
DIGESTS = ROOT / "tests" / "golden" / "digests.json"

# file stem -> (bytes, animated elements); spec section 5
BUDGETS = {
    "galaxy-header": (110_000, 100),
    "stats-card": (48_000, 80),
    "tech-stack": (48_000, 80),
    "projects-constellation": (48_000, 80),
}


def demo_config():
    with open(ROOT / "config.example.yml", encoding="utf-8") as handle:
        return validate_config(yaml.safe_load(handle))


CASES = [(stem, palette, suffix, mode, mobile)
         for stem in build.RENDERERS for palette in PALETTES for suffix, mode, mobile in VARIANTS]


def render(stem, palette, mode, mobile, motion=True, config=None, snap=None):
    config = config or demo_config()
    theme = get_theme(palette, mode, config["themes"]["overrides"])
    return build.RENDERERS[stem](snap or load_demo(), config, theme, mobile, motion)


def case_id(case):
    stem, palette, suffix, _mode, _mobile = case
    return f"{stem}{suffix}[{palette}]"


@pytest.fixture(params=CASES, ids=case_id)
def case(request):
    return request.param


@pytest.fixture
def moving(case):
    stem, palette, _suffix, mode, mobile = case
    return render(stem, palette, mode, mobile, motion=True)


@pytest.fixture
def still(case):
    stem, palette, _suffix, mode, mobile = case
    return render(stem, palette, mode, mobile, motion=False)


def test_rest_state_is_complete(moving, still):
    rules.rest_state_is_complete(moving)
    rules.rest_state_is_complete(still)


def test_no_forbidden_techniques(moving):
    rules.no_forbidden_techniques(moving)


def test_motion_is_guarded(moving):
    rules.motion_is_guarded(moving)


def test_motion_off_means_no_motion(still):
    rules.no_motion_at_all(still)


def test_text_stays_inside_the_plate(moving):
    rules.text_stays_inside(moving)


def test_everything_is_placed_inside_the_plate(moving):
    rules.placements_are_inside(moving)


def test_text_outside_the_font_still_stays_inside_the_plate(case):
    stem, palette, _suffix, mode, mobile = case
    config = copy.deepcopy(demo_config())
    config["profile"]["name"] = "銀河を作る人"
    config["profile"]["tagline"] = "オープンソースの探検家 🚀"
    for project in config["projects"]:
        project["description"] = "コズミックなデザイントークンとダークファーストのテーマを備えたコンポーネントライブラリ " * 3
    svg = render(stem, palette, mode, mobile, config=config)
    rules.text_stays_inside(svg)
    rules.placements_are_inside(svg)


def test_same_input_same_bytes(case, moving):
    stem, palette, _suffix, mode, mobile = case
    assert render(stem, palette, mode, mobile) == moving


def test_within_budget(case, moving):
    rules.within_budget(moving, *BUDGETS[case[0]])


def test_svg_is_sound(moving, still):
    rules.svg_is_sound(moving)
    rules.svg_is_sound(still)


def test_is_accessible(moving):
    rules.is_accessible(moving)


def test_xml_special_characters_do_not_break_the_image(case):
    stem, palette, _suffix, mode, mobile = case
    config = copy.deepcopy(demo_config())
    config["profile"]["name"] = 'Nyx & <Orion> "N"'
    config["profile"]["tagline"] = "R&D <lead>"
    for project in config["projects"]:
        project["description"] = 'Fast & <small> "things" 日本語'
    ET.fromstring(render(stem, palette, mode, mobile, config=config))


def test_output_matches_the_recorded_digest(case, moving):
    """T7. A change in output is deliberate: rerun with UPDATE_GOLDEN=1 and review the images."""
    key = case_id(case)
    digest = hashlib.sha256(moving.encode("utf-8")).hexdigest()
    recorded = json.loads(DIGESTS.read_text(encoding="utf-8")) if DIGESTS.exists() else {}
    if os.environ.get("UPDATE_GOLDEN"):
        recorded[key] = digest
        DIGESTS.write_text(json.dumps(recorded, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert recorded.get(key) == digest, f"{key} changed; review it, then run with UPDATE_GOLDEN=1"
