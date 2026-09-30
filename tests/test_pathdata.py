"""tools/pathdata.relative: the same outline in the shortest commands."""

import json
import re
from pathlib import Path

import pytest

from tools.pathdata import relative

FONTS = Path(__file__).resolve().parent.parent / "generator" / "fonts"
ARITY = {"m": 2, "l": 2, "h": 1, "v": 1, "q": 4, "c": 6, "z": 0}


def trace(d):
    """Every command of a path as (letter, absolute numbers): the reference reading of path data."""
    out, x, y, start = [], 0, 0, (0, 0)
    for letter, args in re.findall(r"([MLHVQCZmlhvqcz])([^MLHVQCZmlhvqcz]*)", d):
        numbers = [int(v) for v in re.findall(r"-?\d+", args)]
        kind, rel = letter.lower(), letter.islower()
        if kind == "z":
            assert not numbers
            out.append(("z", ()))
            x, y = start
            continue
        assert numbers and len(numbers) % ARITY[kind] == 0, f"bad arguments for {letter}: {args!r}"
        for k in range(0, len(numbers), ARITY[kind]):
            group = numbers[k:k + ARITY[kind]]
            step = "l" if kind == "m" and k else kind
            if step == "h":
                x = x + group[0] if rel else group[0]
                points = (x, y)
            elif step == "v":
                y = y + group[0] if rel else group[0]
                points = (x, y)
            else:
                points = tuple(v + ((x if i % 2 == 0 else y) if rel else 0) for i, v in enumerate(group))
                x, y = points[-2], points[-1]
            if step == "m":
                start = (x, y)
            out.append(("l" if step in "hv" else step, points))
    return out


def test_every_command_becomes_relative_except_the_move_that_opens_a_subpath():
    assert relative("M10 20L30 40H50V60Q1 2 3 4Z") == "M10 20l20 20h20v20q-49-58-47-56z"


def test_a_minus_sign_is_all_the_separator_a_number_needs():
    assert relative("M0 0L-5 -5L5 5") == "M0 0l-5-5 10 10"


def test_a_repeated_command_is_not_spelled_again():
    assert relative("M0 0L10 5L20 12L30 30") == "M0 0l10 5 10 7 10 18"


def test_points_after_a_move_are_lines():
    assert relative("M115 -200 70 -660H180L135 -200Z") == "M115-200l-45-460h110l-45 460z"


def test_a_line_along_an_axis_takes_the_short_form():
    assert relative("M0 0L10 0L10 8") == "M0 0h10v8"


def test_a_second_subpath_starts_where_it_says_not_where_the_first_one_closed():
    d = "M10 10L20 10L20 20ZM100 100L110 100L110 110Z"
    assert relative(d) == "M10 10h10v10zM100 100h10v10z"
    assert trace(relative(d)) == trace(d)


def test_an_empty_outline_stays_empty():
    assert relative("") == ""


@pytest.mark.parametrize("d", [
    "M156 10Q109 10 78 -18Q47 -45 47 -94V-330Q301 -365 276 -390L86 -305H64Z",
    "M0 0C10 0 20 10 20 20C20 30 10 40 0 40ZM5 5 8 8 2 9Z",
    "M-3 -4L-3 9H-3V9Q-1 -1 -3 -4Z",
])
def test_the_relative_form_traces_the_same_outline(d):
    assert trace(relative(d)) == trace(d)
    assert len(relative(d)) <= len(d)


@pytest.mark.parametrize("style", ["light", "regular", "medium", "italic"])
def test_the_atlases_are_written_in_the_relative_form(style):
    glyphs = json.loads((FONTS / f"spectral-{style}.json").read_text(encoding="utf-8"))["glyphs"]
    for char, (_advance, d) in glyphs.items():
        assert not re.search(r"[LHVQC]", d), char
        assert relative_is_stable(d), char


def relative_is_stable(d):
    """An outline already in the relative form has nothing left to gain: M is its only capital."""
    return d == "" or (d[0] == "M" and set(re.findall(r"[A-Za-z]", d)) <= set("Mlhvqcz"))
