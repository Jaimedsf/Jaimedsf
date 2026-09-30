"""SVG primitives."""

from generator.svg import esc, num


def test_num_drops_a_trailing_zero():
    assert num(12.0) == "12"


def test_num_rounds_to_one_decimal_by_default():
    assert num(3.14159) == "3.1"


def test_num_never_prints_negative_zero():
    assert num(-0.04) == "0"


def test_num_keeps_more_places_when_asked():
    assert num(0.25, 2) == ".25"
    assert num(0.0135, 4) == ".0135"


def test_num_drops_the_leading_zero_of_fractions():
    assert num(0.5) == ".5"
    assert num(-0.5) == "-.5"


def test_esc_escapes_xml_specials_including_quotes():
    assert esc('R&D <"x">') == "R&amp;D &lt;&quot;x&quot;&gt;"
