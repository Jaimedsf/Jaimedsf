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
    s = from_rest("ada", {"public_repos": 2}, REST_REPOS, {"ada/engine": {"Python": 800}}, 12, 5, TODAY)
    assert s.weeks is None and s.total_contributions is None


def test_rest_snapshot_matches_the_graphql_shape():
    s = from_rest("ada", {"public_repos": 2}, REST_REPOS, {"ada/engine": {"Python": 800}}, 12, 5, TODAY)
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


def test_with_a_token_a_graphql_failure_is_an_error_never_a_poorer_answer_from_rest():
    """The REST path has no calendar. Falling back to it would draw a good image over with a poorer one."""
    http = FakeHTTP({"errors": [{"message": "boom"}]})
    with pytest.raises(DataError, match="GraphQL"):
        fetch("ada", "tok", [], TODAY, http=http)
    assert http.calls == [("POST", "https://api.github.com/graphql")]


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


# ── a bad GraphQL answer is a clear error, never a crash and never a fallback ─

@pytest.mark.parametrize("payload", [
    {"data": None, "errors": [{"message": "timeout"}]},
    {"data": {"user": None}},
    {"unexpected": True},
    [],
])
def test_a_graphql_answer_that_cannot_be_read_is_a_data_error(payload):
    http = FakeHTTP(payload)
    with pytest.raises(DataError):
        fetch("ada", "tok", [], TODAY, http=http)
    assert all("/graphql" in url for _method, url in http.calls)


def test_a_graphql_answer_without_the_calendar_is_a_data_error():
    broken = json.loads(json.dumps(SAMPLE))
    broken["data"]["user"]["contributionsCollection"] = None
    with pytest.raises(DataError):
        fetch("ada", "tok", [], TODAY, http=FakeHTTP(broken))


def test_a_server_error_on_graphql_is_passed_on_not_papered_over():
    class Down(FakeHTTP):
        def request(self, method, url, **kwargs):
            self.calls.append((method, url))
            return FakeResponse({"message": "Bad Gateway"}, status=502)

    http = Down(SAMPLE)
    with pytest.raises(requests.exceptions.HTTPError):
        fetch("ada", "tok", [], TODAY, http=http)
    assert len(http.calls) == 1


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


def test_a_rate_limit_in_the_middle_of_the_languages_stops_the_run_without_sleeping(monkeypatch):
    """Shares computed from some of the repositories would be wrong, so there is no partial answer."""
    naps = []
    monkeypatch.setattr("time.sleep", naps.append)
    http = RateLimited(SAMPLE)
    with pytest.raises(DataError, match="rate limit.*GITHUB_TOKEN"):
        fetch("ada", "", [], TODAY, http=http)
    assert naps == []
    assert len([c for c in http.calls if "/languages" in c[1]]) == 1      # gave up at the first refusal


class ManyRepos(FakeHTTP):
    """A profile with 130 repositories, in two pages, the n-th with n stars."""

    def request(self, method, url, **kwargs):
        if "/users/ada/repos" in url:
            self.calls.append((method, url))
            page = kwargs["params"]["page"]
            first, last = (0, 100) if page == 1 else (100, 130) if page == 2 else (0, 0)
            return FakeResponse([dict(REST_REPOS[0], name=f"r{i}", stargazers_count=i) for i in range(first, last)])
        return super().request(method, url, **kwargs)


def test_without_a_token_every_page_of_repositories_is_read():
    snap_ = fetch("ada", "", [], TODAY, http=ManyRepos(SAMPLE))
    assert len(snap_.repos) == 130


def test_without_a_token_languages_are_read_for_the_forty_brightest_repositories_only():
    """Anonymous GitHub allows 60 requests an hour; one call per repository would never finish a large profile."""
    http = ManyRepos(SAMPLE)
    snap_ = fetch("ada", "", [], TODAY, http=http)
    asked = [url.split("/repos/ada/")[1].split("/")[0] for _method, url in http.calls if "/languages" in url]
    assert asked == [f"r{i}" for i in range(129, 89, -1)]
    assert len(http.calls) <= 60
    assert sum(1 for r in snap_.repos if r.languages) == 40


def test_the_rest_path_takes_the_username_as_github_spells_it():
    class Cased(FakeHTTP):
        def request(self, method, url, **kwargs):
            if url.lower().endswith("/users/ada"):
                self.calls.append((method, url))
                return FakeResponse({"login": "Ada", "public_repos": 2})
            return super().request(method, url.replace("/users/ADA", "/users/ada"), **kwargs)

    assert fetch("ADA", "", [], TODAY, http=Cased(SAMPLE)).login == "Ada"


