"""The contributions plate: a year of weekly totals as a light curve."""

import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import pytest

from generator.plates import contributions
from generator.plates.contributions import moving_average, reference_levels, smooth_path
from generator.themes import get_theme
from tests.contract import rules
from tests.svgread import text_runs, texts

SKY = get_theme("deep-sky", "dark")
COUNTERS = {"stars": 530, "prs": 37, "issues": 12, "repos": 17}
METRICS = ["commits", "stars", "prs", "issues", "repos"]
FIRST = date(2025, 9, 28)


def series(values, total=None):
    """The shape model.weekly_series returns: values, first days, total, index of the peak."""
    days = [FIRST + timedelta(weeks=i) for i in range(len(values))]
    return list(values), days, sum(values) if total is None else total, values.index(max(values))


def year(peak_at=30, peak=482):
    values = [20 + (i * 37) % 90 for i in range(53)]
    values[peak_at] = peak
    return series(values, total=7005)


def plate(data="year", counters=COUNTERS, metrics=METRICS, mobile=False, motion=True, theme=SKY):
    return contributions.render(year() if data == "year" else data, counters, metrics, theme, mobile=mobile, motion=motion)


def stars_drawn(svg):
    return len(re.findall(r'fill="url\(#c[ny]\)"', svg))


# ── the helpers ──────────────────────────────────────────────────────────────

def test_moving_average_is_centred_and_shrinks_its_window_at_the_edges():
    assert moving_average([10, 20, 30, 40, 50, 60, 70]) == [20, 25, 30, 40, 50, 55, 60]


def test_moving_average_of_a_single_week_is_that_week():
    assert moving_average([7]) == [7]


@pytest.mark.parametrize("peak, levels", [(482, [200, 400]), (90, [25, 50]), (3, []), (4, [1, 2]), (7, [2, 4]),
                                          (12, [5, 10]), (1200, [500, 1000])])
def test_reference_levels_are_round_numbers_well_inside_the_chart(peak, levels):
    assert reference_levels(peak) == levels


def test_reference_levels_are_whole_contributions():
    for peak in range(4, 3000, 7):
        assert all(isinstance(level, int) and 0 < level <= peak for level in reference_levels(peak))


def test_smooth_path_goes_through_every_point():
    d = smooth_path([(0, 10), (10, 30), (20, 5), (30, 5)])
    assert d.startswith("M0 10C") and d.count("C") == 3
    ends = [tuple(float(v) for v in segment.split()[-2:]) for segment in d.split("C")[1:]]
    assert ends == [(10, 30), (20, 5), (30, 5)]


def test_smooth_path_of_a_flat_series_is_a_flat_line():
    numbers = re.findall(r"-?[\d.]+", smooth_path([(x, 50) for x in range(0, 50, 10)]))
    assert set(numbers[1::2]) == {"50"}


# ── size ─────────────────────────────────────────────────────────────────────

def test_plate_sizes_with_and_without_a_calendar():
    assert rules.viewbox(plate()) == (850, 254)
    assert rules.viewbox(plate(mobile=True)) == (390, 266)
    assert rules.viewbox(plate(data=None)) == (850, 120)
    assert rules.viewbox(plate(data=None, mobile=True)) == (390, 110)


# ── the title and the numbers ────────────────────────────────────────────────

def test_title_is_the_total_with_a_thousands_separator():
    runs = texts(plate())
    assert "7,005" in runs and "contributionsinthelastyear" in runs


def test_the_caption_starts_right_after_the_total_however_long_it_is():
    for total in (5, 7005, 1234567):
        runs = {run["text"]: run for run in text_runs(plate(data=series([1, 2, 3, 4, 5] * 10, total=total)))}
        number = runs[f"{total:,}"]
        assert runs["contributionsinthelastyear"]["x"] == pytest.approx(number["x"] + number["width"] + 10, abs=0.2)


def test_up_to_three_numbers_in_config_order_and_never_commits():
    runs = texts(plate())
    assert {"530", "stars", "37", "pullrequests", "12", "issues"} <= set(runs)
    assert "17" not in runs and "repositories" not in runs and "commits" not in runs


def test_numbers_follow_the_order_of_the_config():
    runs = {run["text"]: run for run in text_runs(plate(metrics=["repos", "stars"]))}
    assert runs["repositories"]["x"] + runs["repositories"]["width"] < runs["stars"]["x"] + runs["stars"]["width"]
    assert "pullrequests" not in runs


