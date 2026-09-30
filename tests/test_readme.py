"""What the repository tells its users: the example config, the profile README template, the project README."""

import re
from pathlib import Path

import yaml

from generator import build
from generator.config import validate_config
from generator.data import load_demo
from generator.plates import VARIANTS

ROOT = Path(__file__).resolve().parent.parent
FILES = {f"{stem}{suffix}.svg" for stem in build.RENDERERS for suffix, _mode, _mobile in VARIANTS}
PICTURE = re.compile(r"<picture>(.*?)</picture>", re.S)


def pictures(markdown):
    """[(sources as (media, file), the file of the fallback <img>)] for every <picture> block."""
    found = []
    for block in PICTURE.findall(markdown):
        sources = re.findall(r'<source media="([^"]+)" srcset="\./assets/generated/([^"]+)"', block)
        fallback = re.search(r'<img src="\./assets/generated/([^"]+)"', block)
        found.append((sources, fallback.group(1) if fallback else None))
    return found


# ── config.example.yml ───────────────────────────────────────────────────────

def example():
    return yaml.safe_load((ROOT / "config.example.yml").read_text(encoding="utf-8"))


def test_the_example_config_shows_the_new_keys_at_their_defaults():
    raw = example()
    assert raw["theme"] == {"dark": "deep-sky", "light": "deep-sky"}
    assert raw["motion"] is True
    assert all("color" not in arm for arm in raw["galaxy_arms"])


def test_the_example_config_mentions_every_optional_key_even_if_commented_out():
    text = (ROOT / "config.example.yml").read_text(encoding="utf-8")
    for key in ("repos:", "cyanotype", "void:", "text_bright:", "synapse_cyan:", "arm:"):
        assert key in text, key


def test_the_example_config_draws_exactly_what_the_version_one_example_drew():
    """The nine colours it used to carry were the defaults, so dropping them changes nothing."""
    old = yaml.safe_load((ROOT / "tests" / "fixtures" / "config_v1.yml").read_text(encoding="utf-8"))
    assert build.render_all(validate_config(example()), load_demo()) == \
        build.render_all(validate_config(old), load_demo())


# ── README.profile.md ────────────────────────────────────────────────────────

def test_the_profile_readme_has_one_picture_per_plate_in_the_order_of_the_build():
    blocks = pictures((ROOT / "README.profile.md").read_text(encoding="utf-8"))
    assert [fallback for _sources, fallback in blocks] == [f"{stem}.svg" for stem in build.RENDERERS]


def test_each_picture_offers_mobile_light_mobile_and_light_before_the_default():
    for sources, fallback in pictures((ROOT / "README.profile.md").read_text(encoding="utf-8")):
        stem = fallback[:-len(".svg")]
        assert sources == [
            ("(max-width: 600px) and (prefers-color-scheme: light)", f"{stem}-mobile-light.svg"),
            ("(max-width: 600px)", f"{stem}-mobile.svg"),
            ("(prefers-color-scheme: light)", f"{stem}-light.svg"),
        ]


def test_every_image_the_profile_readme_points_at_is_one_the_generator_writes():
    text = (ROOT / "README.profile.md").read_text(encoding="utf-8")
    named = set(re.findall(r"\./assets/generated/([\w.-]+\.svg)", text))
    assert named == FILES


def test_every_picture_describes_its_plate_for_who_cannot_see_it():
    text = (ROOT / "README.profile.md").read_text(encoding="utf-8")
    alts = re.findall(r'<img src="\./assets/generated/[^"]+" width="850" alt="([^"]+)"', text)
    assert len(alts) == 4 and len(set(alts)) == 4 and all(len(alt) > 12 for alt in alts)
