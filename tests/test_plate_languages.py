"""The languages plate: one continuous band, then the stack the profile declares."""

import re
import xml.etree.ElementTree as ET

import pytest

from generator.plates import languages
from generator.plates.languages import sweep_time
from generator.themes import get_theme
from tests.contract import rules
from tests.svgread import text_runs, texts

SKY = get_theme("deep-sky", "dark")
SHARES = [("TypeScript", 41.2), ("Python", 30.4), ("Svelte", 12.1), ("Rust", 7.9), ("Go", 3.4),
          ("JavaScript", 1.7), ("Dockerfile", 1.6), ("Lua", 1.7)]
ARMS = [{"name": "Web & Cloud", "items": ["TypeScript", "Svelte", "Docker"]},
        {"name": "AI & Data", "items": ["Python", "PyTorch"]},
        {"name": "Systems", "items": ["Rust", "Go"]}]


def plate(shares=SHARES, arms=ARMS, mobile=False, motion=True, theme=SKY):
    return languages.render(shares, arms, theme, mobile=mobile, motion=motion)


def segments(svg):
    """(x, width, colour) of every segment of the band, left to right."""
    found = re.findall(r'<g transform="translate\(([\d.]+) 56\)">(?:<g[^>]*>)?<rect width="([\d.]+)" height="24" rx="2.5" '
                       r'fill="(#[0-9a-f]{6})"', svg)
    return [(float(x), float(w), colour) for x, w, colour in found]


# ── the sweep ────────────────────────────────────────────────────────────────

def test_sweep_time_starts_at_zero_ends_at_one_and_never_goes_back():
    assert sweep_time(0) == 0 and sweep_time(1) == 1
    times = [sweep_time(i / 50) for i in range(51)]
    assert times == sorted(times) and len(set(times)) == 51


def test_sweep_time_inverts_a_cubic_ease_out():
    for t in (0.1, 0.35, 0.8):
        assert sweep_time(1 - (1 - t) ** 3) == pytest.approx(t)


# ── size ─────────────────────────────────────────────────────────────────────

def test_plate_sizes_for_three_short_focus_areas():
    assert rules.viewbox(plate()) == (850, 226)
    assert rules.viewbox(plate(mobile=True)) == (390, 326)


# ── the band ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mobile", [False, True])
def test_segments_and_gaps_fill_the_band_exactly(mobile):
    found = segments(plate(mobile=mobile))
    left, right = (24, 366) if mobile else (44, 806)
    assert len(found) == 8
    assert found[0][0] == left
    assert found[-1][0] + found[-1][1] == pytest.approx(right, abs=0.3)
    for (x, w, _c), (next_x, _w, _c2) in zip(found, found[1:]):
        assert next_x - (x + w) == pytest.approx(2, abs=0.15)


def test_segment_widths_are_proportional_to_the_percentages():
    found = segments(plate())
    assert found[0][1] / found[1][1] == pytest.approx(41.2 / 30.4, rel=0.02)


def test_segments_take_the_colours_of_the_themes_ramp_in_order():
    assert [colour for _x, _w, colour in segments(plate())] == list(SKY.ramp)


def test_more_languages_than_the_ramp_has_steps_reuse_its_last_colour():
    many = [(f"Lang{i}", 5.0) for i in range(20)]
    colours = [colour for _x, _w, colour in segments(plate(shares=many))]
    assert len(colours) == 20 and colours[:8] == list(SKY.ramp) and set(colours[8:]) == {SKY.ramp[-1]}


def test_what_the_list_leaves_out_is_a_last_segment_in_the_hairline_colour():
    found = segments(plate(shares=[("Python", 50.0), ("Rust", 30.0)]))
    assert len(found) == 3 and found[-1][2] == SKY.faint
    assert found[-1][1] / found[0][1] == pytest.approx(20 / 50, rel=0.03)


def test_only_the_named_segments_cast_light_below_the_band():
    svg = plate(shares=[("Python", 50.0), ("Rust", 30.0)])
    assert len(re.findall(r'fill="url\(#sg\d\)"', svg)) == 2 and "sgNone" not in svg


