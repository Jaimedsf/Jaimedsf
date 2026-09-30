"""Fetch a GitHub profile and return one snapshot of it, whatever the source.

With a token, a single GraphQL query brings repositories (with languages,
topics, dates and stars), the contribution calendar and the counters. Without
one, REST gives everything except the calendar. The demo fixture is a stored
GraphQL payload, so it runs through the same code as real data.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"
DEMO_FILE = Path(__file__).resolve().parent / "demo_data.json"

_REPO_FRAGMENT = """
fragment repo on Repository {
  name nameWithOwner isFork stargazerCount createdAt pushedAt description
  primaryLanguage { name }
  languages(first: 12, orderBy: {field: SIZE, direction: DESC}) { totalSize edges { size node { name } } }
  repositoryTopics(first: 12) { nodes { topic { name } } }
}"""


class DataError(RuntimeError):
    """The profile could not be read."""


@dataclass(frozen=True)
class Repo:
    name: str
    owner: str
    stars: int
    created: date
    pushed: date
    description: str
    primary_language: Optional[str]
    languages: dict            # language name -> bytes
    topics: tuple
    is_fork: bool


@dataclass(frozen=True)
class Snapshot:
    login: str
    repos: tuple               # Repo, the user's own first, then featured repositories of other owners
    weeks: Optional[tuple]     # ((first day, contributions), ...) or None without a calendar
    total_contributions: Optional[int]
    counters: dict             # stars, prs, issues, repos
    today: date


def _day(stamp: str) -> date:
    return date.fromisoformat(stamp[:10])


def _repo_from_graphql(node: dict) -> Repo:
    owner, _, name = node["nameWithOwner"].partition("/")
    return Repo(
        name=name,
        owner=owner,
        stars=node["stargazerCount"],
        created=_day(node["createdAt"]),
        pushed=_day(node["pushedAt"] or node["createdAt"]),
        description=node.get("description") or "",
        primary_language=(node.get("primaryLanguage") or {}).get("name"),
        languages={edge["node"]["name"]: edge["size"] for edge in node["languages"]["edges"]},
        topics=tuple(t["topic"]["name"] for t in node["repositoryTopics"]["nodes"]),
        is_fork=node["isFork"],
    )


def build_query(login: str, extra_repos: list) -> tuple:
    """The GraphQL query and its variables. extra_repos are "owner/name" featured projects."""
    declared, aliases, variables = ["$login: String!"], [], {"login": login}
    for i, full_name in enumerate(extra_repos):
        owner, _, name = full_name.rpartition("/")
        declared += [f"$o{i}: String!", f"$n{i}: String!"]
        aliases.append(f"  x{i}: repository(owner: $o{i}, name: $n{i}) {{ ...repo }}")
        variables[f"o{i}"], variables[f"n{i}"] = owner or login, name
    query = f"""query({", ".join(declared)}) {{
  user(login: $login) {{
    login
    pullRequests {{ totalCount }}
    issues {{ totalCount }}
    contributionsCollection {{
      contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
    }}
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, first: 100,
                 orderBy: {{field: STARGAZERS, direction: DESC}}) {{
      totalCount
      nodes {{ ...repo }}
    }}
  }}
{chr(10).join(aliases)}
}}{_REPO_FRAGMENT}"""
    return query, variables


def from_graphql(payload: dict, today: date, login: Optional[str] = None) -> Snapshot:
    """Turn a GraphQL response into a snapshot."""
    body = payload.get("data") or {}
    user = body.get("user")
    if not user:
        raise DataError(f"GitHub has no user '{login or '?'}' (or the token cannot see it).")
    owned = [_repo_from_graphql(node) for node in user["repositories"]["nodes"]]
    seen = {(r.owner, r.name) for r in owned}
    extras = []
    for key in sorted(k for k in body if k != "user"):
        node = body[key]
        if not node:
            continue
        repo = _repo_from_graphql(node)
        if (repo.owner, repo.name) not in seen:
            seen.add((repo.owner, repo.name))
            extras.append(repo)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    weeks = tuple(
        (_day(week["contributionDays"][0]["date"]), sum(d["contributionCount"] for d in week["contributionDays"]))
        for week in calendar["weeks"] if week["contributionDays"]
    )
    return Snapshot(
        login=user["login"],
        repos=tuple(owned + extras),
        weeks=weeks,
        total_contributions=calendar["totalContributions"],
        counters={
            "stars": sum(r.stars for r in owned),
            "prs": user["pullRequests"]["totalCount"],
            "issues": user["issues"]["totalCount"],
            "repos": user["repositories"]["totalCount"],
        },
        today=today,
    )


def from_rest(login: str, user: dict, repos: list, languages: dict, prs: int, issues: int,
              today: date) -> Snapshot:
    """Turn REST responses into a snapshot. languages maps repo name -> {language: bytes}."""
    built = tuple(
        Repo(
            name=r["name"],
            owner=r["owner"]["login"],
            stars=r.get("stargazers_count", 0),
            created=_day(r["created_at"]),
            pushed=_day(r.get("pushed_at") or r["created_at"]),
            description=r.get("description") or "",
            primary_language=r.get("language"),
            languages=dict(languages.get(r["name"], {})),
            topics=tuple(r.get("topics") or ()),
            is_fork=bool(r.get("fork")),
        )
        for r in repos
    )
    return Snapshot(
        login=login,
        repos=built,
        weeks=None,
        total_contributions=None,
        counters={
            "stars": sum(r.stars for r in built),
            "prs": prs,
            "issues": issues,
            "repos": user.get("public_repos", len(built)),
        },
        today=today,
    )


def _request(http, method: str, url: str, token: str, **kwargs):
    """One HTTP call; waits out a rate limit once."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    kwargs.setdefault("timeout", 20)
    response = http.request(method, url, headers=headers, **kwargs)
    if response.status_code == 403 and "rate limit" in response.text.lower():
        reset = int(response.headers.get("X-RateLimit-Reset", 0))
        wait = max(reset - int(time.time()), 1)
        logger.warning("GitHub rate limit reached; waiting %ds.", wait)
        time.sleep(min(wait, 120))
        response = http.request(method, url, headers=headers, **kwargs)
    return response


