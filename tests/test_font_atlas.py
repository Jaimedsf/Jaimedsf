"""The committed font atlases: coverage, metrics and outline format."""

import json
import re
from pathlib import Path

import pytest

FONTS = Path(__file__).resolve().parent.parent / "generator" / "fonts"
STYLES = ["light", "regular", "medium", "italic"]


def load(style):
    return json.loads((FONTS / f"spectral-{style}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("style", STYLES)
def test_atlas_covers_latin_text_with_accents_and_punctuation(style):
    atlas = load(style)
    sample = "Vinícius Melo — AI Engineer, 7,005 “quoted” Ærø ž…"
    assert [c for c in sample if c not in atlas["glyphs"]] == []


def test_italic_atlas_carries_greek_letters_for_the_bayer_designations():
    glyphs = load("italic")["glyphs"]
    assert [c for c in "αβγδε" if c not in glyphs] == []


@pytest.mark.parametrize("style", STYLES)
def test_atlas_declares_metrics(style):
    atlas = load(style)
    assert atlas["upm"] == 1000
    assert atlas["ascent"] > 0 and atlas["descent"] > 0
    assert atlas["style"] == style


def test_wide_letter_advances_more_than_narrow_one():
    glyphs = load("regular")["glyphs"]
    assert glyphs["m"][0] > glyphs["i"][0] > 0


def test_av_pair_is_kerned_tighter():
    assert load("regular")["kern"]["AV"] < 0


def test_space_has_an_advance_and_no_outline():
    adv, d = load("regular")["glyphs"][" "]
    assert adv > 0 and d == ""


@pytest.mark.parametrize("style", STYLES)
def test_outlines_are_compact_integers(style):
    for char, (_adv, d) in load(style)["glyphs"].items():
        assert "," not in d, char
        assert re.search(r"\d\.\d", d) is None, char


def test_outlines_are_flipped_for_svg_so_capitals_rise_above_the_baseline():
    # In SVG y grows downward: a capital sitting on the baseline has negative y coordinates.
    _adv, d = load("regular")["glyphs"]["H"]
    ys = []
    for command, args in re.findall(r"([MLHVQCZ])([^MLHVQCZ]*)", d):
        numbers = [int(v) for v in re.findall(r"-?\d+", args)]
        if command == "V":
            ys += numbers
        elif command != "H":
            ys += numbers[1::2]
    assert min(ys) < -500 and max(ys) <= 20
