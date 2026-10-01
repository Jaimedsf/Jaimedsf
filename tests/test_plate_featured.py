"""The featured-projects plate."""

import re
import xml.etree.ElementTree as ET
from datetime import date

import pytest

from generator.model import Featured
from generator.plates import VARIANTS, featured
from generator.themes import get_theme
from tests.svgread import text_runs, texts

SKY = get_theme("deep-sky", "dark")


def item(name="tabAla", stars=4, language="TypeScript", description="Save tabs. Organise them into collections.",
         pushed=date(2026, 9, 26), state="now"):
    return Featured(name=name, description=description, language=language, stars=stars, pushed=pushed, state=state)


TWO = [item(), item("gaeia", 0, "Python", "Autonomous AI study group", date(2026, 2, 21), "year")]


def viewbox(svg):
    return tuple(int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())


# ── size ─────────────────────────────────────────────────────────────────────

def test_desktop_plate_is_850_by_214():
    assert viewbox(featured.render(TWO, SKY)) == (850, 214)


def test_mobile_plate_grows_with_the_number_of_projects():
    assert viewbox(featured.render(TWO, SKY, mobile=True)) == (390, 26 + 142 * 2)
    assert viewbox(featured.render(TWO[:1], SKY, mobile=True)) == (390, 26 + 142)


def test_four_variants_are_declared():
    assert VARIANTS == [("", "dark", False), ("-light", "light", False),
                        ("-mobile", "dark", True), ("-mobile-light", "light", True)]


# ── content ──────────────────────────────────────────────────────────────────

def test_projects_are_lettered_in_the_order_given():
    runs = {run["text"]: run for run in text_runs(featured.render(TWO, SKY))}
    assert runs["α"]["x"] < runs["β"]["x"]
    assert runs["tabAla"]["x"] < runs["gaeia"]["x"]


def test_data_line_lists_language_stars_and_month_of_last_push():
    assert "TypeScript,4stars,updatedSep2026" in texts(featured.render(TWO, SKY))


def test_zero_stars_are_not_mentioned():
    assert "Python,updatedFeb2026" in texts(featured.render(TWO, SKY))


def test_one_star_is_singular():
    assert "Go,1star,updatedSep2026" in texts(featured.render([item("x", 1, "Go")], SKY))


def test_missing_language_leaves_no_stray_comma():
    assert "4stars,updatedSep2026" in texts(featured.render([item(language=None)], SKY))


def test_description_is_part_of_the_plate():
    assert "Savetabs.Organisethemintocollections." in texts(featured.render(TWO, SKY))


def test_accessible_description_summarises_every_project():
    svg = featured.render(TWO, SKY)
    assert "tabAla: TypeScript, 4 stars, updated Sep 2026" in svg
    assert "gaeia: Python, updated Feb 2026" in svg


# ── text that does not fit ───────────────────────────────────────────────────

LONG_NAME = "an-extremely-long-repository-name-that-nobody-should-ever-pick"
LONG_DESC = ("A component library with cosmic design tokens and dark-first theming, " * 5).strip()


@pytest.mark.parametrize("mobile", [False, True])
def test_long_name_and_description_stay_inside_their_column(mobile):
    items = [item(LONG_NAME, 9, description=LONG_DESC), item("b", 5), item("c", 1)]
    svg = featured.render(items, SKY, mobile=mobile)
    width = 390 if mobile else 850
    margin = 24 if mobile else 44
    column = width - 2 * margin if mobile else (width - 2 * margin) / 3
    first = [run for run in text_runs(svg) if run["text"].startswith(("an-extremely", "Acomponent"))]
    assert first, "the long texts were not found"
    for run in first:
        assert run["x"] + run["width"] <= margin + column + 0.5, run["text"]
    assert any(run["text"].endswith("…") for run in first)


def test_description_wraps_to_at_most_two_lines():
    svg = featured.render([item(description=LONG_DESC)], SKY)
    assert len([t for t in texts(svg) if t.startswith(("Acomponent", "cosmic", "and", "theming", "design", "library"))]) <= 2


# ── edge cases ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mobile", [False, True])
def test_no_projects_renders_a_sentence(mobile):
    svg = featured.render([], SKY, mobile=mobile)
    assert "Nofeaturedprojectsyet" in texts(svg)
    assert viewbox(svg)[1] == 110


def test_text_outside_the_font_falls_back_without_breaking_the_svg():
    svg = featured.render([item("日本語", description='R&D <lab> "quoted"')], SKY)
    assert "<text" in svg
    ET.fromstring(svg)


@pytest.mark.parametrize("mobile", [False, True])
def test_output_is_well_formed_xml(mobile):
    ET.fromstring(featured.render(TWO, SKY, mobile=mobile))


def test_same_input_same_bytes():
    assert featured.render(TWO, SKY) == featured.render(TWO, SKY)


# ── motion ───────────────────────────────────────────────────────────────────

def test_motion_is_on_by_default_and_guarded():
    svg = featured.render(TWO, SKY)
    assert "@media (prefers-reduced-motion: no-preference)" in svg
    assert 'class="comet mo"' in svg and 'class="pop"' in svg


def test_without_motion_there_is_nothing_animated():
    svg = featured.render(TWO, SKY, motion=False)
    assert "<style" not in svg and "class=" not in svg and "animation" not in svg


def test_light_theme_draws_in_ink_on_paper():
    light = get_theme("deep-sky", "light")
    svg = featured.render(TWO, light)
    assert f'fill="{light.bg}"' in svg and f'fill="{light.ink}"' in svg


# ── review fixes ─────────────────────────────────────────────────────────────

from generator.svg import spike_half


def three(language="Jupyter Notebook", stars=1240):
    return [item("nebula-ui", stars, language), item("stargate-api", 486, language), item("orbit-cli", 212, "Go")]


def test_data_line_never_runs_into_the_next_column():
    svg = featured.render(three(), SKY)
    column = (850 - 2 * 44) / 3
    lines = [run for run in text_runs(svg) if run["text"].startswith("JupyterNotebook")]
    assert len(lines) == 2
    for run in lines:
        start = 44 + round((run["x"] - 44) / column) * column
        assert run["x"] + run["width"] <= start + column - 24 + 0.5, run["text"]


def test_data_line_shortens_before_it_cuts():
    assert any(text.startswith("JupyterNotebook,1240stars") and not text.endswith("…")
               for text in texts(featured.render(three(), SKY)))


def test_letter_stands_clear_of_a_bright_stars_spikes():
    svg = featured.render(three(), SKY)
    alpha = next(run for run in text_runs(svg) if run["text"] == "α")
    assert alpha["x"] >= 44 + 14 + spike_half(1240) + 4


@pytest.mark.parametrize("mobile", [False, True])
def test_a_very_bright_star_stays_inside_the_plate_and_off_the_text(mobile):
    svg = featured.render([item("huge", 250_000), item("b", 3)], SKY, mobile=mobile)
    gx, gy = (float(v) for v in re.search(r'<g transform="translate\(([\d.]+) ([\d.]+)\)"><g class="pop"', svg).groups())
    reach = max(float(v) for v in re.findall(r'd="M-([\d.]+) 0Q0', svg))
    assert gx - reach >= 0 and gy - reach >= 0
    name = next(run for run in text_runs(svg) if run["text"] == "huge")
    if mobile:
        assert gx + reach <= name["x"]
    else:
        assert gy + reach <= name["y"] - name["size"] * 0.72