def test_percentages_that_already_add_up_get_no_extra_segment():
    assert len(segments(plate(shares=[("Python", 60.2), ("Rust", 39.6)]))) == 2


def test_a_single_language_is_one_segment_with_its_name():
    svg = plate(shares=[("Python", 100.0)])
    found = segments(svg)
    assert len(found) == 1 and found[0][:2] == (44, 762)
    assert {"Python", "100%"} <= set(texts(svg))


# ── names ────────────────────────────────────────────────────────────────────

def test_a_name_that_fits_its_segment_is_written_under_it_with_its_percentage():
    svg = plate()
    runs = {run["text"]: run for run in text_runs(svg)}
    found = segments(svg)
    assert runs["TypeScript"]["x"] == found[0][0] and runs["41.2%"]["x"] == found[0][0]
    assert runs["Python"]["x"] == found[1][0]
    assert runs["41.2%"]["y"] > runs["TypeScript"]["y"] > 56 + 24


def test_a_name_wider_than_its_segment_goes_to_the_closing_phrase():
    svg = plate()
    shown = texts(svg)
    assert "JavaScript" not in shown and "Dockerfile" not in shown
    assert "Rust" in shown and "Go" not in shown                   # "3.4%" is wider than Go's 26 pixels
    assert "andGo3.4%,JavaScript1.7%,Dockerfile1.6%,Lua1.7%" in shown


def test_names_under_the_band_never_run_into_the_next_one():
    for mobile in (False, True):
        svg = plate(mobile=mobile)
        found = segments(svg)
        runs = text_runs(svg)
        for x, w, _colour in found:
            for run in runs:
                if run["x"] == x and 80 < run["y"] < 130:
                    assert run["width"] <= w


def test_whole_percentages_are_written_without_a_decimal():
    assert {"60%", "40%"} <= set(texts(plate(shares=[("Python", 60.0), ("TypeScript", 40.0)])))


@pytest.mark.parametrize("mobile", [False, True])
def test_twenty_languages_cut_the_closing_phrase_inside_the_plate(mobile):
    many = [(f"Language{i}", 5.0) for i in range(20)]
    svg = plate(shares=many, mobile=mobile)
    rules.text_stays_inside(svg)
    tail = next(run for run in text_runs(svg) if run["text"].startswith("andLanguage"))
    assert tail["text"].endswith("…")
    heading = next(run for run in text_runs(svg) if run["text"].startswith("Languagesacross"))
    if not mobile:
        assert tail["x"] >= heading["x"] + heading["width"] + 16       # beside the heading, never over it


def test_on_mobile_the_closing_phrase_has_a_line_of_its_own():
    runs = text_runs(plate(mobile=True))
    tail = next(run for run in runs if run["text"].startswith("and"))
    heading = next(run for run in runs if run["text"].startswith("Languagesacross"))
    assert "JavaScript1.7%" in tail["text"]
    assert tail["y"] > 56 + 24 + 44 and tail["x"] == heading["x"] == 24


# ── the declared stack ───────────────────────────────────────────────────────

def test_each_focus_area_lists_its_items_under_its_name():
    shown = texts(plate())
    assert {"Web&Cloud", "TypeScript,Svelte,Docker", "AI&Data", "Python,PyTorch", "Systems", "Rust,Go"} <= set(shown)


def test_on_desktop_focus_areas_sit_in_three_columns():
    runs = {run["text"]: run for run in text_runs(plate())}
    xs = [runs[name]["x"] for name in ("Web&Cloud", "AI&Data", "Systems")]
    assert xs == [44, 44 + 254, 44 + 508]
    assert len({runs[name]["y"] for name in ("Web&Cloud", "AI&Data", "Systems")}) == 1


def test_on_mobile_focus_areas_are_stacked():
    runs = {run["text"]: run for run in text_runs(plate(mobile=True))}
    assert runs["Web&Cloud"]["x"] == runs["AI&Data"]["x"] == 24
    assert runs["Web&Cloud"]["y"] < runs["AI&Data"]["y"] < runs["Systems"]["y"]


