"""View models: turn a data snapshot and the config into what each plate draws."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from generator.config import repo_key
from generator.data import Repo, Snapshot

# An arm lists technologies by the name people use; GitHub reports languages by another.
ALIASES = {"docker": "dockerfile", "vue.js": "vue", "node.js": "javascript"}
MIN_SHARE = 0.15          # a repository joins an arm when its languages are at least this much of its code
STAR_LIMIT = 48           # repositories drawn in the galaxy
FEATURED_LIMIT = 3
NOW_DAYS, YEAR_DAYS = 30, 365


def recency(pushed: date, today: date) -> str:
    """How alive a repository is: "now" (a month), "year", or "dorm"."""
    days = (today - pushed).days
    if days <= NOW_DAYS:
        return "now"
    return "year" if days <= YEAR_DAYS else "dorm"


def _tech(name: str) -> str:
    key = str(name).strip().lower()
    return ALIASES.get(key, key)


def _featured_keys(config: dict) -> set:
    return {repo_key(p["repo"]) for p in config.get("projects", [])}


def visible_repos(snap: Snapshot, config: dict, limit: int = STAR_LIMIT) -> list:
    """The repositories that become stars: no forks, no profile repository; featured ones first."""
    login = snap.login.lower()
    wanted = _featured_keys(config)
    repos = [r for r in snap.repos
             if not r.is_fork and not (r.owner.lower() == login and r.name.lower() == login)]
    repos.sort(key=lambda r: (repo_key(r.name) not in wanted, -r.stars, -r.pushed.toordinal(), r.name.lower()))
    return repos[:limit]


def _share_arm(repo: Repo, arm_techs: list) -> Optional[int]:
    total = sum(repo.languages.values())
    if total:
        shares = {_tech(lang): size / total for lang, size in repo.languages.items()}
    elif repo.primary_language:
        shares = {_tech(repo.primary_language): 1.0}      # REST gave no byte counts
    else:
        return None
    scores = [sum(share for lang, share in shares.items() if lang in techs) for techs in arm_techs]
    best = max(scores, default=0.0)
    return scores.index(best) if best >= MIN_SHARE else None


def assign_arms(repos: list, arms: list, projects: list) -> dict:
    """Arm index (or None) for every repository: explicit pins first, then share of code."""
    pinned = {}
    for project in projects:
        if "arm" in project:
            pinned[repo_key(project["repo"])] = project["arm"]
    for index, arm in enumerate(arms):
        for name in arm.get("repos", []):
            pinned[repo_key(name)] = index
    arm_techs = [{_tech(item) for item in arm.get("items", [])} for arm in arms]
    return {repo.name: pinned[repo_key(repo.name)] if repo_key(repo.name) in pinned else _share_arm(repo, arm_techs)
            for repo in repos}


@dataclass(frozen=True)
class Featured:
    name: str
    description: str
    language: Optional[str]
    stars: int
    pushed: date
    state: str


def featured(snap: Snapshot, config: dict) -> list:
    """Up to three featured projects, brightest first."""
    by_full_name = {(r.owner.lower(), r.name.lower()): r for r in snap.repos}
    items = []
    for project in config.get("projects", []):
        owner, _, name = str(project["repo"]).rpartition("/")
        repo = by_full_name.get(((owner or snap.login).lower(), name.lower()))
        if repo is None:
            continue
        items.append(Featured(
            name=repo.name,
            description=project.get("description") or repo.description,
            language=repo.primary_language,
            stars=repo.stars,
            pushed=repo.pushed,
            state=recency(repo.pushed, snap.today),
        ))
    items.sort(key=lambda f: -f.stars)
    return items[:FEATURED_LIMIT]


def language_shares(snap: Snapshot, exclude: list, max_display: int) -> list:
    """(language, percent) for the user's own non-fork repositories, largest first."""
    login, skip, totals = snap.login.lower(), set(exclude), {}
    for repo in snap.repos:
        if repo.is_fork or repo.owner.lower() != login:
            continue
        for lang, size in repo.languages.items():
            if lang not in skip:
                totals[lang] = totals.get(lang, 0) + size
    whole = sum(totals.values())
    if not whole:
        return []
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:max_display]
    return [(lang, round(size / whole * 100, 1)) for lang, size in ranked]


def weekly_series(snap: Snapshot) -> Optional[tuple]:
    """(values, first days, total, index of the peak week), or None without a calendar."""
    if not snap.weeks:
        return None
    dates = [day for day, _count in snap.weeks]
    values = [count for _day, count in snap.weeks]
    total = snap.total_contributions if snap.total_contributions is not None else sum(values)
    return values, dates, total, values.index(max(values))
