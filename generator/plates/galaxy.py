"""The galaxy: a face-on logarithmic spiral drawn from the profile's repositories.

The arms are made of loose particles that stream along them while the shape
of the spiral stays still. That works because a logarithmic spiral maps onto
itself under a rotation by phi combined with a scale of e^(b*phi): each layer
of particles is one 60-degree tile repeated in rotated, scaled copies, and
animating the group through one step of that transform moves every copy onto
the next. One animated element moves thousands of particles, and the loop has
no seam.

A particle's size is proportional to its distance from the core. The same
symmetry requires it, and it keeps the image coherent under any zoom.
"""

from __future__ import annotations

import math

from generator.svg import dots, dots_d, num

PHI = math.pi / 3                 # tile step along an arm
R0 = 20.0                         # radius where the spiral starts
TURNS = 1.5                       # turns from R0 to the rim
FLOW_STEPS = 4                    # keyframes per loop; keeps the scale close to exponential

# particles per tile, seconds per loop, inner cut, outer cut (fractions of the radius), size multiplier
LAYERS = ((95, 22, 0.0, 1.0, 1.0), (75, 29, 0.0, 0.6, 1.8), (75, 25, 0.4, 1.0, 1.0))
# diameter as a fraction of the tile's radius, share of the particles, opacity, bloom
SIZES = ((0.0085, 0.55, 0.9, False), (0.014, 0.28, 1.0, False), (0.022, 0.13, 1.0, True), (0.034, 0.04, 1.0, True))
BULGE_SIZES = (1.0, 1.7, 2.5, 3.6)                     # pixels; the bulge does not flow, so it has no tile
BLOOM = ((3.3, 0.035), (2.6, 0.07), (2.0, 0.13), (1.5, 0.26))   # width multiplier, opacity
OFF_AXIS = 0.085                  # further than this from the arm's axis, a particle is always small
CLUSTERS = 8


class Geometry:
    """Where things are: the frame, the core, the spiral."""

    def __init__(self, mobile: bool, arms: int) -> None:
        self.width, self.height = (390, 478) if mobile else (850, 430)
        self.cx, self.cy, self.radius = (195, 282, 172) if mobile else (630, 215, 196)
        self.arms = max(arms, 1)
        self.b = math.log(self.radius / R0) / (TURNS * 2 * math.pi)
        self.k = math.exp(self.b * PHI)

    def angle(self, arm: int) -> float:
        """The direction in which an arm leaves the core, in radians."""
        return math.radians(35) + arm * 2 * math.pi / self.arms

    def plane(self, arm: int, r: float, stretch: float = 1.0) -> tuple:
        """The point of an arm at distance r from the core, relative to the core."""
        a = self.angle(arm) + math.log(r / R0) / self.b
        return r * stretch * math.cos(a), r * stretch * math.sin(a)

    def point(self, arm: int, r: float, stretch: float = 1.0) -> tuple:
        """The same point in the frame's coordinates."""
        x, y = self.plane(arm, r, stretch)
        return self.cx + x, self.cy + y

    def copy(self, j: int) -> tuple:
        """(degrees, scale) that place the j-th copy of the rim tile; j is 0 at the rim and negative inward."""
        return math.degrees(j * PHI), self.k ** j

    def flow(self, q: float) -> tuple:
        """(degrees, scale) of the flow transform at fraction q of a loop."""
        return math.degrees(PHI * q), math.exp(self.b * PHI * q)


def _pick(rng, table):
    roll, acc = rng.random(), 0.0
    for item, share in table:
        acc += share
        if roll <= acc:
            return item
    return table[-1][0]