def six_long_areas():
    items = ["TypeScript", "PostgreSQL", "Kubernetes", "Terraform", "GraphQL", "Elixir/Phoenix", "Apache Kafka",
             "OpenTelemetry", "WebAssembly", "Prometheus"]
    return [{"name": f"Focus area number {i + 1}", "items": items} for i in range(6)]


@pytest.mark.parametrize("mobile", [False, True])
def test_six_areas_of_ten_items_fit_the_plate_and_make_it_taller(mobile):
    svg = plate(arms=six_long_areas(), mobile=mobile)
    width, height = rules.viewbox(svg)
    assert height > (326 if mobile else 226)
    rules.text_stays_inside(svg)
    rules.svg_is_sound(svg)
    runs = text_runs(svg)
    assert sum(1 for run in runs if run["text"].startswith("Focusareanumber")) == 6
    assert max(run["y"] for run in runs) <= height - 24             # room under the last line
    assert any(run["text"].endswith("…") for run in runs)           # ten items do not fit in two lines


def test_on_desktop_a_fourth_area_starts_a_second_row():
    runs = {run["text"]: run for run in text_runs(plate(arms=six_long_areas()))}
    assert runs["Focusareanumber4"]["x"] == runs["Focusareanumber1"]["x"]
    assert runs["Focusareanumber4"]["y"] > runs["Focusareanumber1"]["y"] + 50


def test_a_list_is_never_longer_than_two_lines():
    svg = plate(arms=six_long_areas()[:1])
    lines = [run for run in text_runs(svg) if run["text"].startswith(("TypeScript,", "Kubernetes", "Terraform", "GraphQL"))]
    assert 1 <= len(lines) <= 2


def test_a_list_breaks_between_items_never_inside_one():
    arms = [{"name": "Web & Cloud", "items": ["TypeScript", "React", "Flask", "AWS / Oracle"]}]
    shown = texts(plate(arms=arms))
    assert "TypeScript,React,Flask," in shown and "AWS/Oracle" in shown


def test_an_item_wider_than_the_column_is_cut_not_spilled():
    arms = [{"name": "Long", "items": ["An extraordinarily long item that no column of this plate could ever hold", "Go"]}]
    for mobile in (False, True):
        svg = plate(arms=arms, mobile=mobile)
        rules.text_stays_inside(svg)
        lines = [run for run in text_runs(svg) if run["text"].startswith("Anextraordinarily")]
        assert len(lines) == 1 and lines[0]["width"] <= (342 if mobile else 230)


def test_a_list_cut_at_two_lines_says_so_with_an_ellipsis():
    runs = [run for run in text_runs(plate(arms=six_long_areas()[:1])) if run["style"] == "regular" and run["y"] > 150]
    assert len(runs) == 2 and runs[-1]["text"].endswith("…") and not runs[0]["text"].endswith("…")
    assert runs[0]["text"].endswith(",")


def test_an_area_without_items_shows_its_name_alone():
    svg = plate(arms=[{"name": "Curiosity", "items": []}])
    ET.fromstring(svg)
    assert "Curiosity" in texts(svg)


def test_items_that_are_not_text_are_written_as_text():
    assert "0,3,True,Go" in texts(plate(arms=[{"name": "Odd", "items": [0, 3, True, "Go"]}]))


# ── no language data ─────────────────────────────────────────────────────────

def test_without_languages_a_sentence_takes_the_place_of_the_band_and_the_stack_stays():
    for mobile in (False, True):
        svg = plate(shares=[], mobile=mobile)
        shown = texts(svg)
        assert "Nolanguagedatayet" in shown and "Web&Cloud" in shown
        assert segments(svg) == [] and 'class="edge' not in svg
        rules.text_stays_inside(svg)


# ── motion ───────────────────────────────────────────────────────────────────

