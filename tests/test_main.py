"""The command line: config in, sixteen SVG files out."""

import shutil
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pytest
import requests
import yaml

from generator import build, main
from generator.config import ConfigError, validate_config
from generator.data import DataError, load_demo

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "config.example.yml"
TODAY = date(2026, 9, 30)
CONFIG = {
    "username": "ada",
    "profile": {"name": "Ada Lovelace", "tagline": "Analyst"},
    "galaxy_arms": [{"name": "Engines", "items": ["Python"]}],
    "projects": [{"repo": "babbage/difference", "description": "A difference engine."},
                 {"repo": "ada/engine", "description": "Notes on the engine."}],
}


def write_config(folder, content=CONFIG):
    path = folder / "config.yml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


@pytest.fixture
def fetched(monkeypatch):
    """Stands in for GitHub: records how the data was asked for and answers with the demo snapshot."""
    calls = []

    def fake_fetch(login, token, extra_repos, today, http=requests):
        calls.append({"login": login, "token": token, "extra_repos": list(extra_repos), "today": today})
        return load_demo()

    monkeypatch.setattr(main.data, "fetch", fake_fetch)
    return calls


# ── run ──────────────────────────────────────────────────────────────────────

def test_demo_mode_writes_every_plate_in_every_variant(tmp_path):
    written = main.run(EXAMPLE, tmp_path / "out", demo=True, token="", today=TODAY)
    names = sorted(path.name for path in written)
    assert len(names) == 16
    assert names == sorted(f"{stem}{suffix}.svg" for stem in build.RENDERERS
                           for suffix in ("", "-light", "-mobile", "-mobile-light"))
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == names
    for path in written:
        ET.fromstring(path.read_text(encoding="utf-8"))


def test_the_files_are_what_the_build_renders(tmp_path):
    main.run(EXAMPLE, tmp_path, demo=True, token="", today=TODAY)
    config = validate_config(yaml.safe_load(EXAMPLE.read_text(encoding="utf-8")))
    for name, svg in build.render_all(config, load_demo()).items():
        assert (tmp_path / name).read_text(encoding="utf-8") == svg


def test_demo_mode_asks_github_for_nothing(tmp_path, fetched):
    main.run(EXAMPLE, tmp_path, demo=True, token="tok", today=TODAY)
    assert fetched == []


def test_a_real_run_asks_for_the_profile_with_the_token_the_featured_projects_and_the_day(tmp_path, fetched):
    main.run(write_config(tmp_path), tmp_path / "out", demo=False, token="tok", today=TODAY)
    assert fetched == [{"login": "ada", "token": "tok", "extra_repos": ["babbage/difference", "ada/engine"],
                        "today": TODAY}]
    assert len(list((tmp_path / "out").glob("*.svg"))) == 16


def test_the_output_folder_is_created_when_missing(tmp_path):
    main.run(EXAMPLE, tmp_path / "deep" / "er", demo=True, token="", today=TODAY)
    assert (tmp_path / "deep" / "er" / "galaxy-header.svg").exists()


