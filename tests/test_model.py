"""View models: which repositories are drawn, which arm each sits on, and what the plates show."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from generator.data import Repo, Snapshot
from generator.model import (assign_arms, featured, language_shares, recency, visible_repos,
                             weekly_series)

TODAY = date(2026, 9, 30)
ARMS = [
    {"name": "AI & Data", "items": ["Python", "PyTorch", "MySQL"]},
    {"name": "Web & Cloud", "items": ["TypeScript", "React", "Flask", "AWS / Oracle"]},
    {"name": "Automation", "items": ["Docker", "Linux", "GitHub Actions"]},
]


def make(name, stars=0, languages=None, primary="__first__", owner="ada", fork=False,
         pushed=TODAY, created=date(2024, 1, 1), description=""):
    languages = languages or {}
    if primary == "__first__":
        primary = next(iter(languages), None)
    return Repo(name=name, owner=owner, stars=stars, created=created, pushed=pushed, description=description,
                primary_language=primary, languages=languages, topics=(), is_fork=fork)


def snapshot(repos=(), weeks=None, total=None, login="ada"):
    return Snapshot(login=login, repos=tuple(repos), weeks=weeks, total_contributions=total,
                    counters={"stars": 0, "prs": 0, "issues": 0, "repos": len(repos)}, today=TODAY)


def thirteen():
    nodes = json.loads((Path(__file__).parent / "fixtures" / "matching_13_repos.json").read_text(
        encoding="utf-8"))["data"]["user"]["repositories"]["nodes"]
    return [make(n["name"], n["stargazerCount"],
                 {e["node"]["name"]: e["size"] for e in n["languages"]["edges"]},
                 primary=(n["primaryLanguage"] or {}).get("name"), owner="vinimlo") for n in nodes]


# ── arm matching (spec D04, test T8) ─────────────────────────────────────────

def test_share_rule_on_thirteen_real_repositories_leaves_three_loose():
    arms = assign_arms(thirteen(), ARMS, [])
    loose = sorted(name for name, arm in arms.items() if arm is None)
    assert loose == ["cosmos-universe-ai", "cses", "macweep"]
    assert len(arms) == 13


def test_share_rule_places_mixed_repositories_by_their_largest_matching_share():
    arms = assign_arms(thirteen(), ARMS, [])
    assert arms["dashboard-smar-pd3"] == 0       # Vue 48%, but Python 38% is the arm language
    assert arms["cosmos"] == 1                   # Astro 46%, TypeScript 36%
    assert arms["galaxy-profile"] == 0 and arms["tabAla"] == 1


def test_share_of_exactly_the_threshold_is_enough():
    repo = make("edge", languages={"Python": 15, "Haskell": 85}, primary="Haskell")
    assert assign_arms([repo], ARMS, [])["edge"] == 0


def test_share_just_below_the_threshold_stays_loose():
    repo = make("edge", languages={"Python": 149, "Haskell": 851}, primary="Haskell")
    assert assign_arms([repo], ARMS, [])["edge"] is None


def test_tie_goes_to_the_first_arm():
    repo = make("both", languages={"Python": 50, "TypeScript": 50})
    assert assign_arms([repo], ARMS, [])["both"] == 0


def test_tool_names_match_their_language_through_the_alias_table():
    repo = make("deploy", languages={"Dockerfile": 30, "HCL": 70}, primary="HCL")
    assert assign_arms([repo], ARMS, [])["deploy"] == 2


def test_project_arm_wins_over_the_share_rule():
    repos = thirteen()
    arms = assign_arms(repos, ARMS, [{"repo": "vinimlo/macweep", "arm": 2}])
    assert arms["macweep"] == 2


def test_a_project_without_an_arm_does_not_pin_anything():
    repo = make("site", languages={"TypeScript": 100})
    assert assign_arms([repo], ARMS, [{"repo": "ada/site"}])["site"] == 1


def test_arm_repos_list_pins_a_repository_and_beats_the_project_arm():
    arms_cfg = [dict(a) for a in ARMS]
    arms_cfg[2]["repos"] = ["CSES"]
    arms = assign_arms(thirteen(), arms_cfg, [{"repo": "vinimlo/cses", "arm": 0}])
    assert arms["cses"] == 2


def test_repository_without_language_data_falls_back_to_its_primary_language():
    repo = make("rest-only", languages={}, primary="TypeScript")
    assert assign_arms([repo], ARMS, [])["rest-only"] == 1


def test_repository_with_no_language_at_all_stays_loose():
    repo = make("empty", languages={}, primary=None)
    assert assign_arms([repo], ARMS, [])["empty"] is None


# ── which repositories become stars ──────────────────────────────────────────

def test_forks_and_the_profile_repository_are_left_out():
    snap = snapshot([make("engine", 5), make("loom", 9, fork=True), make("Ada", 3)])
    assert [r.name for r in visible_repos(snap, {"projects": []})] == ["engine"]


def test_order_is_featured_first_then_stars_then_latest_push():
    old, new = TODAY - timedelta(days=400), TODAY
    snap = snapshot([make("a", 5, pushed=old), make("b", 5, pushed=new), make("c", 50), make("pet", 0)])
    names = [r.name for r in visible_repos(snap, {"projects": [{"repo": "ada/pet"}]})]
    assert names == ["pet", "c", "b", "a"]


def test_limit_keeps_featured_repositories_even_without_stars():
    repos = [make(f"r{i}", 100 - i) for i in range(60)] + [make("pet", 0)]
    shown = visible_repos(snapshot(repos), {"projects": [{"repo": "pet"}]}, limit=48)
    assert len(shown) == 48 and shown[0].name == "pet"


def test_featured_repository_of_another_owner_is_shown():
    snap = snapshot([make("engine", 5), make("difference", 900, owner="babbage")])
    names = [r.name for r in visible_repos(snap, {"projects": [{"repo": "babbage/difference"}]})]
    assert names == ["difference", "engine"]


# ── recency ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days, state", [(0, "now"), (30, "now"), (31, "year"), (365, "year"), (366, "dorm")])
def test_recency_thresholds(days, state):
    assert recency(TODAY - timedelta(days=days), TODAY) == state


# ── featured projects ────────────────────────────────────────────────────────

def test_featured_are_ordered_by_stars_and_carry_the_repositorys_data():
    snap = snapshot([make("small", 4, {"TypeScript": 1}), make("big", 40, {"Python": 1}, pushed=TODAY - timedelta(days=90))])
    items = featured(snap, {"projects": [{"repo": "ada/small", "description": "S"}, {"repo": "ada/big", "description": "B"}]})
    assert [(f.name, f.stars, f.language, f.state, f.description) for f in items] == [
        ("big", 40, "Python", "year", "B"), ("small", 4, "TypeScript", "now", "S")]


def test_featured_description_falls_back_to_the_repositorys_own():
    snap = snapshot([make("engine", 1, description="From GitHub")])
    assert featured(snap, {"projects": [{"repo": "engine"}]})[0].description == "From GitHub"


def test_featured_skips_projects_missing_from_the_snapshot_and_caps_at_three():
    snap = snapshot([make(f"p{i}", i) for i in range(5)])
    projects = [{"repo": f"ada/p{i}"} for i in range(5)] + [{"repo": "ada/ghost"}]
    assert [f.name for f in featured(snap, {"projects": projects})] == ["p4", "p3", "p2"]


def test_featured_finds_a_repository_of_another_owner():
    snap = snapshot([make("engine", 1), make("engine", 900, owner="babbage")])
    assert featured(snap, {"projects": [{"repo": "babbage/engine"}]})[0].stars == 900


# ── language shares ──────────────────────────────────────────────────────────

def test_language_shares_are_percentages_of_the_kept_languages_largest_first():
    snap = snapshot([make("a", languages={"Python": 600, "HTML": 1000}), make("b", languages={"Rust": 400})])
    assert language_shares(snap, ["HTML"], 8) == [("Python", 60.0), ("Rust", 40.0)]


def test_language_shares_stop_at_max_display():
    snap = snapshot([make("a", languages={"A": 5, "B": 4, "C": 1})])
    assert [name for name, _ in language_shares(snap, [], 2)] == ["A", "B"]


def test_language_shares_ignore_forks_and_other_owners():
    snap = snapshot([make("mine", languages={"Python": 100}), make("fork", languages={"C": 900}, fork=True),
                     make("theirs", languages={"Go": 900}, owner="babbage")])
    assert language_shares(snap, [], 8) == [("Python", 100.0)]


# ── weekly series ────────────────────────────────────────────────────────────

def test_weekly_series_gives_values_dates_total_and_peak():
    weeks = ((date(2026, 9, 13), 15), (date(2026, 9, 20), 25), (date(2026, 9, 27), 4))
    values, dates, total, peak = weekly_series(snapshot(weeks=weeks, total=44))
    assert (values, total, peak) == ([15, 25, 4], 44, 1)
    assert dates[0] == date(2026, 9, 13)


def test_weekly_series_is_absent_without_a_calendar():
    assert weekly_series(snapshot(weeks=None)) is None
    assert weekly_series(snapshot(weeks=())) is None


# ── an empty profile ─────────────────────────────────────────────────────────

def test_empty_profile_yields_empty_models():
    snap = snapshot([])
    assert visible_repos(snap, {"projects": []}) == []
    assert featured(snap, {"projects": [{"repo": "ada/ghost"}]}) == []
    assert language_shares(snap, [], 8) == []
    assert assign_arms([], ARMS, []) == {}


# ── the galaxy model ─────────────────────────────────────────────────────────

import yaml

from generator.config import validate_config
from generator.data import load_demo
from generator.model import Arm, GalaxyModel, galaxy


def demo_config():
    with open("config.example.yml", encoding="utf-8") as handle:
        return validate_config(yaml.safe_load(handle))


def test_only_focus_areas_with_repositories_become_arms_in_config_order():
    model = galaxy(load_demo(), demo_config())
    assert [arm.name for arm in model.arms] == ["Frontend", "Backend", "DevOps"]
    assert [r.name for r in model.arms[2].repos] == ["comet-deploy"]


def test_repositories_on_an_arm_are_in_order_of_creation():
    model = galaxy(load_demo(), demo_config())
    assert [r.name for r in model.arms[0].repos] == [
        "dark-matter-css", "nebula-ui", "quasar-charts", "star-map", "telescope-action"]


def test_repositories_without_an_arm_are_loose():
    model = galaxy(load_demo(), demo_config())
    assert sorted(r.name for r in model.loose) == ["aphelion", "nyx-dotfiles", "orbit-cli", "parallax-notes", "wormhole"]


def test_a_focus_area_without_repositories_is_not_an_arm():
    config = demo_config()
    config["galaxy_arms"].append({"name": "Hardware", "items": ["Verilog"]})
    assert "Hardware" not in [arm.name for arm in galaxy(load_demo(), config).arms]


def test_labels_are_the_featured_projects_plus_the_brightest_repository():
    config = demo_config()
    config["projects"] = [{"repo": "galaxy-dev/lightcurve"}]
    assert galaxy(load_demo(), config).labels == frozenset({"lightcurve", "nebula-ui"})


def test_never_more_than_four_labels():
    config = demo_config()
    config["projects"] = [{"repo": name} for name in ("nebula-ui", "stargate-api", "orbit-cli", "lightcurve", "wormhole")]
    assert len(galaxy(load_demo(), config).labels) == 4


def test_entrance_order_is_the_order_of_creation_across_the_whole_galaxy():
    model = galaxy(load_demo(), demo_config())
    assert model.order[0] == "nyx-dotfiles" and model.order[-1] == "aphelion"
    assert len(model.order) == 15


def test_when_no_repository_matches_an_arm_there_are_two_unnamed_arms_and_everything_is_loose():
    config = demo_config()
    config["galaxy_arms"] = [{"name": "Hardware", "items": ["Verilog"]}]
    config["projects"] = []
    model = galaxy(load_demo(), config)
    assert model.arms == (Arm(None, ()), Arm(None, ()))
    assert len(model.loose) == 15


def test_empty_profile_is_two_unnamed_arms_and_nothing_else():
    model = galaxy(snapshot([]), {"projects": [], "galaxy_arms": ARMS})
    assert model == GalaxyModel(arms=(Arm(None, ()), Arm(None, ())), loose=(), labels=frozenset(), order=(),
                                today=TODAY)


def test_a_featured_fork_is_a_star_even_though_other_forks_are_not():
    snap = snapshot([make("mine", 5), make("fork-a", 9, fork=True), make("fork-b", 9, fork=True)])
    assert [r.name for r in visible_repos(snap, {"projects": [{"repo": "ada/fork-a"}]})] == ["fork-a", "mine"]
