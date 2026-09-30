"""Palettes: two of them, each in a dark and a light mode, plus the legacy colour overrides."""

import pytest

from generator.themes import get_theme, mix

TOKENS = {
    ("deep-sky", "dark"): ("#0b1020", "#eef1f6", "#9fbcff"),
    ("deep-sky", "light"): ("#f6f7f9", "#151a24", "#2447b3"),
    ("cyanotype", "dark"): ("#11305a", "#f5f2e9", "#ffb454"),
    ("cyanotype", "light"): ("#f1f4f9", "#11305a", "#c9560b"),
}


@pytest.mark.parametrize("key", TOKENS)
def test_background_ink_and_active_colour(key):
    theme = get_theme(*key)
    assert (theme.bg, theme.ink, theme.now) == TOKENS[key]


@pytest.mark.parametrize("key", TOKENS)
def test_secondary_text_and_rules_are_the_ink_thinned_over_the_background(key):
    theme = get_theme(*key)
    assert theme.mute == mix(theme.ink, theme.bg, 0.64)
    assert theme.faint == mix(theme.ink, theme.bg, 0.22)


@pytest.mark.parametrize("key", TOKENS)
def test_spectrum_ramp_has_eight_steps_and_dust_weights_add_up(key):
    theme = get_theme(*key)
    assert len(theme.ramp) == 8
    assert sum(weight for _colour, weight in theme.dust) == pytest.approx(1.0)


def test_cyanotype_is_two_inks_so_neutral_and_dormant_stars_use_the_ink():
    theme = get_theme("cyanotype", "dark")
    assert theme.year == theme.dorm == theme.ink
    assert theme.ramp[0] == theme.ink


def test_deep_sky_dark_uses_star_colours():
    theme = get_theme("deep-sky", "dark")
    assert (theme.year, theme.dorm) == ("#fff3dc", "#e0946a")


def test_dark_flag_follows_the_mode():
    assert get_theme("deep-sky", "dark").dark is True
    assert get_theme("deep-sky", "light").dark is False


def test_label_backdrop_is_a_darkened_sky_in_dark_mode_and_the_paper_in_light_mode():
    dark, light = get_theme("deep-sky", "dark"), get_theme("deep-sky", "light")
    assert dark.chip == (mix("#000000", dark.bg, 0.3), 0.5)
    assert light.chip == (light.bg, 0.8)


def test_unknown_palette_or_mode_is_an_error():
    with pytest.raises(ValueError):
        get_theme("neon", "dark")
    with pytest.raises(ValueError):
        get_theme("deep-sky", "sepia")


# ── legacy hex overrides (the nine colours of the old config) ────────────────

def test_legacy_background_and_text_colours_map_onto_the_dark_theme():
    theme = get_theme("deep-sky", "dark", {"void": "#000000", "text_bright": "#ffffff",
                                           "text_dim": "#aaaaaa", "text_faint": "#333333"})
    assert (theme.bg, theme.ink, theme.mute, theme.faint) == ("#000000", "#ffffff", "#aaaaaa", "#333333")


def test_overriding_only_the_background_rederives_secondary_colours_and_backdrop():
    theme = get_theme("deep-sky", "dark", {"void": "#000000"})
    assert theme.mute == mix(theme.ink, "#000000", 0.64)
    assert theme.chip[0] == "#000000"


def test_legacy_accents_map_onto_active_dormant_and_dust():
    theme = get_theme("deep-sky", "dark", {"synapse_cyan": "#00ffff", "dendrite_violet": "#aa00ff",
                                           "axon_amber": "#ffaa00"})
    assert theme.now == "#00ffff" and theme.dorm == "#ffaa00"
    assert [colour for colour, _w in theme.dust] == ["#00ffff", "#aa00ff", "#ffaa00"]


def test_legacy_card_colours_are_accepted_and_do_nothing():
    assert get_theme("deep-sky", "dark", {"nebula": "#123456", "star_dust": "#654321"}) == get_theme("deep-sky", "dark")


def test_legacy_overrides_do_not_touch_the_light_theme():
    assert get_theme("deep-sky", "light", {"void": "#000000", "synapse_cyan": "#00ffff"}) == get_theme("deep-sky", "light")


# ── mix ──────────────────────────────────────────────────────────────────────

def test_mix_returns_the_endpoints_and_a_midpoint():
    assert mix("#ffffff", "#000000", 1) == "#ffffff"
    assert mix("#ffffff", "#000000", 0) == "#000000"
    assert mix("#ffffff", "#000000", 0.5) == "#808080"


def test_overriding_the_ink_of_a_two_ink_palette_carries_through_everything_made_of_ink():
    theme = get_theme("cyanotype", "dark", {"text_bright": "#ffffff"})
    assert theme.year == theme.dorm == theme.haze == "#ffffff"
    assert theme.ramp[0] == "#ffffff" and theme.dust[0][0] == "#ffffff"


def test_overriding_the_background_of_a_two_ink_palette_rebuilds_its_ramp():
    theme = get_theme("cyanotype", "dark", {"void": "#000000"})
    assert theme.ramp[-1] == mix(theme.ink, "#000000", 0.2)
