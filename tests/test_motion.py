"""The motion switch: classes, motion-only elements and the guarded CSS block."""

import pytest

from generator.motion import GUARD, Motion


def test_cls_names_the_animation_and_sets_its_timing():
    motion = Motion()
    assert motion.cls("pop") == ' class="pop"'
    assert motion.cls("pop", delay=1.25) == ' class="pop" style="animation-delay:1.25s"'
    assert motion.cls("soft", delay=0.5, duration=2) == ' class="soft" style="animation-delay:.5s;animation-duration:2s"'


def test_cls_passes_custom_properties():
    assert Motion().cls("soft", vars={"d": "40px"}) == ' class="soft" style="--d:40px"'


def test_motion_only_elements_are_marked_and_invisible_at_rest():
    assert Motion().cls("comet", only=True) == ' class="comet mo" opacity="0"'


def test_unknown_animation_name_is_a_programming_error():
    with pytest.raises(KeyError):
        Motion().cls("wobble")


def test_css_holds_only_the_animations_in_use_inside_the_reduced_motion_guard():
    motion = Motion()
    motion.cls("pop")
    css = motion.css()
    assert css.startswith(GUARD + "{") and css.endswith("}")
    assert ".pop{" in css and "@keyframes pop" in css
    assert "comet" not in css


def test_custom_css_goes_inside_the_guard_too():
    motion = Motion()
    motion.add(".edge{animation:edge 1s linear both}@keyframes edge{from{opacity:0}}")
    assert motion.css() == GUARD + "{.edge{animation:edge 1s linear both}@keyframes edge{from{opacity:0}}}"


def test_no_animation_used_means_no_css():
    assert Motion().css() == ""


def test_switched_off_motion_emits_nothing():
    motion = Motion(False)
    assert motion.cls("pop", delay=1) == ""
    assert motion.cls("comet", only=True) == ""
    assert motion.only("<g/>") == ""
    motion.add(".x{}")
    assert motion.css() == ""


def test_only_passes_markup_through_when_motion_is_on():
    assert Motion().only("<g/>") == "<g/>"


# ── classes a plate defines for itself ───────────────────────────────────────

def test_a_plate_can_define_its_own_animation_class():
    motion = Motion()
    motion.define("flow", ".flow{animation:flow 22s linear infinite}@keyframes flow{to{transform:rotate(60deg)}}")
    assert motion.cls("flow", duration=29) == ' class="flow" style="animation-duration:29s"'
    assert motion.cls("flow", only=True) == ' class="flow mo" opacity="0"'
    assert "@keyframes flow" in motion.css()


def test_a_defined_class_costs_nothing_until_it_is_used():
    motion = Motion()
    motion.define("flow", ".flow{}")
    assert motion.css() == ""


def test_defining_a_class_does_nothing_when_motion_is_off():
    motion = Motion(False)
    motion.define("flow", ".flow{}")
    assert motion.cls("flow") == "" and motion.css() == ""


# ── the three lower plates ───────────────────────────────────────────────────

def test_rise_lifts_an_element_from_a_given_distance_below():
    motion = Motion()
    assert motion.cls("rise", delay=0.22, vars={"d": "40px"}) == ' class="rise" style="animation-delay:.22s;--d:40px"'
    assert "@keyframes rise{from{transform:translateY(var(--d));opacity:0}}" in motion.css()


def test_grow_sweeps_an_element_open_from_its_left_edge_at_a_steady_pace():
    motion = Motion()
    assert motion.cls("grow", delay=0.3, duration=0.2) == ' class="grow" style="animation-delay:.3s;animation-duration:.2s"'
    css = motion.css()
    assert ".grow{animation:grow linear both}" in css and "@keyframes grow{from{transform:scaleX(0)}}" in css


def test_breathe_dims_to_half_and_back_every_six_seconds():
    motion = Motion()
    assert motion.cls("breathe", delay=-1.1) == ' class="breathe" style="animation-delay:-1.1s"'
    assert ".breathe{animation:breathe 6s ease-in-out infinite}@keyframes breathe{50%{opacity:.5}}" in motion.css()
