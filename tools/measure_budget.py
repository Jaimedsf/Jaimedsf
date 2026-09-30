"""Print the size of every generated SVG, raw and gzipped, against its budget.

    python tools/measure_budget.py

Until the galaxy plate exists, it also sizes a prototype of its particle
field: the same number of particles, tiles, bloom layers and entrance actors
the approved mockup had, written with the real primitives.
"""

from __future__ import annotations

import gzip
import math
import random
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generator import build                                   # noqa: E402
from generator.config import validate_config                  # noqa: E402
from generator.data import load_demo                          # noqa: E402
from generator.motion import Motion                           # noqa: E402
from generator.svg import dots, dots_d, frame, num, star, star_defs   # noqa: E402
from generator.themes import get_theme                        # noqa: E402
from generator.typeset import Typesetter                      # noqa: E402

BUDGETS = {"galaxy-header": 110_000, "stats-card": 48_000, "tech-stack": 48_000,
           "projects-constellation": 48_000}


def report(name: str, svg: str, budget: int) -> bool:
    raw = len(svg.encode("utf-8"))
    packed = len(gzip.compress(svg.encode("utf-8")))
    ok = raw <= budget
    print(f"{name:42} {raw / 1024:7.1f} KB raw  {packed / 1024:6.1f} KB gzip  "
          f"budget {budget / 1024:.0f} KB  {'ok' if ok else 'OVER'}")
    return ok


def header_prototype() -> str:
    """A stand-in for the galaxy header with the approved mockup's particle counts."""
    theme, motion, ts = get_theme("deep-sky", "dark"), Motion(), Typesetter()
    rng = random.Random("budget")
    radius, r0, turns = 196.0, 20.0, 1.5
    b = math.log(radius / r0) / (turns * 2 * math.pi)
    phi = math.pi / 3                                   # 60-degree tiles: size steps of 1.29x between copies
    k = math.exp(b * phi)
    sizes = ((.0085, .55, .9, False), (.014, .28, 1, False), (.022, .13, 1, True), (.034, .04, 1, True))
    defs, body, pid = [star_defs(theme)], [], 0

    def field(points_by_bucket):
        nonlocal pid
        out = []
        for (colour, width, opacity, glow), points in points_by_bucket.items():
            if not glow:
                out.append(dots(points, width, colour, opacity))
                continue
            pid += 1
            out.append(f'<defs><path id="d{pid}" d="{dots_d(points)}"/></defs>'
                       f'<g stroke="{colour}" stroke-linecap="round" fill="none">'
                       + "".join(f'<use href="#d{pid}" stroke-width="{num(width * m, 2)}" stroke-opacity="{num(a, 2)}"/>'
                                 for m, a in ((2.6, .07), (1.8, .16), (1, opacity))) + "</g>")
        return "".join(out)

    def bucketed(count, place, scale_width):
        buckets = {}
        for _ in range(count):
            roll, acc = rng.random(), 0.0
            for size, share, opacity, glow in sizes:
                acc += share
                if roll <= acc:
                    break
            colour = rng.choices([c for c, _w in theme.dust], [w for _c, w in theme.dust])[0]
            buckets.setdefault((colour, round(scale_width(size), 2), opacity, glow), []).append(place())
        return buckets

    for arm in range(2):
        for layer, count in enumerate((95, 75, 75)):
            def on_arm():
                s = rng.uniform(0, phi)
                r = r0 * math.exp(b * s) * (1 + rng.gauss(0, .07))
                return r * math.cos(arm * math.pi + s), r * math.sin(arm * math.pi + s)
            tile = f"t{arm}{layer}"
            defs.append(f'<g id="{tile}">{field(bucketed(count, on_arm, lambda size: size * r0 * 1.14))}</g>')
            copies = "".join(f'<use href="#{tile}" transform="rotate({num(math.degrees(j * phi), 2)}) '
                             f'scale({num(k ** j, 4)})"/>' for j in range(-1, 9))
            body.append(f'<g class="flow" style="animation-duration:{44 + layer * 7}s">{copies}</g>')

    def in_bulge():
        a, r = rng.uniform(0, 2 * math.pi), abs(rng.gauss(0, radius * .095))
        return r * math.cos(a), r * math.sin(a)
    body.append(field(bucketed(320, in_bulge, lambda size: size * 110)))

    for group in range(14):                              # entrance actors, motion only
        def anywhere():
            a, r = rng.uniform(0, 2 * math.pi), rng.uniform(20, radius)
            return r * math.cos(a), r * math.sin(a)
        body.append(f'<g class="a{group}">{field(bucketed(48, anywhere, lambda size: size * 80))}</g>')
        motion.add(f".a{group}{{animation:a{group} 3.6s linear .2s both}}@keyframes a{group}{{0%{{opacity:0;"
                   f"transform:rotate(-200deg) scale(2.9)}}12%{{opacity:1}}40%{{transform:rotate(-186deg) scale(2.8)}}"
                   f"78%{{transform:rotate(-40deg) scale(.5)}}100%{{opacity:1;transform:rotate(0deg) scale(1)}}}}")

    stars = "".join(f'<g transform="translate({num(rng.uniform(-180, 180))} {num(rng.uniform(-180, 180))})">'
                    f'{star(rng.choice((0, 1, 4, 12, 480)), rng.choice(("now", "year", "dorm")), theme, motion)}</g>'
                    for _ in range(13))
    sky = "".join(f'<circle cx="{num(rng.uniform(8, 842))}" cy="{num(rng.uniform(8, 422))}" '
                  f'r="{num(rng.uniform(.35, .9), 2)}" opacity="{num(rng.uniform(.18, .6), 2)}"/>' for _ in range(80))
    text = (ts.line(44, 196, "Vinícius Melo", 48, theme.ink, "light")
            + ts.line(45, 228, "AI Engineer", 20, theme.mute, "italic")
            + ts.line(45, 274, "Solving one problem at a time,", 14.5, theme.mute, "italic")
            + ts.line(45, 293, "with code and creativity.", 14.5, theme.mute, "italic")
            + "".join(ts.line(500 + 40 * i, 100 + 60 * i, name, 13.5, theme.ink, "medium")
                      for i, name in enumerate(("tabAla", "gaeia", "galaxy-profile")))
            + ts.line(600, 60, "Web & Cloud", 13.5, theme.mute, "italic")
            + ts.line(480, 300, "AI & Data", 13.5, theme.mute, "italic"))
    defs.append(ts.defs())
    return frame(theme, 850, 430, f'<g fill="{theme.haze}">{sky}</g><g transform="translate(630 215)">'
                 f'{"".join(body)}</g><g transform="translate(630 215)">{stars}</g>{text}',
                 "Galaxy header prototype", "Size estimate only", "".join(defs), motion)


def main() -> int:
    with open(ROOT / "config.example.yml", encoding="utf-8") as handle:
        config = validate_config(yaml.safe_load(handle))
    ok = True
    for name, svg in sorted(build.render_all(config, load_demo()).items()):
        ok &= report(name, svg, BUDGETS[name.split(".")[0].replace("-mobile", "").replace("-light", "")])
    if "galaxy-header" not in build.RENDERERS:
        ok &= report("galaxy-header (prototype, not the plate)", header_prototype(), BUDGETS["galaxy-header"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