def test_a_count_of_one_is_singular():
    runs = texts(plate(counters={"stars": 1, "prs": 1, "issues": 1, "repos": 1}, metrics=["stars", "prs", "repos"]))
    assert {"star", "pullrequest", "repository"} <= set(runs) and "stars" not in runs


def test_a_number_the_data_does_not_have_is_left_out():
    runs = texts(plate(counters={"stars": 9, "prs": None, "repos": 4}, metrics=["stars", "prs", "issues", "repos"]))
    assert "pullrequests" not in runs and "issues" not in runs and {"9", "4", "repositories"} <= set(runs)


def test_big_numbers_are_grouped_and_never_run_into_the_title():
    huge = {"stars": 1234567, "prs": 2345678, "issues": 3456789, "repos": 100}
    for mobile in (False, True):
        svg = plate(data=series([5] * 53, total=1234567890), counters=huge, mobile=mobile)
        rules.text_stays_inside(svg)
        runs = text_runs(svg)
        shown = [run["text"] for run in runs]
        assert "contributionsinthelastyear" in shown          # the total shrinks before its caption is cut
        assert "1,234,567" in shown
        caption = next(run for run in runs if run["text"] == "contributionsinthelastyear")
        for run in runs:
            if run is caption or run["text"] == "1,234,567,890":
                continue
            same_band = abs(run["y"] - caption["y"]) < 14
            assert not (same_band and run["x"] < caption["x"] + caption["width"] + 8
                        and caption["x"] < run["x"] + run["width"]), f"'{run['text']}' runs into the title"


def test_on_desktop_a_number_that_would_reach_the_title_is_left_out_last_one_first():
    huge = {"stars": 1234567, "prs": 2345678, "issues": 3456789}
    shown = texts(plate(data=series([5] * 53, total=1234567890), counters=huge))
    assert "1,234,567" in shown and "2,345,678" in shown and "3,456,789" not in shown
    assert {"1,234,567", "2,345,678", "3,456,789"} <= set(texts(plate(data=series([5] * 53, total=70), counters=huge)))


def test_a_commits_counter_in_the_data_is_still_not_listed():
    shown = texts(plate(counters=dict(COUNTERS, commits=999), metrics=["commits", "stars"]))
    assert "999" not in shown and "530" in shown


# ── the curve ────────────────────────────────────────────────────────────────

def test_one_point_per_week_except_the_peak_which_is_a_star():
    svg = plate()
    assert len(re.findall(r'<circle[^>]* r="2"', svg)) == 52
    assert stars_drawn(svg) == 1


def test_the_curve_is_written_once_and_reused_for_glow_line_and_travelling_light():
    svg = plate()
    assert svg.count('<path id="cv"') == 1
    assert svg.count('<use href="#cv"') == 2 + 5                 # glow and line, then the five layers of the light
    assert plate(motion=False).count('<use href="#cv"') == 2


def test_the_peak_label_names_the_week():
    peak_day = FIRST + timedelta(weeks=30)
    assert f"482intheweekof{contributions.MONTHS[peak_day.month - 1]}{peak_day.day}" in texts(plate())


def test_the_peak_label_sits_left_of_the_peak_when_there_is_room():
    svg = plate()
    label = next(run for run in text_runs(svg) if run["text"].startswith("482inthe"))
    peak_x = 44 + (850 - 88) * 30 / 52
    assert label["x"] + label["width"] < peak_x


@pytest.mark.parametrize("mobile", [False, True])
@pytest.mark.parametrize("peak_at", [0, 1, 26, 51, 52])
def test_the_peak_label_stays_inside_the_plate_wherever_the_peak_is(mobile, peak_at):
    svg = plate(data=year(peak_at=peak_at), mobile=mobile)
    width = 390 if mobile else 850
    label = next(run for run in text_runs(svg) if run["text"].startswith("482inthe"))
    assert label["x"] >= 0 and label["x"] + label["width"] <= width
    rules.text_stays_inside(svg)
    rules.placements_are_inside(svg)


def test_a_peak_in_the_first_week_puts_its_label_to_the_right():
    label = next(run for run in text_runs(plate(data=year(peak_at=0))) if run["text"].startswith("482inthe"))
    assert label["x"] > 44


