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


# ── README.md and what ships with it ─────────────────────────────────────────

def test_the_project_readme_previews_every_plate_with_the_same_picture_blocks():
    blocks = pictures((ROOT / "README.md").read_text(encoding="utf-8"))
    assert [fallback for _sources, fallback in blocks] == [f"{stem}.svg" for stem in build.RENDERERS]
    for sources, fallback in blocks:
        stem = fallback[:-len(".svg")]
        assert [name for _media, name in sources] == [f"{stem}-mobile-light.svg", f"{stem}-mobile.svg",
                                                      f"{stem}-light.svg"]


def test_every_file_the_readmes_point_at_exists_in_the_repository():
    for readme in ("README.md", "README.profile.md"):
        text = (ROOT / readme).read_text(encoding="utf-8")
        for path in set(re.findall(r'(?:src|srcset)="\./([^"]+)"', text)) | set(re.findall(r"\]\(([\w./-]+\.\w+)\)", text)):
            assert (ROOT / path).exists(), f"{readme} points at {path}"


def test_the_preview_images_are_what_the_demo_mode_draws_today():
    """`make demo` refreshes them. A fork that has its own config.yml shows its own profile instead."""
    if (ROOT / "config.yml").exists():
        return
    config = validate_config(example())
    for name, svg in build.render_all(config, load_demo()).items():
        path = ROOT / "assets" / "generated" / name
        assert path.exists(), f"{name} is missing: run `make demo`"
        assert path.read_text(encoding="utf-8") == svg, f"{name} is stale: run `make demo`"
    assert {p.name for p in (ROOT / "assets" / "generated").glob("*.svg")} == FILES


def test_the_version_is_two():
    import generator
    assert generator.__version__ == "2.0.0"
    assert "## 2.0.0" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def test_the_readme_describes_the_modules_that_exist():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    tree = text[text.index("## Architecture"):]
    for module in re.findall(r"[├└]── (\w+\.py)", tree):
        assert list((ROOT / "generator").rglob(module)), f"README lists {module}, which is not there"
    for path in sorted((ROOT / "generator").glob("*.py")) + sorted((ROOT / "generator" / "plates").glob("*.py")):
        if path.name not in ("__init__.py", "tech_catalog.py"):
            assert path.name in tree, f"{path.name} is missing from the README's architecture"