def test_each_segment_opens_from_its_left_edge_in_time_with_one_sweep():
    svg = plate()
    timing = re.findall(r'class="grow" style="animation-delay:([\d.]+)s;animation-duration:([\d.]+)s"', svg)
    assert len(timing) == 8
    starts = [float(delay) for delay, _d in timing]
    ends = [float(delay) + float(duration) for delay, duration in timing]
    assert starts[0] == 0.25 and starts == sorted(starts)
    assert ends[-1] == pytest.approx(0.25 + 1.5, abs=0.02)
    for end, next_start in zip(ends, starts[1:]):
        assert next_start == pytest.approx(end, abs=0.03)             # the next one opens as this one closes


def test_a_bright_edge_travels_with_the_sweep_and_exists_only_in_motion():
    svg = plate()
    assert re.findall(r'class="([^"]*\bmo\b[^"]*)"', svg) == ["edge mo"]
    css = re.search(r"<style>(.*?)</style>", svg).group(1)
    frames = re.search(r"@keyframes edge\{(.*?\})\}", css).group(1)
    assert frames.startswith("0%{transform:translateX(44px);opacity:0}")
    assert re.search(r"100%\{transform:translateX\(806px\);opacity:0\}$", frames)
    assert "edge" not in plate(motion=False)


def test_names_appear_as_the_light_reaches_them():
    svg = plate()
    delays = [float(v) for v in re.findall(r'class="soft" style="animation-delay:([\d.]+)s"', svg)]
    assert delays[:4] == sorted(delays[:4]) and delays[0] == pytest.approx(0.4)


def test_the_light_under_the_band_breathes_out_of_step():
    svg = plate()
    assert svg.count('class="breathe"') == 8
    assert len(set(re.findall(r'class="breathe" style="animation-delay:(-?[\d.]+)s"', svg))) == 7   # the first has none


def test_without_motion_the_plate_is_complete_and_still():
    svg = plate(motion=False)
    rules.no_motion_at_all(svg)
    assert texts(svg) == texts(plate()) and len(segments(svg)) == 8
    assert "<path d=\"M0 " not in svg                               # the sweep's bright edge is not left behind


@pytest.mark.parametrize("arms", [ARMS, six_long_areas()], ids=["three", "six-long"])
def test_the_contract_holds_in_every_theme(arms):
    many = [(f"Language{i}", 5.0) for i in range(20)]
    for palette in ("deep-sky", "cyanotype"):
        for mode in ("dark", "light"):
            for mobile in (False, True):
                for shares in (SHARES, many):
                    svg = plate(shares=shares, arms=arms, theme=get_theme(palette, mode), mobile=mobile)
                    rules.rest_state_is_complete(svg)
                    rules.no_forbidden_techniques(svg)
                    rules.motion_is_guarded(svg)
                    rules.text_stays_inside(svg)
                    rules.placements_are_inside(svg)
                    rules.within_budget(svg, 48_000, 80)
                    rules.svg_is_sound(svg)
                    rules.is_accessible(svg)


def test_description_lists_languages_and_stack():
    svg = plate()
    assert "TypeScript 41.2%" in svg and "Web &amp; Cloud: TypeScript, Svelte, Docker" in svg


def test_same_input_same_bytes():
    assert plate() == plate() and plate(mobile=True) == plate(mobile=True)


# ── shares at the edge of nothing ────────────────────────────────────────────

def test_sweep_time_holds_at_its_ends_for_a_fraction_a_hair_outside_them():
    assert sweep_time(1 + 1e-12) == 1 and sweep_time(-1e-12) == 0
    assert isinstance(sweep_time(1.0000001), float)


@pytest.mark.parametrize("mobile", [False, True])
@pytest.mark.parametrize("shares", [
    [("Python", 99.9), ("Shell", 0.1), ("Makefile", 0.0)],
    [("Python", 100.0), ("Shell", 0.0)],
    [("Python", 60.0), ("Go", 40.0), ("C", 0.0), ("Lua", 0.0)],
    [("Python", 0.0)],
])
def test_a_language_that_rounds_to_nothing_does_not_break_the_plate(shares, mobile):
    svg = plate(shares=shares, mobile=mobile)
    ET.fromstring(svg)
    rules.svg_is_sound(svg)
    rules.text_stays_inside(svg)
    assert all(width > 0 for _x, width, _colour in segments(svg))