def test_reference_lines_are_labelled_at_the_left():
    runs = {run["text"]: run for run in text_runs(plate())}
    assert runs["200aweek"]["x"] == 44 and runs["400aweek"]["x"] == 44
    assert runs["400aweek"]["y"] < runs["200aweek"]["y"]


def test_months_are_marked_with_three_letters_on_desktop_and_one_on_mobile():
    assert {"Oct", "Jan", "Sep"} <= set(texts(plate()))
    mobile = texts(plate(mobile=True))
    assert "Oct" not in mobile and {"O", "J", "S"} <= set(mobile)


def test_every_change_of_month_is_marked_once_and_the_first_week_is_not():
    months = [text for text in texts(plate()) if text in contributions.MONTHS]
    assert len(months) == 12 and months[0] == "Oct" and months[-1] == "Sep"


def test_an_empty_year_is_a_flat_line_with_no_peak():
    for mobile in (False, True):
        svg = plate(data=series([0] * 53), mobile=mobile)
        ET.fromstring(svg)
        assert stars_drawn(svg) == 0
        assert not any("intheweekof" in text for text in texts(svg))
        assert "0" in texts(svg) and not any("aweek" in text for text in texts(svg))
        assert len(re.findall(r'<circle[^>]* r="[\d.]+"', svg)) == 53


def test_a_calendar_of_one_week_does_not_break():
    svg = plate(data=series([9]))
    ET.fromstring(svg)
    rules.placements_are_inside(svg)


def test_nothing_is_drawn_above_the_chart_or_below_its_baseline():
    svg = plate()
    ys = [float(y) for y in re.findall(r'<circle cx="[\d.]+" cy="([\d.]+)" r="2"', svg)]
    assert len(ys) == 52 and min(ys) >= 100 and max(ys) <= 254 - 42


# ── without a calendar ───────────────────────────────────────────────────────

def test_without_a_calendar_only_the_numbers_are_shown():
    for mobile in (False, True):
        svg = plate(data=None, mobile=mobile)
        runs = texts(svg)
        assert {"530", "stars", "37", "pullrequests", "12", "issues"} <= set(runs)
        assert "contributionsinthelastyear" not in runs and "<circle" not in svg
        rules.text_stays_inside(svg)


def test_without_a_calendar_and_without_numbers_the_plate_says_so():
    svg = plate(data=None, counters={}, metrics=["commits"])
    assert texts(svg) == ["Nocontributiondatayet"]


# ── motion ───────────────────────────────────────────────────────────────────

def test_weeks_rise_left_to_right_then_the_curve_draws_and_the_peak_ignites():
    svg = plate()
    rises = [float(v) for v in re.findall(r'class="rise" style="animation-delay:([\d.]+)s', svg)]
    assert len(rises) == 51 and rises == sorted(rises)           # the first week has no delay to write
    assert re.search(r'<use href="#cv"[^>]*class="ldraw" style="animation-delay:.45s"', svg)
    assert re.search(r'class="pop" style="animation-delay:.86s"', svg)      # week 30: 30 * .022 + .2


def test_a_light_runs_along_the_curve_every_twelve_seconds():
    assert plate().count("--cy:12s;--st:3.4s") == 5


def test_without_motion_the_plate_is_complete_and_still():
    svg = plate(motion=False)
    rules.no_motion_at_all(svg)
    assert texts(svg) == texts(plate()) and stars_drawn(svg) == 1


def test_the_contract_holds_in_every_theme():
    for palette in ("deep-sky", "cyanotype"):
        for mode in ("dark", "light"):
            for mobile in (False, True):
                svg = plate(theme=get_theme(palette, mode), mobile=mobile)
                rules.rest_state_is_complete(svg)
                rules.no_forbidden_techniques(svg)
                rules.motion_is_guarded(svg)
                rules.text_stays_inside(svg)
                rules.placements_are_inside(svg)
                rules.within_budget(svg, 48_000, 80)
                rules.svg_is_sound(svg)
                rules.is_accessible(svg)


def test_description_tells_the_numbers():
    svg = plate()
    assert "7,005 contributions in the last year" in svg and "482 in the week of" in svg


def test_same_input_same_bytes():
    assert plate() == plate() and plate(mobile=True) == plate(mobile=True)
