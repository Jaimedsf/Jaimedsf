"""Rewrite SVG path data in its shortest commands.

A glyph outline comes out of the font pen in absolute coordinates. Written
relative to the previous point the numbers are one digit shorter on average,
and an outline takes a quarter less room in every SVG that uses it. The shape
is exactly the same.

Pure Python, integers only: this is for glyph outlines in font units.
"""

from __future__ import annotations

import re

_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6}
_COMMAND = re.compile(r"([MLHVQCZ])([^MLHVQCZ]*)")
_WHOLE = re.compile(r"(?:Z|[MLHVQC] ?-?\d+(?: ?-?\d+)*)*")


def _numbers(values) -> str:
    """Numbers separated by a space only where a minus sign does not already separate them."""
    text = ""
    for value in values:
        piece = str(value)
        text += piece if not text or piece.startswith("-") else " " + piece
    return text


def relative(d: str) -> str:
    """The same path with every command relative, except the move that opens each subpath.

    Takes absolute M, L, H, V, Q, C and Z with integer arguments. Lines along
    an axis become h or v, and a command repeated right after itself is not
    spelled again. Anything else raises ValueError: a path it does not fully
    understand would come out as a different shape.
    """
    if not _WHOLE.fullmatch(d):
        raise ValueError(f"path data outside absolute M L H V Q C Z with whole numbers: {d[:40]!r}")
    out, last = [], ""
    x = y = start_x = start_y = 0

    def emit(letter: str, values) -> None:
        nonlocal last
        text = _numbers(values)
        if letter == last and letter not in "Mz":
            out.append(text if text.startswith("-") else " " + text)
        else:
            out.append(letter + text)
        last = letter

    for command, arguments in _COMMAND.findall(d):
        if command == "Z":
            emit("z", ())
            x, y = start_x, start_y
            continue
        values = [int(v) for v in re.findall(r"-?\d+", arguments)]
        size = _ARITY[command]
        if not values or len(values) % size:
            raise ValueError(f"{command} takes {size} numbers at a time, got {len(values)}: {d[:40]!r}")
        for k in range(0, len(values), size):
            group = values[k:k + size]
            step = "L" if command == "M" and k else command      # points after a move are lines
            if step == "M":
                emit("M", group)
                x, y = start_x, start_y = group
            elif step == "H" or (step == "L" and group[1] == y):
                emit("h", (group[0] - x,))
                x = group[0]
            elif step == "V" or (step == "L" and group[0] == x):
                emit("v", (group[-1] - y,))
                y = group[-1]
            else:
                emit(step.lower(), [v - (x if i % 2 == 0 else y) for i, v in enumerate(group)])
                x, y = group[-2], group[-1]
    return "".join(out)
