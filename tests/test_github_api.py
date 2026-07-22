"""Checks for GitHubAPI repo pagination and private-repo log redaction."""

from generator.github_api import GitHubAPI


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.headers = {}
        self.text = ""

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


def test_paginate_repos_uses_authenticated_endpoint_with_token(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return FakeResponse([])

    api = GitHubAPI("jaimedsf", token="fake-token")
    monkeypatch.setattr(api, "_request", fake_request)

    list(api._paginate_repos())

    assert calls[0][0] == f"{GitHubAPI.REST_URL}/user/repos"
    assert calls[0][1]["affiliation"] == "owner,organization_member"


def test_paginate_repos_uses_public_endpoint_without_token(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return FakeResponse([])

    api = GitHubAPI("jaimedsf", token=None)
    monkeypatch.setattr(api, "_request", fake_request)

    list(api._paginate_repos())

    assert calls[0][0] == f"{GitHubAPI.REST_URL}/users/jaimedsf/repos"


def test_fetch_languages_redacts_private_repo_name_in_logs(monkeypatch, caplog):
    repo_page = [
        {
            "full_name": "jaimedsf-org/secret-project",
            "private": True,
            "fork": False,
            "languages_url": "https://api.github.com/repos/jaimedsf-org/secret-project/languages",
        }
    ]

    def fake_paginate_repos(self):
        yield repo_page

    def fake_request(method, url, **kwargs):
        return FakeResponse({}, status_code=500)

    api = GitHubAPI("jaimedsf", token="fake-token")
    monkeypatch.setattr(GitHubAPI, "_paginate_repos", fake_paginate_repos)
    monkeypatch.setattr(api, "_request", fake_request)

    with caplog.at_level("WARNING"):
        api.fetch_languages()

    assert "secret-project" not in caplog.text
    assert "<private repo>" in caplog.text