def test_a_failed_fetch_writes_nothing_and_leaves_the_old_images_alone(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    (out / "galaxy-header.svg").write_text("the image from the last good run", encoding="utf-8")

    def refuse(*_args, **_kwargs):
        raise DataError("GitHub has no user 'ada'.")

    monkeypatch.setattr(main.data, "fetch", refuse)
    with pytest.raises(DataError):
        main.run(write_config(tmp_path), out, demo=False, token="", today=TODAY)
    assert [p.name for p in out.iterdir()] == ["galaxy-header.svg"]
    assert (out / "galaxy-header.svg").read_text(encoding="utf-8") == "the image from the last good run"


def test_a_failure_while_drawing_writes_nothing(tmp_path, monkeypatch):
    def broken(_config, _snap):
        raise RuntimeError("a plate failed")

    monkeypatch.setattr(main.build, "render_all", broken)
    with pytest.raises(RuntimeError):
        main.run(EXAMPLE, tmp_path / "out", demo=True, token="", today=TODAY)
    assert not (tmp_path / "out").exists() or list((tmp_path / "out").iterdir()) == []


def test_an_invalid_config_is_reported_before_anything_is_fetched_or_written(tmp_path, fetched):
    broken = write_config(tmp_path, {"username": "ada"})
    with pytest.raises(ConfigError):
        main.run(broken, tmp_path / "out", demo=False, token="", today=TODAY)
    assert fetched == [] and not (tmp_path / "out").exists()


def test_a_config_that_is_not_a_mapping_is_a_config_error(tmp_path):
    path = tmp_path / "config.yml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        main.run(path, tmp_path / "out", demo=True, token="", today=TODAY)


def test_same_inputs_same_bytes(tmp_path):
    first = main.run(EXAMPLE, tmp_path / "a", demo=True, token="", today=TODAY)
    second = main.run(EXAMPLE, tmp_path / "b", demo=True, token="", today=TODAY)
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


# ── the command line ─────────────────────────────────────────────────────────

@pytest.fixture
def project(tmp_path, monkeypatch):
    """A copy of the repository's layout in a temporary folder, with main pointed at it."""
    shutil.copy(EXAMPLE, tmp_path / "config.example.yml")
    monkeypatch.setattr(main, "ROOT", tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return tmp_path


def generated(project):
    return sorted(p.name for p in (project / "assets" / "generated").glob("*.svg"))


def test_demo_flag_alone_generates_from_the_example_config(project):
    main.main(["--demo"])
    assert len(generated(project)) == 16


def test_generate_subcommand_with_demo_does_the_same(project):
    main.main(["generate", "--demo"])
    first = {p.name: p.read_bytes() for p in (project / "assets" / "generated").iterdir()}
    main.main(["--demo"])
    assert first == {p.name: p.read_bytes() for p in (project / "assets" / "generated").iterdir()}


def test_without_a_config_the_command_says_how_to_make_one_and_fails(project, caplog):
    with pytest.raises(SystemExit) as stop:
        main.main([])
    assert stop.value.code == 1
    assert "config.example.yml" in caplog.text and generated(project) == []


def test_the_token_comes_from_the_environment(project, fetched, monkeypatch):
    write_config(project)
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    main.main([])
    assert fetched[0]["token"] == "from-env" and len(generated(project)) == 16


def test_a_fetch_failure_ends_with_a_message_and_a_failing_exit_code(project, monkeypatch, caplog):
    write_config(project)

    def refuse(*_args, **_kwargs):
        raise DataError("GitHub rate limit reached before the profile could be read.")

    monkeypatch.setattr(main.data, "fetch", refuse)
    with pytest.raises(SystemExit) as stop:
        main.main([])
    assert stop.value.code == 1 and "rate limit" in caplog.text and generated(project) == []


def test_a_network_failure_ends_the_same_way(project, monkeypatch, caplog):
    write_config(project)

    def unreachable(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr(main.data, "fetch", unreachable)
    with pytest.raises(SystemExit) as stop:
        main.main([])
    assert stop.value.code == 1 and "no route to host" in caplog.text


def test_an_invalid_config_ends_with_its_reason(project, caplog):
    write_config(project, {"username": "ada"})
    with pytest.raises(SystemExit) as stop:
        main.main([])
    assert stop.value.code == 1 and "Invalid config" in caplog.text


# ── against GitHub's answers ─────────────────────────────────────────────────

class Answer:
    def __init__(self, payload, status=200):
        self._payload, self.status_code, self.headers, self.text = payload, status, {}, ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}")


class GraphQLOnly:
    """An HTTP client that answers the GraphQL call with a stored payload and records what was asked."""

    def __init__(self, payload):
        self.payload, self.asked = payload, []

    def request(self, method, url, **kwargs):
        self.asked.append((method, url, kwargs))
        assert url.endswith("/graphql"), url
        return Answer(self.payload)


def test_a_featured_project_that_no_longer_exists_is_left_out_and_the_rest_is_drawn(tmp_path):
    import json
    sample = json.loads((ROOT / "tests" / "fixtures" / "graphql_sample.json").read_text(encoding="utf-8"))
    config = dict(CONFIG, projects=CONFIG["projects"] + [{"repo": "ghost/gone", "description": "Deleted."}])
    http = GraphQLOnly(sample)
    written = main.run(write_config(tmp_path, config), tmp_path / "out", demo=False, token="tok", today=TODAY,
                       http=http)
    assert len(written) == 16
    variables = http.asked[0][2]["json"]["variables"]
    assert (variables["o2"], variables["n2"]) == ("ghost", "gone")
    featured = (tmp_path / "out" / "projects-constellation.svg").read_text(encoding="utf-8")
    assert "difference" in featured and "gone" not in featured