# ── what the digest alone used to guard ──────────────────────────────────────

def test_the_band_is_filled_whatever_the_percentages_add_up_to():
    for shares in ([("Python", 60.0), ("Go", 39.7)], [("Python", 60.1), ("Go", 40.1)], [("A", 33.3), ("B", 33.3), ("C", 33.3)]):
        found = segments(plate(shares=shares))
        assert len(found) == len(shares)
        assert found[-1][0] + found[-1][1] == pytest.approx(806, abs=0.3)


def test_the_bright_edge_reaches_the_end_of_each_segment_as_that_segment_finishes_opening():
    svg = plate()
    css = re.search(r"<style>(.*?)</style>", svg).group(1)
    stops = {float(x): float(when) for when, x in re.findall(
        r"([\d.]+)%\{transform:translateX\(([\d.]+)px\)", re.search(r"@keyframes edge\{(.*?\})\}", css).group(1))}
    timing = re.findall(r'class="grow" style="animation-delay:([\d.]+)s;animation-duration:([\d.]+)s"', svg)
    assert len(stops) == 9                                          # the start and the end of each of eight segments
    for (x, w, _colour), (delay, duration) in zip(segments(svg), timing):
        finishes = (float(delay) + float(duration) - 0.25) / 1.5 * 100
        nearest = min(stops, key=lambda stop: abs(stop - (x + w)))
        assert nearest == pytest.approx(x + w, abs=0.11) and stops[nearest] == pytest.approx(finishes, abs=0.7)


def test_the_two_lines_of_a_list_are_a_line_apart():
    for mobile, step in ((False, 19), (True, 17)):
        runs = [run for run in text_runs(plate(arms=six_long_areas()[:1], mobile=mobile))
                if run["style"] == "regular" and run["y"] > 150]
        assert len(runs) == 2 and runs[1]["y"] - runs[0]["y"] == pytest.approx(step, abs=0.11)


def test_blank_items_are_skipped_among_the_others():
    assert "Go,Rust" in texts(plate(arms=[{"name": "Systems", "items": ["Go", " ", None, "", "Rust"]}]))


def test_a_focus_area_whose_items_are_blank_shows_its_name_alone():
    for items in ([" "], ["", "  "], [None]):
        svg = plate(arms=[{"name": "Curiosity", "items": items}])
        ET.fromstring(svg)
        assert "Curiosity" in texts(svg)


# ── the size of the file ─────────────────────────────────────────────────────

ORDINARY = [
    ("Frontend", ["TypeScript", "React", "Next.js", "Vue", "Svelte", "Tailwind CSS", "Vite", "Storybook", "Jest", "Cypress"]),
    ("Backend", ["Python", "Django", "FastAPI", "Node.js", "Express", "Go", "gRPC", "GraphQL", "Redis", "RabbitMQ"]),
    ("Data", ["PostgreSQL", "MySQL", "MongoDB", "ClickHouse", "Apache Kafka", "Airflow", "dbt", "Spark", "Pandas", "DuckDB"]),
    ("Machine Learning", ["PyTorch", "TensorFlow", "scikit-learn", "Hugging Face", "LangChain", "ONNX", "MLflow", "Jupyter",
                          "NumPy", "XGBoost"]),
    ("Infrastructure", ["Docker", "Kubernetes", "Terraform", "Ansible", "AWS", "Google Cloud", "Azure", "Nginx", "Linux",
                        "Prometheus"]),
    ("Mobile & Desktop", ["Swift", "Kotlin", "Flutter", "React Native", "Electron", "Tauri", "Qt", "SwiftUI", "Jetpack",
                          "Xcode"]),
]


def ordinary_areas(count=6):
    return [{"name": name, "items": items} for name, items in ORDINARY[:count]]


