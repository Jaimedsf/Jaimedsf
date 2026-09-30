"""Config validation and defaults for the Galaxy Profile generator."""

import logging
import re

from generator.themes import PALETTES

logger = logging.getLogger(__name__)

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# The nine colours version 1 read from `theme`, with its defaults. A config copied from the old
# example carries all nine unchanged, so a colour equal to its default here is not an override.
LEGACY_THEME = {
    "void": "#080c14",
    "nebula": "#0f1623",
    "star_dust": "#1a2332",
    "synapse_cyan": "#00d4ff",
    "dendrite_violet": "#a78bfa",
    "axon_amber": "#ffb020",
    "text_bright": "#f1f5f9",
    "text_dim": "#94a3b8",
    "text_faint": "#64748b",
}

# theme colours that painted card backgrounds and borders; the Atlas plates have neither
RETIRED_COLOURS = ("nebula", "star_dust")

# theme keys that choose a palette instead of overriding a colour
PALETTE_KEYS = ("dark", "light")


def repo_key(name: str) -> str:
    """How a repository is compared across arms: by name, without owner, ignoring case."""
    return str(name).split("/")[-1].lower()


class ConfigError(ValueError):
    """Raised when config.yml has invalid or missing data."""


def validate_config(config: dict) -> dict:
    """Validate and apply defaults to a parsed config dict.

    Args:
        config: raw dict from yaml.safe_load()

    Returns:
        config dict with defaults applied for optional fields

    Raises:
        ConfigError: if required fields are missing or values are invalid
    """
    if not isinstance(config, dict):
        raise ConfigError("Config must be a YAML mapping (dict).")

    # username — required
    username = config.get("username")
    if not username or not isinstance(username, str) or not username.strip():
        raise ConfigError("'username' is required and must be a non-empty string.")

    # profile.name — required
    profile = config.get("profile", {})
    if not isinstance(profile, dict):
        raise ConfigError("'profile' must be a mapping.")
    if not profile.get("name"):
        raise ConfigError("'profile.name' is required.")

    # galaxy_arms — required, must be a list
    galaxy_arms = config.get("galaxy_arms", [])
    if not isinstance(galaxy_arms, list) or not galaxy_arms:
        raise ConfigError("'galaxy_arms' must be a non-empty list.")
    for i, arm in enumerate(galaxy_arms):
        if not isinstance(arm, dict):
            raise ConfigError(f"galaxy_arms[{i}] must be a mapping.")
        if not arm.get("name"):
            raise ConfigError(f"galaxy_arms[{i}].name is required.")
        if not isinstance(arm.get("items", []), list):
            raise ConfigError(f"galaxy_arms[{i}].items must be a list.")
        repos = arm.get("repos", [])
        if not isinstance(repos, list) or not all(isinstance(r, str) for r in repos):
            raise ConfigError(f"galaxy_arms[{i}].repos must be a list of repository names.")

    # a repository can be pinned to one arm only
    pinned = {}
    for i, arm in enumerate(galaxy_arms):
        for repo in arm.get("repos", []):
            key = repo_key(repo)
            if key in pinned and pinned[key] != i:
                raise ConfigError(
                    f"repository '{key}' is listed in galaxy_arms[{pinned[key]}] and galaxy_arms[{i}]; "
                    "pick one arm."
                )
            pinned[key] = i

    # projects — optional, validate entries if present
    projects = config.get("projects", [])
    if not isinstance(projects, list):
        raise ConfigError("'projects' must be a list.")
    for i, proj in enumerate(projects):
        if not isinstance(proj, dict):
            raise ConfigError(f"projects[{i}] must be a mapping.")
        if not proj.get("repo"):
            raise ConfigError(f"projects[{i}].repo is required.")
        arm_idx = proj.get("arm", 0)
        if not isinstance(arm_idx, int) or arm_idx < 0 or arm_idx >= len(galaxy_arms):
            raise ConfigError(
                f"projects[{i}].arm must be an integer from 0 to {len(galaxy_arms) - 1}."
            )
        if "description" in proj and not isinstance(proj["description"], str):
            raise ConfigError(
                f"projects[{i}].description must be text; put it in quotes (got {proj['description']!r})."
            )
        key = repo_key(proj["repo"])
        if "arm" in proj and pinned.get(key, arm_idx) != arm_idx:
            raise ConfigError(
                f"repository '{key}' is listed in galaxy_arms[{pinned[key]}].repos but projects[{i}].arm "
                f"is {arm_idx}; pick one arm."
            )

    # theme — optional, validate hex codes
    user_theme = config.get("theme", {})
    if not isinstance(user_theme, dict):
        raise ConfigError("'theme' must be a mapping.")
    palettes = {}
    overrides = {}
    for key, value in user_theme.items():
        if key in PALETTE_KEYS:
            if value not in PALETTES:
                raise ConfigError(
                    f"theme.{key} must be one of {', '.join(PALETTES)}, got '{value}'."
                )
            palettes[key] = value
        elif not isinstance(value, str) or not HEX_COLOR_RE.match(value):
            raise ConfigError(
                f"theme.{key} must be a valid hex color (e.g. #00d4ff), got '{value}'."
            )
        elif value.lower() == LEGACY_THEME.get(key, "").lower():
            # the old default, usually copied from the example config: not a customisation
            continue
        elif key in RETIRED_COLOURS:
            logger.warning("theme.%s no longer has an effect: the plates have no card backgrounds or borders.", key)
        else:
            overrides[key] = value

    config["themes"] = {
        "dark": palettes.get("dark", PALETTES[0]),
        "light": palettes.get("light", PALETTES[0]),
        "overrides": overrides,
    }

    # motion — optional flag
    motion = config.get("motion", True)
    if not isinstance(motion, bool):
        raise ConfigError(f"'motion' must be true or false, got '{motion}'.")
    config["motion"] = motion

    # Apply other defaults
    config["profile"].setdefault("tagline", "")
    config["profile"].setdefault("philosophy", "")
    config.setdefault("social", {})
    config.setdefault("projects", [])
    config.setdefault("stats", {}).setdefault(
        "metrics", ["commits", "stars", "prs", "issues", "repos"]
    )
    lang_cfg = config.setdefault("languages", {})
    lang_cfg.setdefault("exclude", [])
    lang_cfg.setdefault("max_display", 8)

    return config
