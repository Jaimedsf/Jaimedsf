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
