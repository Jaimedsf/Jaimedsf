"""Write generator/demo_data.json: the fictional profile behind --demo.

It has the exact shape of the GitHub GraphQL response the generator asks for,
plus a fixed "today", so demo output never changes from one run to the next.

    python tools/build_demo_data.py
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "generator" / "demo_data.json"
LOGIN = "galaxy-dev"
TODAY = date(2026, 9, 30)

# name, stars, created, pushed, description, languages (bytes), topics, fork
REPOS = [
    ("nebula-ui", 1240, "2023-03-14", "2026-09-22",
     "A component library with cosmic design tokens and dark-first theming.",
     {"TypeScript": 610000, "CSS": 240000, "JavaScript": 30000}, ["design-system", "react"], False),
    ("stargate-api", 486, "2022-08-02", "2026-09-27",
     "High-performance API gateway with built-in observability and caching.",
     {"Python": 520000, "Shell": 20000, "Dockerfile": 8000}, ["api-gateway"], False),
    ("orbit-cli", 212, "2021-11-20", "2026-06-11", "Command-line companion for the Stellar Labs platform.",
     {"Go": 300000, "Shell": 12000}, ["cli"], False),
    ("quasar-charts", 97, "2024-02-09", "2026-09-05", "Charts that read well at a glance.",
     {"TypeScript": 410000, "CSS": 60000}, ["dataviz"], False),
    ("pulsar-queue", 64, "2023-10-01", "2026-03-18", "A small, fast job queue.",
     {"Python": 280000}, [], False),
    ("comet-deploy", 41, "2024-06-23", "2026-08-30", "Opinionated deploy scripts for small teams.",
     {"Shell": 90000, "Dockerfile": 60000, "HCL": 50000}, ["devops"], False),
    ("dark-matter-css", 33, "2022-04-12", "2024-01-15", "A CSS reset for dark interfaces.",
     {"CSS": 90000}, [], False),
    ("lightcurve", 28, "2025-01-07", "2026-09-29", "Time-series tools for noisy signals.",
     {"Python": 150000, "Jupyter Notebook": 40000}, [], False),
    ("redshift-orm", 19, "2021-05-30", "2023-02-02", "An ORM experiment.",
     {"Python": 120000}, [], False),
    ("star-map", 12, "2025-05-16", "2026-07-04", "Interactive sky charts in the browser.",
     {"TypeScript": 96000, "CSS": 9000}, [], False),
    ("telescope-action", 9, "2025-09-02", "2026-09-18", "A GitHub Action that watches your builds.",
     {"TypeScript": 30000, "Dockerfile": 12000, "Shell": 8000}, ["github-actions"], False),
    ("galaxy-dev", 6, "2020-01-01", "2026-09-30", "Profile README.",
     {"Python": 40000}, [], False),
    ("parallax-notes", 4, "2020-09-09", "2021-01-01", "Notes from a parallax workshop.",
     {}, [], False),
    ("wormhole", 3, "2024-11-11", "2026-02-02", "Peer-to-peer file tunnels.",
     {"Rust": 70000}, [], False),
    ("aphelion", 2, "2026-03-03", "2026-09-10", "A tiny orbital mechanics simulator.",
     {"Rust": 54000, "Python": 5000}, [], False),
    ("nyx-dotfiles", 1, "2019-12-01", "2026-05-05", "Dotfiles.",
     {"Shell": 22000, "Lua": 14000}, [], False),
    ("react", 0, "2024-05-05", "2024-05-06", "A fork.", {"JavaScript": 900000}, [], True),
    ("cpython", 0, "2023-02-02", "2023-02-03", "A fork.", {"Python": 900000, "C": 600000}, [], True),
]


def _repo(row) -> dict:
    name, stars, created, pushed, description, languages, topics, fork = row
    edges = [{"size": size, "node": {"name": lang}}
             for lang, size in sorted(languages.items(), key=lambda kv: -kv[1])]
    return {
        "name": name,
        "nameWithOwner": f"{LOGIN}/{name}",
        "isFork": fork,
        "stargazerCount": stars,
        "createdAt": f"{created}T12:00:00Z",
        "pushedAt": f"{pushed}T12:00:00Z",
        "description": description,
        "primaryLanguage": {"name": edges[0]["node"]["name"]} if edges else None,
        "languages": {"totalSize": sum(languages.values()), "edges": edges},
        "repositoryTopics": {"nodes": [{"topic": {"name": t}} for t in topics]},
    }


def _calendar() -> dict:
    """53 weeks ending in the week of TODAY: a rising year with two bursts and a quiet holiday."""
    rng = random.Random("galaxy-dev demo")
    start = TODAY - timedelta(days=(TODAY.weekday() + 1) % 7) - timedelta(weeks=52)   # a Sunday
    weeks, total = [], 0
    for w in range(53):
        level = 3.5 + 5.5 * w / 52
        if w in (11, 12):                       # year-end break
            level *= 0.15
        if 24 <= w <= 27 or w >= 49:            # a launch in spring and one now
            level *= 2.3
        days = []
        for d in range(7):
            day = start + timedelta(weeks=w, days=d)
            if day > TODAY:
                break
            weekday_factor = 0.35 if d in (0, 6) else 1.0
            count = max(0, round(rng.gauss(level * weekday_factor, level * 0.45)))
            total += count
            days.append({"date": day.isoformat(), "contributionCount": count})
        weeks.append({"contributionDays": days})
    return {"totalContributions": total, "weeks": weeks}


def build() -> dict:
    return {
        "today": TODAY.isoformat(),
        "data": {
            "user": {
                "login": LOGIN,
                "pullRequests": {"totalCount": 156},
                "issues": {"totalCount": 89},
                "contributionsCollection": {"contributionCalendar": _calendar()},
                "repositories": {"totalCount": len(REPOS), "nodes": [_repo(row) for row in REPOS]},
            }
        },
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    calendar = build()["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    print(f"{OUT.name}: {len(REPOS)} repositories, {len(calendar['weeks'])} weeks, "
          f"{calendar['totalContributions']} contributions")
