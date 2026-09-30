"""Interactive setup wizard for Galaxy Profile configuration."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import yaml
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator

from generator.config import LEGACY_THEME, RETIRED_COLOURS, ConfigError, validate_config
from generator.tech_catalog import get_all_techs
from generator.themes import PALETTES

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yml")

PALETTE_NOTES = {
    "deep-sky": "deep-sky: a night sky, stars in their real colours",
    "cyanotype": "cyanotype: Prussian blue and paper white, one warm accent",
}

ALL_METRICS = ["commits", "stars", "prs", "issues", "repos"]


def run_init():
    """Orchestrate the full interactive setup wizard."""
    print("\n🌌 Galaxy Profile — Interactive Setup\n")

    existing = _detect_existing_config()
    defaults = {}

    if existing is not None:
        action, defaults = _handle_existing_config(existing)
        if action == "cancel":
            print("Setup cancelled.")
            return

    essential = _prompt_essential(defaults)
    arms = _prompt_galaxy_arms(defaults)
    look = _prompt_look(defaults)

    configure_advanced = inquirer.confirm(
        message="Configure advanced options (bio, social, projects, stats, languages)?",
        default=False,
    ).execute()

    advanced = _prompt_advanced(defaults) if configure_advanced else {}

    config = _build_config(essential, arms, advanced, look)
    path = _save_config(config)

    # Validate
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)
        validate_config(raw)
        print(f"\n✅ Config saved and validated: {path}")
    except ConfigError as e:
        print(f"\n⚠️  Config saved to {path} but validation found issues: {e}")

    _offer_generation()


def _detect_existing_config() -> dict | None:
    """Check if config.yml already exists. Return the parsed dict or None."""
    path = os.path.normpath(_CONFIG_PATH)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _handle_existing_config(existing: dict) -> tuple[str, dict]:
    """Ask user what to do with existing config. Return (action, defaults)."""
    action = inquirer.select(
        message="config.yml already exists. What would you like to do?",
        choices=[
            {"name": "Overwrite — start from scratch", "value": "overwrite"},
            {"name": "Edit — use current values as defaults", "value": "edit"},
            {"name": "Cancel", "value": "cancel"},
        ],
    ).execute()

    if action == "cancel":
        return ("cancel", {})
    if action == "edit":
        return ("edit", existing if isinstance(existing, dict) else {})
    return ("overwrite", {})


def _prompt_essential(defaults: dict) -> dict:
    """Collect essential fields: username, name, tagline."""
    profile_defaults = defaults.get("profile", {})

    username = inquirer.text(
        message="GitHub username:",
        default=defaults.get("username", ""),
        validate=EmptyInputValidator("Username cannot be empty."),
    ).execute()

    name = inquirer.text(
        message="Display name:",
        default=profile_defaults.get("name", ""),
        validate=EmptyInputValidator("Name cannot be empty."),
    ).execute()

    tagline = inquirer.text(
        message="Tagline (short description):",
        default=profile_defaults.get("tagline", ""),
    ).execute()

    return {"username": username, "name": name, "tagline": tagline}


def _arm_entry(name: str, items: list, previous: dict) -> dict:
    """One focus area as it goes into the config. Repositories pinned to it before are kept."""
    entry = {"name": name, "items": list(items)}
    if isinstance(previous, dict) and previous.get("repos"):
        entry["repos"] = list(previous["repos"])
    return entry


def _prompt_galaxy_arms(defaults: dict) -> list:
    """Collect 3 galaxy arms, each with a name and its technologies."""
    all_techs = get_all_techs()
    default_arms = defaults.get("galaxy_arms", [])
    arms = []

    for i in range(3):
        print(f"\n--- Galaxy Arm {i + 1}/3 ---")
        arm_default = default_arms[i] if i < len(default_arms) else {}

        arm_name = inquirer.text(
            message=f"Arm {i + 1} name (e.g. Frontend, Backend, DevOps):",
            default=arm_default.get("name", ""),
            validate=EmptyInputValidator("Arm name cannot be empty."),
        ).execute()

        default_items = arm_default.get("items", [])
        arm_techs = inquirer.fuzzy(
            message=f"Arm {i + 1} technologies (type to filter, space to select):",
            choices=all_techs,
            default=default_items,
            multiselect=True,
            validate=lambda result: len(result) > 0,
            invalid_message="Select at least one technology.",
        ).execute()

        arms.append(_arm_entry(arm_name, arm_techs, arm_default))

    return arms


def _theme_section(dark: str, light: str, previous) -> dict:
    """The config's `theme`: the two palettes, plus any version-1 colour the user had really changed.

    A colour equal to its old default is not written again, and the two that
    no longer paint anything (card backgrounds and borders) are dropped.
    """
    section = {"dark": dark, "light": light}
    if isinstance(previous, dict):
        for key, default in LEGACY_THEME.items():
            value = previous.get(key)
            if key in RETIRED_COLOURS or not isinstance(value, str) or value.lower() == default.lower():
                continue
            section[key] = value
    return section


def _prompt_look(defaults: dict) -> dict:
    """Ask for the palette of each mode and whether the images move."""
    print("\n--- Look ---")
    previous = defaults.get("theme")
    chosen = previous if isinstance(previous, dict) else {}
    palettes = [{"name": PALETTE_NOTES[name], "value": name} for name in PALETTES]
    dark = inquirer.select(
        message="Palette for GitHub's dark theme:",
        choices=palettes,
        default=chosen.get("dark", PALETTES[0]),
    ).execute()
    light = inquirer.select(
        message="Palette for GitHub's light theme:",
        choices=palettes,
        default=chosen.get("light", PALETTES[0]),
    ).execute()
    motion = inquirer.confirm(
        message="Animate the images? (visitors who ask their system for reduced motion always get them still)",
        default=defaults.get("motion", True) is not False,
    ).execute()
    kept = _theme_section(dark, light, previous)
    return {"dark": dark, "light": light, "motion": motion,
            "colours": {key: value for key, value in kept.items() if key not in ("dark", "light")}}


def _prompt_advanced(defaults: dict) -> dict:
    """Collect optional advanced fields."""
    result = {}
    profile_defaults = defaults.get("profile", {})
    social_defaults = defaults.get("social", {})

    # Bio, company, location, philosophy
    profile_fields = [
        ("bio", "Bio (multi-line, use \\n for newlines):"),
        ("company", "Company:"),
        ("location", "Location:"),
        ("philosophy", "Philosophy quote:"),
    ]
    for key, prompt in profile_fields:
        default = profile_defaults.get(key, "")
        if key == "bio":
            default = default.strip()
        value = inquirer.text(message=prompt, default=default).execute()
        if value:
            result[key] = value.replace("\\n", "\n") if key == "bio" else value

    # Social links
    print("\n--- Social Links (leave blank to skip) ---")
    social_fields = [("email", "Email:"), ("linkedin", "LinkedIn username:"), ("website", "Website URL:")]
    social = {}
    for key, prompt in social_fields:
        value = inquirer.text(
            message=prompt,
            default=social_defaults.get(key, ""),
        ).execute()
        if value:
            social[key] = value
    if social:
        result["social"] = social

    # Projects
    projects = _prompt_projects(defaults)
    if projects:
        result["projects"] = projects

    # Stats
    metrics = inquirer.checkbox(
        message="Which stats metrics to display?",
        choices=[
            {"name": "Commits", "value": "commits", "enabled": True},
            {"name": "Stars", "value": "stars", "enabled": True},
            {"name": "PRs", "value": "prs", "enabled": True},
            {"name": "Issues", "value": "issues", "enabled": True},
            {"name": "Repos", "value": "repos", "enabled": True},
        ],
    ).execute()
    if metrics:
        result["stats"] = {"metrics": metrics}

    # Languages
    print("\n--- Language Display Settings ---")
    exclude_input = inquirer.text(
        message="Languages to exclude (comma-separated, e.g. HTML,CSS,Shell):",
        default=",".join(defaults.get("languages", {}).get("exclude", [])),
    ).execute()
    if exclude_input.strip():
        exclude = [lang.strip() for lang in exclude_input.split(",") if lang.strip()]
    else:
        exclude = []

    max_display = inquirer.text(
        message="Max languages to display:",
        default=str(defaults.get("languages", {}).get("max_display", 8)),
    ).execute()
    result["languages"] = {
        "exclude": exclude,
        "max_display": int(max_display) if max_display.isdigit() else 8,
    }

    return result


def _project_entry(repo: str, arm: Optional[int], description: str) -> dict:
    """One featured project as it goes into the config. Without an arm, its languages decide where it sits."""
    entry = {"repo": repo}
    if arm is not None:
        entry["arm"] = arm
    entry["description"] = description
    return entry


def _prompt_projects(defaults: dict) -> list:
    """Collect featured projects in a loop."""
    default_projects = defaults.get("projects", [])
    projects = []

    add_project = inquirer.confirm(
        message="Add a featured project?",
        default=len(default_projects) > 0,
    ).execute()

    idx = 0
    while add_project:
        proj_default = default_projects[idx] if idx < len(default_projects) else {}

        repo = inquirer.text(
            message="Repository (owner/repo):",
            default=proj_default.get("repo", ""),
            validate=EmptyInputValidator("Repository cannot be empty."),
        ).execute()

        arm = inquirer.select(
            message="Which arm of the galaxy does it sit on?",
            choices=[
                {"name": "Let its languages decide", "value": None},
                {"name": "Arm 1", "value": 0},
                {"name": "Arm 2", "value": 1},
                {"name": "Arm 3", "value": 2},
            ],
            default=proj_default.get("arm"),
        ).execute()

        description = inquirer.text(
            message="Short description:",
            default=proj_default.get("description", ""),
        ).execute()

        projects.append(_project_entry(repo, arm, description))
        idx += 1

        add_project = inquirer.confirm(
            message="Add another project?",
            default=idx < len(default_projects),
        ).execute()

    return projects


def _build_config(essential: dict, arms: list, advanced: dict, look: Optional[dict] = None) -> dict:
    """Assemble the final config dictionary. look is what _prompt_look returns."""
    config = {
        "username": essential["username"],
        "profile": {
            "name": essential["name"],
            "tagline": essential.get("tagline", ""),
        },
        "galaxy_arms": arms,
    }

    # Merge advanced profile fields
    for key in ("bio", "company", "location", "philosophy"):
        if key in advanced:
            config["profile"][key] = advanced[key]

    for key in ("social", "projects", "stats", "languages"):
        if key in advanced:
            config[key] = advanced[key]

    if look:
        config["theme"] = {"dark": look["dark"], "light": look["light"], **look.get("colours", {})}
        config["motion"] = look["motion"]

    return config


def _save_config(config: dict) -> str:
    """Serialize config to YAML and write to config.yml. Return the path."""
    path = os.path.normpath(_CONFIG_PATH)

    header = (
        "# Galaxy Profile README Configuration\n"
        "# Generated by: python -m generator.main init\n"
        "#\n"
        "# Regenerate SVGs with:\n"
        "#   python -m generator.main\n"
        "#\n"
        "# Demo mode (no API calls):\n"
        "#   python -m generator.main --demo\n\n"
    )

    with open(path, "w") as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return path


def _offer_generation():
    """Ask if user wants to generate SVGs now."""
    generate_now = inquirer.confirm(
        message="Generate SVGs now?",
        default=True,
    ).execute()

    if generate_now:
        print("\nGenerating SVGs...")
        from generator.main import generate

        generate(argparse.Namespace(demo=False))
