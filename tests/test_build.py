"""build.render_all: every plate in every variant, themed and switched by the config."""

import copy
import re

import pytest
import yaml

from generator import build
from generator.config import validate_config
from generator.data import load_demo
from generator.themes import get_theme


@pytest.fixture
def config():
    with open("config.example.yml", encoding="utf-8") as handle:
        return validate_config(yaml.safe_load(handle))


def test_every_plate_comes_in_four_variants(config):
    files = build.render_all(config, load_demo())
    for stem in build.RENDERERS:
        for suffix in ("", "-light", "-mobile", "-mobile-light"):
            assert f"{stem}{suffix}.svg" in files
    assert len(files) == 4 * len(build.RENDERERS)


def test_the_four_plates_of_the_readme_in_its_order():
    assert list(build.RENDERERS) == ["galaxy-header", "stats-card", "tech-stack", "projects-constellation"]


def test_each_plate_draws_its_own_data(config):
    files = build.render_all(config, load_demo())
    assert "contributions in the last year" in files["stats-card.svg"]
    assert "Declared stack:" in files["tech-stack.svg"]
    assert "Galaxy of " in files["galaxy-header.svg"]


def test_languages_follow_the_configs_exclusions_and_limit(config):
    cfg = copy.deepcopy(config)
    first = build.render_all(cfg, load_demo())["tech-stack.svg"]
    top = re.search(r"<desc[^>]*>([A-Za-z+#]+) ", first).group(1)
    cfg["languages"]["exclude"] = cfg["languages"]["exclude"] + [top]
    cfg["languages"]["max_display"] = 2
    second = build.render_all(cfg, load_demo())["tech-stack.svg"]
    listed = re.search(r"<desc[^>]*>(.*?)\. Declared", second).group(1)
    assert top not in listed and listed.count("%") == 2


def test_without_a_calendar_the_contributions_plate_is_the_short_one(config):
    from dataclasses import replace
    snap = replace(load_demo(), weeks=None, total_contributions=None)
    assert 'viewBox="0 0 850 120"' in build.render_all(config, snap)["stats-card.svg"]


def test_the_unsuffixed_file_is_the_dark_desktop_variant(config):
    svg = build.render_all(config, load_demo())["projects-constellation.svg"]
    assert 'viewBox="0 0 850 ' in svg and get_theme("deep-sky", "dark", config["themes"]["overrides"]).bg in svg


def test_dark_and_light_palettes_are_chosen_independently(config):
    cfg = copy.deepcopy(config)
    cfg["themes"] = {"dark": "cyanotype", "light": "deep-sky", "overrides": {}}
    files = build.render_all(cfg, load_demo())
    assert get_theme("cyanotype", "dark").bg in files["projects-constellation.svg"]
    assert get_theme("deep-sky", "light").bg in files["projects-constellation-light.svg"]


def test_motion_flag_reaches_every_file(config):
    cfg = copy.deepcopy(config)
    cfg["motion"] = False
    assert all("<style" not in svg for svg in build.render_all(cfg, load_demo()).values())