def test_on_the_rest_path_two_repositories_of_one_name_keep_their_own_languages():
    class Twins(FakeHTTP):
        def request(self, method, url, **kwargs):
            if url.endswith("/repos/babbage/engine"):
                self.calls.append((method, url))
                return FakeResponse(dict(REST_REPOS[0], owner={"login": "babbage"}, language="Rust"))
            if url.endswith("/repos/babbage/engine/languages"):
                self.calls.append((method, url))
                return FakeResponse({"Rust": 99999})
            return super().request(method, url, **kwargs)

    snap_ = fetch("ada", "", ["babbage/engine", "babbage/engine"], TODAY, http=Twins(SAMPLE))
    by_key = {r.key: r.languages for r in snap_.repos}
    assert by_key["ada/engine"] == {"Python": 800} and by_key["babbage/engine"] == {"Rust": 99999}
    assert [r.key for r in snap_.repos].count("babbage/engine") == 1          # listed twice, read once


def test_the_token_travels_in_the_authorization_header_and_every_call_has_a_timeout():
    seen = []

    class Watching(FakeHTTP):
        def request(self, method, url, **kwargs):
            seen.append(kwargs)
            return super().request(method, url, **kwargs)

    fetch("ada", "tok", [], TODAY, http=Watching(SAMPLE))
    fetch("ada", "", [], TODAY, http=Watching(SAMPLE))
    assert seen[0]["headers"]["Authorization"] == "Bearer tok"
    assert all("Authorization" not in kwargs["headers"] for kwargs in seen[1:])
    assert all(kwargs.get("timeout") for kwargs in seen)


def test_a_repository_never_pushed_to_takes_its_creation_day():
    never = dict(REST_REPOS[0], pushed_at=None)
    snap_ = from_rest("ada", {"public_repos": 1}, [never], {}, 0, 0, TODAY)
    assert snap_.repos[0].pushed == date(2024, 3, 1)


def test_a_rate_limit_on_the_profile_itself_is_a_clear_error():
    class Blocked(FakeHTTP):
        def request(self, method, url, **kwargs):
            response = FakeResponse({"message": "API rate limit exceeded"}, status=403)
            response.text = "API rate limit exceeded"
            return response

    with pytest.raises(DataError, match="rate limit"):
        fetch("ada", "", [], TODAY, http=Blocked(SAMPLE))


def test_counters_the_rate_limit_kept_from_being_read_are_unknown_not_zero():
    """The search API has a limit of its own. If it refuses, pull requests and issues are unknown, not 0."""
    class SearchRefused(FakeHTTP):
        def request(self, method, url, **kwargs):
            if "/search/issues" in url:
                self.calls.append((method, url))
                response = FakeResponse({"message": "API rate limit exceeded"}, status=403)
                response.text = "API rate limit exceeded"
                return response
            return super().request(method, url, **kwargs)

    http = SearchRefused(SAMPLE)
    snap_ = fetch("ada", "", [], TODAY, http=http)
    assert snap_.counters["prs"] is None and snap_.counters["issues"] is None
    assert snap_.counters["repos"] == 2 and snap_.counters["stars"] is not None
    assert len([c for c in http.calls if "/search/issues" in c[1]]) == 1      # asked once, not once per counter


def test_counters_that_were_read_are_kept_even_when_zero():
    class NoPullRequests(FakeHTTP):
        def request(self, method, url, **kwargs):
            if "/search/issues" in url:
                self.calls.append((method, url))
                return FakeResponse({"total_count": 0})
            return super().request(method, url, **kwargs)

    snap_ = fetch("ada", "", [], TODAY, http=NoPullRequests(SAMPLE))
    assert snap_.counters["prs"] == 0 and snap_.counters["issues"] == 0


def test_without_a_token_a_featured_project_that_is_gone_is_left_out_and_the_rest_is_read(caplog):
    class Gone(FakeHTTP):
        def request(self, method, url, **kwargs):
            if url.endswith("/repos/ghost/gone"):
                self.calls.append((method, url))
                return FakeResponse({"message": "Not Found"}, status=404)
            return super().request(method, url, **kwargs)

    with caplog.at_level("WARNING"):
        snap_ = fetch("ada", "", ["ghost/gone"], TODAY, http=Gone(SAMPLE))
    assert {r.key for r in snap_.repos} == {"ada/engine", "ada/loom"}
    assert "ghost/gone" in caplog.text
