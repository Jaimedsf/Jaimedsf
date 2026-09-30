"""Proof that each contract rule can fail: a minimal SVG that breaks it must be rejected."""

import pytest

from generator.motion import GUARD
from tests.contract import rules

HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" role="img"><title>t</title><desc>d</desc>'


def svg(body, head=HEAD):
    return f"{head}{body}</svg>"


def test_rest_state_rejects_an_element_hidden_at_rest():
    with pytest.raises(AssertionError, match="invisible at rest"):
        rules.rest_state_is_complete(svg('<g opacity="0" class="soft"/>'))


def test_rest_state_rejects_a_visible_motion_only_element():
    with pytest.raises(AssertionError, match="visible at rest"):
        rules.rest_state_is_complete(svg('<use class="comet mo"/>'))


def test_rest_state_accepts_a_hidden_motion_only_element():
    rules.rest_state_is_complete(svg('<use class="comet mo" opacity="0"/>'))


def test_forbidden_rejects_non_scaling_stroke():
    with pytest.raises(AssertionError, match="pinch zoom"):
        rules.no_forbidden_techniques(svg('<path d="M0 0h1" vector-effect="non-scaling-stroke"/>'))


def test_forbidden_rejects_smil():
    with pytest.raises(AssertionError, match="SMIL"):
        rules.no_forbidden_techniques(svg('<circle r="1"><animate attributeName="r" to="2" dur="1s"/></circle>'))


def test_forbidden_rejects_group_opacity_on_particles():
    particles = "M1 1h.01" + "m2 2h.01" * 6
    with pytest.raises(AssertionError, match="stroke-opacity"):
        rules.no_forbidden_techniques(svg(f'<path d="{particles}" opacity=".5"/>'))


def test_guard_rejects_css_outside_the_media_query():
    with pytest.raises(AssertionError, match="guard"):
        rules.motion_is_guarded(svg("<style>.pop{animation:pop 1s}</style>"))


def test_guard_rejects_css_after_the_media_query():
    with pytest.raises(AssertionError, match="after"):
        rules.motion_is_guarded(svg(f"<style>{GUARD}{{.a{{animation:a 1s}}}}.b{{animation:b 1s}}</style>"))


def test_guard_accepts_one_guarded_block():
    rules.motion_is_guarded(svg(f"<style>{GUARD}{{.a{{animation:a 1s}}@keyframes a{{from{{opacity:0}}}}}}</style>"))


def test_no_motion_rejects_a_leftover_class():
    with pytest.raises(AssertionError, match="animation class"):
        rules.no_motion_at_all(svg('<g class="pop"/>'))


def test_no_motion_rejects_a_style_block():
    with pytest.raises(AssertionError):
        rules.no_motion_at_all(svg(f"<style>{GUARD}{{}}</style>"))


def test_bounds_reject_text_running_off_the_plate():
    line = '<g transform="translate(90 20) scale(.02)" fill="#fff"><use href="#r41"/><use href="#r56" x="700"/></g>'
    with pytest.raises(AssertionError, match="sideways"):
        rules.text_stays_inside(svg(line))


def test_budget_rejects_a_heavy_file_and_too_many_animated_elements():
    with pytest.raises(AssertionError, match="bytes"):
        rules.within_budget(svg("<g/>" * 50), max_bytes=100, max_animated=10)
    with pytest.raises(AssertionError, match="animated elements"):
        rules.within_budget(svg('<g class="pop"/>' * 5), max_bytes=10_000, max_animated=4)


def test_soundness_rejects_duplicate_ids_and_dangling_references():
    with pytest.raises(AssertionError, match="duplicated"):
        rules.svg_is_sound(svg('<path id="a"/><path id="a"/>'))
    with pytest.raises(AssertionError, match="undefined"):
        rules.svg_is_sound(svg('<use href="#ghost"/>'))
    with pytest.raises(AssertionError, match="undefined"):
        rules.svg_is_sound(svg('<circle fill="url(#ghost)"/>'))


def test_accessibility_rejects_a_missing_role_or_empty_description():
    with pytest.raises(AssertionError):
        rules.is_accessible(svg("", head='<svg xmlns="http://www.w3.org/2000/svg"><title>t</title><desc>d</desc>'))
    with pytest.raises(AssertionError, match="title and desc"):
        rules.is_accessible(svg("", head='<svg xmlns="http://www.w3.org/2000/svg" role="img"><title>t</title><desc> </desc>'))
