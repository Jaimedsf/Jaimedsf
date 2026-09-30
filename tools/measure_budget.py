"""Print the size of every generated SVG, raw and gzipped, against its budget.

    python tools/measure_budget.py
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from generator import build                                   # noqa: E402
from generator.config import validate_config                  # noqa: E402
from generator.data import load_demo                          # noqa: E402

BUDGETS = {"galaxy-header": 110_000, "stats-card": 48_000, "tech-stack": 48_000,
           "projects-constellation": 48_000}


def report(name: str, svg: str, budget: int) -> bool:
    raw = len(svg.encode("utf-8"))
    packed = len(gzip.compress(svg.encode("utf-8")))
    ok = raw <= budget
    print(f"{name:42} {raw / 1024:7.1f} KB raw  {packed / 1024:6.1f} KB gzip  "
          f"budget {budget / 1024:.0f} KB  {'ok' if ok else 'OVER'}")
    return ok


def main() -> int:
    with open(ROOT / "config.example.yml", encoding="utf-8") as handle:
        config = validate_config(yaml.safe_load(handle))
    ok = True
    for name, svg in sorted(build.render_all(config, load_demo()).items()):
        ok &= report(name, svg, BUDGETS[name.split(".")[0].replace("-mobile", "").replace("-light", "")])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