@pytest.mark.parametrize("mobile", [False, True])
def test_six_ordinary_focus_areas_of_ten_items_each_stay_under_the_budget(mobile):
    many = [(f"Language{i}", 5.0) for i in range(20)]
    for shares in (SHARES, many):
        svg = plate(shares=shares, arms=ordinary_areas(), mobile=mobile)
        rules.within_budget(svg, 48_000, 80)
        rules.text_stays_inside(svg)


def item_lines(svg, top=150):
    return [run for run in text_runs(svg) if run["style"] == "regular" and run["y"] > top]


def test_lists_keep_two_lines_as_long_as_the_file_fits_whatever_the_number_of_areas():
    four = [{"name": name, "items": items[:6]} for name, items in ORDINARY[:4]]
    for mobile in (False, True):
        top = 180 if mobile else 150
        assert len(item_lines(plate(arms=ordinary_areas(3), mobile=mobile), top)) == 6
        svg = plate(arms=[dict(area, items=area["items"] * 2) for area in four], mobile=mobile)
        assert len(item_lines(svg, top)) == 8                       # four areas, two lines each
        rules.within_budget(svg, 48_000, 80)


@pytest.mark.parametrize("mobile", [False, True])
@pytest.mark.parametrize("areas", [ordinary_areas(6), six_long_areas(), ordinary_areas(6) + ordinary_areas(6)],
                         ids=["six", "six-long", "twelve"])
def test_the_lists_get_two_lines_exactly_when_two_lines_fit_the_budget(areas, mobile):
    two = languages._compose(SHARES, areas, SKY, mobile, True, 2)
    one = languages._compose(SHARES, areas, SKY, mobile, True, 1)
    assert len(one.encode()) < len(two.encode())
    assert plate(arms=areas, mobile=mobile) == (two if len(two.encode()) <= 48_000 else one)


def test_twelve_full_focus_areas_are_what_it_takes_to_lose_the_second_line():
    assert len(languages._compose(SHARES, ordinary_areas(6), SKY, False, True, 2).encode()) <= 48_000
    twelve = ordinary_areas(6) + ordinary_areas(6)
    assert len(languages._compose(SHARES, twelve, SKY, True, True, 2).encode()) > 48_000
    assert len(item_lines(plate(arms=twelve, mobile=True), 180)) == 12


def test_the_description_lists_the_stack_as_it_is_drawn():
    svg = plate(arms=[{"name": "Tools", "items": ["Git", None, "", "  ", 3, "Vim"]}, {"name": None, "items": ["Go"]}])
    assert "Declared stack: Tools: Git, 3, Vim; Go." in svg


def test_a_cut_list_ends_in_an_ellipsis_with_no_comma_left_hanging_before_it():
    cut = [run["text"] for mobile in (False, True) for count in (1, 3, 6)
           for run in item_lines(plate(arms=ordinary_areas(count), mobile=mobile), 150) if run["text"].endswith("…")]
    assert len(cut) >= 6 and not any(text.endswith(",…") for text in cut)


def test_a_plate_over_its_budget_gives_up_the_second_line_of_each_list(monkeypatch):
    two_lines = plate(arms=ordinary_areas(3))
    monkeypatch.setattr(languages, "BYTE_BUDGET", len(two_lines.encode()) - 1)
    lighter = plate(arms=ordinary_areas(3))
    assert len(item_lines(two_lines)) == 6 and len(item_lines(lighter)) == 3
    assert {"Frontend", "Backend", "Data"} <= set(texts(lighter))           # the areas themselves all stay


def test_a_plate_that_cannot_be_made_to_fit_says_so_in_the_log_and_is_drawn_anyway(monkeypatch, caplog):
    monkeypatch.setattr(languages, "BYTE_BUDGET", 1000)
    with caplog.at_level("WARNING"):
        svg = plate(arms=ordinary_areas(3))
    ET.fromstring(svg)
    assert "over the" in caplog.text and "tech-stack" in caplog.text
