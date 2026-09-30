"""The data snapshot: GraphQL and REST payloads turned into one shape, and the demo fixture."""

import json
from datetime import date
from pathlib import Path

import pytest
import requests

from generator import data
from generator.data import DataError, Snapshot, build_query, fetch, from_graphql, from_rest, load_demo

TODAY = date(2026, 9, 30)
SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "graphql_sample.json").read_text(encoding="utf-8"))


def snap() -> Snapshot:
    return from_graphql(SAMPLE, TODAY)


def repo(name):
    return next(r for r in snap().repos if r.name == name)


# ── from_graphql ─────────────────────────────────────────────────────────────

def test_repositories_keep_owner_stars_and_dates():
    engine = repo("engine")
    assert (engine.owner, engine.stars) == ("ada", 120)
    assert (engine.created, engine.pushed) == (date(2024, 3, 1), date(2026, 9, 25))


def test_languages_are_bytes_per_language_and_topics_a_tuple():
    engine = repo("engine")
    assert engine.languages == {"Python": 800, "Shell": 200}
    assert engine.primary_language == "Python"
    assert engine.topics == ("math", "engines")


def test_repository_without_language_or_description():
    notes = repo("notes")
    assert notes.primary_language is None
    assert notes.languages == {}
    assert notes.description == ""


def test_forks_are_kept_and_flagged():
    assert repo("loom").is_fork is True
    assert repo("engine").is_fork is False


def test_featured_repository_from_another_owner_is_included():
    difference = repo("difference")
    assert (difference.owner, difference.stars) == ("babbage", 900)


def test_a_featured_repository_the_user_already_owns_is_not_duplicated():
    assert [r.name for r in snap().repos].count("engine") == 1


def test_a_featured_repository_that_does_not_exist_is_skipped():
    assert len(snap().repos) == 5


def test_weeks_are_summed_and_dated_by_their_first_day():
    assert snap().weeks == ((date(2026, 9, 13), 15), (date(2026, 9, 20), 25))
    assert snap().total_contributions == 40


def test_counters():
    assert snap().counters == {"stars": 131, "prs": 12, "issues": 5, "repos": 4}


def test_login_and_today_are_carried():
    assert (snap().login, snap().today) == ("ada", TODAY)


def test_unknown_user_is_an_error():
    with pytest.raises(DataError, match="ghost"):
        from_graphql({"data": {"user": None}}, TODAY, login="ghost")


# ── build_query ──────────────────────────────────────────────────────────────

def test_query_without_featured_repositories_has_no_alias():
    query, variables = build_query("ada", [])
    assert "x0:" not in query
    assert variables == {"login": "ada"}


def test_query_adds_one_alias_per_featured_repository():
    query, variables = build_query("ada", ["babbage/difference", "ada/engine"])
    assert "x0: repository(owner: $o0, name: $n0)" in query
    assert "x1: repository(owner: $o1, name: $n1)" in query
    assert variables == {"login": "ada", "o0": "babbage", "n0": "difference", "o1": "ada", "n1": "engine"}


def test_query_treats_a_bare_name_as_the_users_own_repository():
    query, variables = build_query("ada", ["just-a-name"])
    assert "x0: repository(owner: $o0, name: $n0)" in query
    assert (variables["o0"], variables["n0"]) == ("ada", "just-a-name")


# ── from_rest ────────────────────────────────────────────────────────────────

REST_REPOS = [
    {"name": "engine", "owner": {"login": "ada"}, "fork": False, "stargazers_count": 120,
     "created_at": "2024-03-01T10:00:00Z", "pushed_at": "2026-09-25T08:30:00Z",
     "description": "Analytical engine", "language": "Python", "topics": ["math"]},
    {"name": "loom", "owner": {"login": "ada"}, "fork": True, "stargazers_count": 7,
     "created_at": "2026-01-05T00:00:00Z", "pushed_at": "2026-01-06T00:00:00Z",
     "description": None, "language": None, "topics": []},
]


def test_rest_snapshot_has_no_calendar():
    s = from_rest("ada", {"public_repos": 2}, REST_REPOS, {"engine": {"Python": 800}}, 12, 5, TODAY)
    assert s.weeks is None and s.total_contributions is None


def test_rest_snapshot_matches_the_graphql_shape():
    s = from_rest("ada", {"public_repos": 2}, REST_REPOS, {"engine": {"Python": 800}}, 12, 5, TODAY)
    engine, loom = s.repos
    assert (engine.languages, engine.primary_language, engine.topics) == ({"Python": 800}, "Python", ("math",))
    assert (loom.is_fork, loom.description, loom.languages) == (True, "", {})
    assert s.counters == {"stars": 127, "prs": 12, "issues": 5, "repos": 2}


# ── fetch (wiring, with a fake transport) ────────────────────────────────────

class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code, self.headers, self.text = payload, status, {}, ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class FakeHTTP:
    def __init__(self, graphql):
        self.graphql, self.calls = graphql, []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        if url.endswith("/graphql"):
            return FakeResponse(self.graphql)
        if url.endswith("/users/ada"):
            return FakeResponse({"public_repos": 2})
        if "/users/ada/repos" in url:
            return FakeResponse(REST_REPOS if kwargs["params"]["page"] == 1 else [])
        if "/search/issues" in url:
            return FakeResponse({"total_count": 9})
        if "/languages" in url:
            return FakeResponse({"Python": 800})
        raise AssertionError(url)


