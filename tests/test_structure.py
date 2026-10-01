"""The shape of the code after the Atlas redesign: the old generator is gone, and an old config still works."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from generator import build
from generator.config import validate_config
from generator.data import load_demo

ROOT = Path(__file__).resolve().parent.parent
RETIRED = ("utils", "svg_builder", "github_api", "templates")


def test_the_old_generator_is_not_in_the_package():
    for name in RETIRED:
        assert not (ROOT / "generator" / f"{name}.py").exists(), name
        assert not (ROOT / "generator" / name).exists(), name


def test_nothing_imports_the_old_generator():
    names = "|".join(RETIRED)
    pattern = re.compile(rf"generator\.(?:{names})\b|from generator import [^\n]*\b(?:{names})\b")
    for folder in ("generator", "tools", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.name == "test_structure.py":
                continue
            assert not pattern.search(path.read_text(encoding="utf-8")), path.relative_to(ROOT)


def test_a_config_written_for_version_one_still_validates_and_draws_everything():
    """tests/fixtures/config_v1.yml is the example config as it shipped before the redesign."""
    raw = yaml.safe_load((ROOT / "tests" / "fixtures" / "config_v1.yml").read_text(encoding="utf-8"))
    assert "color" in raw["galaxy_arms"][0] and len(raw["theme"]) == 9      # it really is the old shape
    config = validate_config(raw)
    assert config["themes"] == {"dark": "deep-sky", "light": "deep-sky", "overrides": {}}
    files = build.render_all(config, load_demo())
    assert len(files) == 16
    for svg in files.values():
        ET.fromstring(svg)