def _field(buckets: dict, glow: float, ids: list) -> str:
    """Particles grouped by colour and size. Bright ones share one coordinate list with their bloom."""
    out = []
    for (colour, width, opacity, bloom), points in sorted(buckets.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if not bloom:
            out.append(dots(points, width, colour, opacity))
            continue
        ids[0] += 1
        out.append(f'<defs><path id="d{ids[0]}" d="{dots_d(points)}"/></defs>'
                   f'<g stroke="{colour}" stroke-linecap="round" fill="none">'
                   + "".join(f'<use href="#d{ids[0]}" stroke-width="{num(width * m, 2)}" stroke-opacity="{num(a * glow, 3)}"/>'
                             for m, a in BLOOM)
                   + f'<use href="#d{ids[0]}" stroke-width="{num(width, 2)}"/></g>')
    return "".join(out)


def _tile(geo: Geometry, arm: int, count: int, multiplier: float, theme, rng) -> dict:
    """One 60-degree stretch of an arm at the rim, as {(colour, width, opacity, bloom): [points]}."""
    start = TURNS * 2 * math.pi - PHI                       # the tile covers the last PHI of the arm
    mid_radius = geo.radius * math.exp(-geo.b * PHI / 2)
    clusters = [(rng.uniform(0, PHI), rng.gauss(0, 0.05)) for _ in range(CLUSTERS)]
    sizes = [(size, size[1]) for size in SIZES]
    buckets = {}
    for _ in range(count):
        if rng.random() < 0.45:
            centre, offset = rng.choice(clusters)
            s, delta = centre + rng.gauss(0, 0.05), offset + rng.gauss(0, 0.03)
        else:
            s, delta = rng.uniform(0, PHI), rng.gauss(0, 0.16 if rng.random() < 0.2 else 0.055)
        s %= PHI
        size, _share, opacity, bloom = _pick(rng, sizes)
        if abs(delta) > OFF_AXIS:
            size, _share, opacity, bloom = SIZES[0] if rng.random() < 0.7 else SIZES[1]
        r = R0 * math.exp(geo.b * (start + s)) * (1 + delta)
        a = geo.angle(arm) + start + s
        key = (_pick(rng, theme.dust), round(size * multiplier * mid_radius, 2), opacity, bloom)
        buckets.setdefault(key, []).append((r * math.cos(a), r * math.sin(a)))
    return buckets


def dust(geo: Geometry, cuts: list, theme, rng, motion) -> tuple:
    """(defs, body) of the particle field, in coordinates relative to the core.

    cuts is the radius where each arm ends. Each arm has three layers of
    particles flowing at different speeds, each layer behind a radial mask
    that fades it in and out; then comes the dense bulge at the core.
    """
    frames = "".join(
        f"{num(100 * q / FLOW_STEPS)}%{{transform:rotate({num(geo.flow(q / FLOW_STEPS)[0], 2)}deg) "
        f"scale({num(geo.flow(q / FLOW_STEPS)[1], 4)})}}" for q in range(FLOW_STEPS + 1))
    motion.define("flow", f".flow{{animation:flow 22s linear infinite}}@keyframes flow{{{frames}}}")

    defs, body, ids, R = [], [], [0], geo.radius
    for arm, cut in enumerate(cuts):
        for layer, (count, seconds, inner, outer, multiplier) in enumerate(LAYERS):
            r_lo, r_hi = inner * R, min(outer * R, cut) * 1.04
            if r_lo >= r_hi * 0.9:
                continue
            tile = f"t{arm}{layer}"
            defs.append(f'<g id="{tile}">{_field(_tile(geo, arm, count, multiplier, theme, rng), theme.glow, ids)}</g>')
            # only the copies that can show inside this band at some point of a loop
            copies = []
            j = 0
            while R * geo.k ** j >= R0 * 0.7:
                if R * geo.k ** (j + 1) > r_lo * 0.85 and R * geo.k ** (j - 1) < r_hi:
                    degrees, scale = geo.copy(j)
                    copies.append(f'<use href="#{tile}" transform="rotate({num(degrees, 2)}) scale({num(scale, 4)})"/>')
                j -= 1
            fade_in = ('<stop offset="0" stop-color="#fff"/>' if not r_lo else
                       f'<stop offset="{num(max(r_lo - R * 0.1, 0) / r_hi, 3)}" stop-color="#fff" stop-opacity="0"/>'
                       f'<stop offset="{num(r_lo / r_hi, 3)}" stop-color="#fff"/>')
            side = num(r_hi)
            defs.append(
                f'<radialGradient id="g{arm}{layer}" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="{side}">{fade_in}'
                f'<stop offset=".8" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
                f'<mask id="m{arm}{layer}" maskUnits="userSpaceOnUse" x="-{side}" y="-{side}" width="{num(r_hi * 2)}" '
                f'height="{num(r_hi * 2)}"><circle r="{side}" fill="url(#g{arm}{layer})"/></mask>')
            phase = rng.uniform(0, seconds)                 # drawn whether or not motion is on
            body.append(f'<g mask="url(#m{arm}{layer})"><g{motion.cls("flow", delay=-phase, duration=seconds)}>'
                        f'{"".join(copies)}</g></g>')

    sizes = [(index, size[1]) for index, size in enumerate(SIZES)]
    bulge = {}
    for _ in range(320):
        a, r = rng.uniform(0, 2 * math.pi), abs(rng.gauss(0, R * 0.095))
        index = _pick(rng, sizes)
        key = (_pick(rng, theme.dust), BULGE_SIZES[index], SIZES[index][2], SIZES[index][3])
        bulge.setdefault(key, []).append((r * math.cos(a), r * math.sin(a)))
    body.append(f'<g{motion.cls("swirl")}>{_field(bulge, theme.glow, ids)}</g>')
    return "".join(defs), "".join(body)