def test_fetch_with_a_token_makes_one_graphql_call():
    http = FakeHTTP(SAMPLE)
    s = fetch("ada", "tok", ["babbage/difference"], TODAY, http=http)
    assert http.calls == [("POST", "https://api.github.com/graphql")]
    assert s.total_contributions == 40


def test_fetch_without_a_token_uses_rest():
    http = FakeHTTP(SAMPLE)
    s = fetch("ada", "", [], TODAY, http=http)
    assert all("/graphql" not in url for _m, url in http.calls)
    assert s.weeks is None and s.counters["prs"] == 9


def test_fetch_falls_back_to_rest_when_graphql_reports_errors():
    http = FakeHTTP({"errors": [{"message": "boom"}]})
    s = fetch("ada", "tok", [], TODAY, http=http)
    assert s.weeks is None
    assert ("POST", "https://api.github.com/graphql") in http.calls


# ── demo ─────────────────────────────────────────────────────────────────────

def test_demo_snapshot_is_always_the_same():
    assert load_demo() == load_demo()


def test_demo_snapshot_has_a_fixed_day_a_full_year_and_enough_repositories():
    demo = load_demo()
    assert demo.today == date(2026, 9, 30)
    assert len(demo.weeks) == 53
    assert len([r for r in demo.repos if not r.is_fork]) >= 12


def test_demo_snapshot_contains_the_example_configs_featured_projects():
    names = {f"{r.owner}/{r.name}" for r in load_demo().repos}
    assert {"galaxy-dev/nebula-ui", "galaxy-dev/stargate-api"} <= names


def test_demo_file_is_a_graphql_payload_so_it_exercises_the_real_path():
    payload = json.loads(data.DEMO_FILE.read_text(encoding="utf-8"))
    assert "user" in payload["data"] and "today" in payload


# ── review fixes: a bad GraphQL answer must fall back, never crash ───────────



def test_fetch_falls_back_when_graphql_returns_null_data():
    http = FakeHTTP({"data": None, "errors": [{"message": "timeout"}]})
    assert fetch("ada", "tok", [], TODAY, http=http).weeks is None


def test_fetch_falls_back_when_the_graphql_payload_cannot_be_read():
    broken = json.loads(json.dumps(SAMPLE))
    broken["data"]["user"]["contributionsCollection"] = None
    assert fetch("ada", "tok", [], TODAY, http=FakeHTTP(broken)).weeks is None


def test_null_repository_nodes_and_null_languages_are_tolerated():
    payload = json.loads(json.dumps(SAMPLE))
    payload["data"]["user"]["repositories"]["nodes"].append(None)
    payload["data"]["user"]["repositories"]["nodes"][0]["languages"] = None
    payload["data"]["user"]["repositories"]["nodes"][0]["repositoryTopics"] = None
    engine = next(r for r in from_graphql(payload, TODAY).repos if r.name == "engine")
    assert engine.languages == {} and engine.topics == ()


def test_rest_path_also_fetches_featured_repositories_of_other_owners():
    class WithOrg(FakeHTTP):
        def request(self, method, url, **kwargs):
            if url.endswith("/repos/babbage/difference"):
                self.calls.append((method, url))
                return FakeResponse({"name": "difference", "owner": {"login": "babbage"}, "fork": False,
                                     "stargazers_count": 900, "created_at": "2022-02-02T00:00:00Z",
                                     "pushed_at": "2026-08-01T00:00:00Z", "description": "Difference engine",
                                     "language": "C", "topics": []})
            return super().request(method, url, **kwargs)

    snap_ = fetch("ada", "", ["babbage/difference", "ada/engine"], TODAY, http=WithOrg(SAMPLE))
    difference = next(r for r in snap_.repos if r.name == "difference")
    assert (difference.owner, difference.stars) == ("babbage", 900)
    assert [r.name for r in snap_.repos].count("engine") == 1


class RateLimited(FakeHTTP):
    """Everything works except the per-repository languages endpoint, which is rate limited."""

    def request(self, method, url, **kwargs):
        if "/languages" in url:
            self.calls.append((method, url))
            response = FakeResponse({"message": "API rate limit exceeded"}, status=403)
            response.text = "API rate limit exceeded"
            response.headers = {"X-RateLimit-Reset": "9999999999"}
            return response
        return super().request(method, url, **kwargs)


def test_a_rate_limit_never_makes_the_run_sleep(monkeypatch):
    naps = []
    monkeypatch.setattr("time.sleep", naps.append)
    http = RateLimited(SAMPLE)
    many = [dict(REST_REPOS[0], name=f"r{i}") for i in range(40)]
    monkeypatch.setattr(http, "request", (lambda original: lambda method, url, **kw:
                        FakeResponse(many if kw["params"]["page"] == 1 else [])
                        if "/users/ada/repos" in url else original(method, url, **kw))(http.request))
    snap_ = fetch("ada", "", [], TODAY, http=http)
    assert naps == []
    assert len([c for c in http.calls if "/languages" in c[1]]) == 1      # gave up after the first refusal
    assert len(snap_.repos) == 40 and all(r.languages == {} for r in snap_.repos)


def test_a_rate_limit_on_the_profile_itself_is_a_clear_error():
    class Blocked(FakeHTTP):
        def request(self, method, url, **kwargs):
            response = FakeResponse({"message": "API rate limit exceeded"}, status=403)
            response.text = "API rate limit exceeded"
            return response

    with pytest.raises(DataError, match="rate limit"):
        fetch("ada", "", [], TODAY, http=Blocked(SAMPLE))
