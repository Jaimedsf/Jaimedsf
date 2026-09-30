"""build.render_all: every plate in every variant, themed and switched by the config."""

import copy

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