def _fetch_rest(http, login: str, token: str, today: date) -> Snapshot:
    user = _request(http, "GET", f"{REST_URL}/users/{login}", token)
    if user.status_code == 404:
        raise DataError(f"GitHub has no user '{login}'.")
    user.raise_for_status()
    repos, page = [], 1
    while True:
        batch = _request(http, "GET", f"{REST_URL}/users/{login}/repos", token,
                         params={"per_page": 100, "page": page, "type": "owner"})
        batch.raise_for_status()
        items = batch.json()
        repos += items
        if len(items) < 100:
            break
        page += 1
    languages = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        response = _request(http, "GET", f"{REST_URL}/repos/{login}/{repo['name']}/languages", token)
        if response.status_code == 200:
            languages[repo["name"]] = response.json()
        else:
            logger.warning("Could not read languages of %s (HTTP %d).", repo["name"], response.status_code)

    def count(kind: str) -> int:
        response = _request(http, "GET", f"{REST_URL}/search/issues", token,
                            params={"q": f"author:{login} type:{kind}", "per_page": 1})
        return response.json().get("total_count", 0) if response.status_code == 200 else 0

    return from_rest(login, user.json(), repos, languages, count("pr"), count("issue"), today)


def fetch(login: str, token: str, extra_repos: list, today: date, http=requests) -> Snapshot:
    """Read a profile from GitHub: GraphQL with a token, REST without (or if GraphQL fails)."""
    if token:
        query, variables = build_query(login, extra_repos)
        try:
            response = _request(http, "POST", GRAPHQL_URL, token, json={"query": query, "variables": variables})
            response.raise_for_status()
            payload = response.json()
        except (requests.exceptions.RequestException, RuntimeError, ValueError) as error:
            logger.warning("GraphQL request failed (%s); falling back to REST.", error)
        else:
            # a featured repository that does not exist comes back as an error next to valid data
            if payload.get("data", {}).get("user"):
                return from_graphql(payload, today, login)
            logger.warning("GraphQL returned no user (%s); falling back to REST.", payload.get("errors"))
    return _fetch_rest(http, login, token, today)


def load_demo() -> Snapshot:
    """The fictional profile used by --demo, the README images and the tests."""
    payload = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
    return from_graphql(payload, date.fromisoformat(payload["today"]))
