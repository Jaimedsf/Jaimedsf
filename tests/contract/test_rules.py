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


# ── review fixes: the rules must see more ────────────────────────────────────

def test_rest_state_rejects_other_spellings_of_zero_opacity():
    for hidden in ('<g opacity="0.0" class="soft"/>', '<g opacity=".0"/>', '<g style="opacity:0"/>',
                   '<g style="--d:4px;opacity: 0;"/>'):
        with pytest.raises(AssertionError, match="invisible at rest"):
            rules.rest_state_is_complete(svg(hidden))


def test_rest_state_rejects_a_css_rule_that_hides_an_element_outside_keyframes():
    css = f"<style>{GUARD}{{.hide{{opacity:0}}@keyframes a{{from{{opacity:0}}}}}}</style>"
    with pytest.raises(AssertionError, match="CSS rule"):
        rules.rest_state_is_complete(svg(css + '<g class="hide"/>'))


def test_rest_state_accepts_keyframes_that_start_from_zero():
    rules.rest_state_is_complete(svg(f"<style>{GUARD}{{.a{{animation:a 1s both}}@keyframes a{{from{{opacity:0}}}}}}</style>"))


def test_forbidden_rejects_a_group_opacity_wrapping_particles():
    particles = "M1 1h.01" + "m2 2h.01" * 6
    with pytest.raises(AssertionError, match="stroke-opacity"):
        rules.no_forbidden_techniques(svg(f'<g opacity=".5"><g><path d="{particles}"/></g></g>'))


def test_forbidden_allows_a_motion_only_wrapper_around_particles():
    particles = "M1 1h.01" + "m2 2h.01" * 6
    rules.no_forbidden_techniques(svg(f'<g class="actors mo" opacity="0"><path d="{particles}"/></g>'))


def test_guard_rejects_an_animation_named_in_an_inline_style():
    with pytest.raises(AssertionError, match="inline"):
        rules.motion_is_guarded(svg('<g style="animation-name:spin;animation-duration:1s"/>'))
    with pytest.raises(AssertionError, match="inline"):
        rules.motion_is_guarded(svg('<g style="animation:spin 1s infinite"/>'))


def test_guard_accepts_inline_timing_and_custom_properties():
    rules.motion_is_guarded(svg('<g class="pop" style="animation-delay:.2s;animation-duration:1s;--d:4px"/>'))


def test_bounds_reject_fallback_text_running_off_the_plate():
    text = '<text x="60" y="20" font-family="Georgia, serif" font-size="16" fill="#fff">日本語の説明です</text>'
    with pytest.raises(AssertionError, match="sideways"):
        rules.text_stays_inside(svg(text))


def test_bounds_accept_fallback_text_that_fits():
    rules.text_stays_inside(svg('<text x="10" y="20" font-family="Georgia, serif" font-size="12" fill="#fff">日本</text>'))


def test_bounds_reject_an_element_placed_outside_the_plate():
    with pytest.raises(AssertionError, match="outside"):
        rules.placements_are_inside(svg('<g transform="translate(-40 20)"><circle r="2"/></g>'))
    with pytest.raises(AssertionError, match="outside"):
        rules.placements_are_inside(svg('<g fill="#fff"><use href="#i41" transform="translate(50 80) rotate(10) scale(.01) translate(-300 0)"/></g>'))


def test_bounds_ignore_coordinates_inside_a_transformed_group():
    rules.placements_are_inside(svg('<g transform="translate(50 25)"><g transform="translate(-300 0)"/></g>'))


def test_bounds_follow_the_rotation_of_fallback_text():
    upright = '<text transform="translate(90 25) rotate(90)" font-size="10" text-anchor="middle">銀河銀河</text>'
    rules.text_stays_inside(svg(upright))                 # 40 px of text standing up near the right edge fit
    with pytest.raises(AssertionError, match="sideways"):
        rules.text_stays_inside(svg(upright.replace("rotate(90)", "rotate(0)")))
    with pytest.raises(AssertionError, match="vertically"):
        rules.text_stays_inside(svg(upright.replace("translate(90 25)", "translate(90 40)")))



def test_strokes_reject_a_fallback_text_outlined_in_font_units():
    wide = '<text x="10" y="20" font-size="13.5" stroke="#000" stroke-width="259.3" paint-order="stroke">日本</text>'
    with pytest.raises(AssertionError, match="259.3 px outline"):
        rules.text_strokes_are_thin(svg(wide))
    rules.text_strokes_are_thin(svg(wide.replace("259.3", "3.5")))


# ── T1b: an animation ends where the still image is ──────────────────────────

def animated(css, body='<g class="soft"/>'):
    return svg(f"<defs><style>{GUARD}{{{css}}}</style></defs>{body}")


def test_ending_accepts_an_entrance_that_only_says_where_it_comes_from():
    rules.animations_end_at_rest(animated(".soft{animation:soft 1.2s ease-out both}@keyframes soft{from{opacity:0}}"))
    rules.animations_end_at_rest(animated(
        ".soft{animation:soft 1s both}@keyframes soft{0%{opacity:0;transform:scale(2)}"
        "60%{transform:scale(.5)}100%{opacity:1;transform:rotate(0deg) scale(1)}}"))


@pytest.mark.parametrize("css", [
    ".soft{animation:soft 1.2s ease-out both}@keyframes soft{to{opacity:0}}",
    ".soft{animation:soft 1.2s ease-out both}@keyframes soft{from{opacity:1}100%{opacity:0}}",
    ".soft{animation:soft .75s both}@keyframes soft{from{opacity:0}to{transform:scale(0)}}",
    ".soft{animation:soft 2s both}@keyframes soft{from{stroke-dashoffset:0}to{stroke-dashoffset:1}}",
    ".soft{animation:soft 2s both}@keyframes soft{0%{opacity:0}50%,100%{transform:translateY(8px)}}",
])
def test_ending_rejects_an_entrance_that_finishes_away_from_the_still_image(css):
    with pytest.raises(AssertionError, match="ends away from"):
        rules.animations_end_at_rest(animated(css))


def test_ending_rejects_an_entrance_that_does_not_hold_its_first_frame_through_its_delay():
    with pytest.raises(AssertionError, match="fill"):
        rules.animations_end_at_rest(animated(".soft{animation:soft 1.2s ease-out}@keyframes soft{from{opacity:0}}"))


def test_ending_rejects_a_motion_only_element_left_visible():
    leave = '<g class="leave mo" opacity="0"/>'
    rules.animations_end_at_rest(animated(
        ".leave{animation:leave 1s both}@keyframes leave{0%{opacity:1}100%{opacity:0}}", leave))
    with pytest.raises(AssertionError, match="left visible"):
        rules.animations_end_at_rest(animated(
            ".leave{animation:leave 1s both}@keyframes leave{0%{opacity:0}100%{opacity:1}}", leave))
    with pytest.raises(AssertionError, match="left visible"):
        rules.animations_end_at_rest(animated(
            ".leave{animation:leave 1s both}@keyframes leave{0%{opacity:0}50%{opacity:1}}", leave))


def test_ending_leaves_loops_alone():
    rules.animations_end_at_rest(animated(
        ".soft{animation:soft 60s linear infinite}@keyframes soft{to{transform:rotate(360deg)}}"))
