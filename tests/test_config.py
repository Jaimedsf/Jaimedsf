"""Tests for generator.config.validate_config."""

import pytest

from generator.config import ConfigError, validate_config


class TestValidateConfig:
    def test_valid_config_passes(self, cfg):
        result = validate_config(cfg)
        assert result["username"] == "galaxy-dev"
        assert result["profile"]["name"] == "Nyx Orion"

    def test_username_required(self, cfg):
        del cfg["username"]
        with pytest.raises(ConfigError, match="username"):
            validate_config(cfg)

    def test_username_empty_string(self, cfg):
        cfg["username"] = "   "
        with pytest.raises(ConfigError, match="username"):
            validate_config(cfg)

    def test_profile_name_required(self, cfg):
        cfg["profile"]["name"] = ""
        with pytest.raises(ConfigError, match="profile.name"):
            validate_config(cfg)

    def test_galaxy_arms_must_be_nonempty_list(self, cfg):
        cfg["galaxy_arms"] = []
        with pytest.raises(ConfigError, match="galaxy_arms"):
            validate_config(cfg)

    def test_galaxy_arm_without_name(self, cfg):
        cfg["galaxy_arms"] = [{"color": "synapse_cyan"}]
        with pytest.raises(ConfigError, match="name is required"):
            validate_config(cfg)

    def test_galaxy_arm_without_color_is_fine(self, cfg):
        cfg["galaxy_arms"] = [{"name": "Frontend"}]
        cfg["projects"] = []
        assert validate_config(cfg)["galaxy_arms"][0]["name"] == "Frontend"

    def test_project_arm_index_invalid(self, cfg):
        cfg["projects"] = [{"repo": "user/repo", "arm": 99}]
        with pytest.raises(ConfigError, match="arm must be an integer"):
            validate_config(cfg)

    def test_invalid_hex_color_in_theme(self, cfg):
        cfg["theme"] = {"void": "not-a-color"}
        with pytest.raises(ConfigError, match="valid hex color"):
            validate_config(cfg)

    def test_theme_override_merges_with_defaults(self, cfg):
        cfg["theme"] = {"void": "#112233"}
        result = validate_config(cfg)
        assert result["theme"]["void"] == "#112233"
        assert result["theme"]["synapse_cyan"] == "#00d4ff"  # default preserved

    def test_defaults_applied_for_optional_fields(self, cfg):
        del cfg["stats"]
        del cfg["languages"]
        del cfg["theme"]
        result = validate_config(cfg)
        assert "metrics" in result["stats"]
        assert "exclude" in result["languages"]
        assert "void" in result["theme"]

    def test_config_not_dict_fails(self):
        with pytest.raises(ConfigError, match="dict"):
            validate_config("not a dict")

    def test_config_none_fails(self):
        with pytest.raises(ConfigError, match="dict"):
            validate_config(None)


class TestAtlasKeys:
    """The keys added by the Atlas redesign: all optional, all with defaults."""

    def test_todays_example_config_gets_the_new_defaults(self, cfg):
        result = validate_config(cfg)
        assert result["themes"]["dark"] == "deep-sky"
        assert result["themes"]["light"] == "deep-sky"
        assert result["motion"] is True

    def test_palettes_can_be_chosen_per_mode(self, cfg):
        cfg["theme"] = {"dark": "cyanotype", "light": "deep-sky"}
        result = validate_config(cfg)
        assert (result["themes"]["dark"], result["themes"]["light"]) == ("cyanotype", "deep-sky")

    def test_unknown_palette_is_rejected(self, cfg):
        cfg["theme"] = {"dark": "neon"}
        with pytest.raises(ConfigError, match="theme.dark"):
            validate_config(cfg)

    def test_legacy_hex_colours_are_kept_as_overrides(self, cfg):
        cfg["theme"] = {"dark": "cyanotype", "void": "#000000", "synapse_cyan": "#00ffff"}
        result = validate_config(cfg)
        assert result["themes"]["overrides"] == {"void": "#000000", "synapse_cyan": "#00ffff"}

    def test_old_generator_still_gets_its_nine_colours(self, cfg):
        cfg["theme"] = {"dark": "cyanotype", "void": "#112233"}
        result = validate_config(cfg)
        assert result["theme"]["void"] == "#112233"
        assert "dark" not in result["theme"]

    def test_motion_can_be_switched_off(self, cfg):
        cfg["motion"] = False
        assert validate_config(cfg)["motion"] is False

    def test_motion_must_be_a_boolean(self, cfg):
        cfg["motion"] = "yes"
        with pytest.raises(ConfigError, match="motion"):
            validate_config(cfg)

    def test_arm_repos_must_be_a_list_of_names(self, cfg):
        cfg["galaxy_arms"][0]["repos"] = "nebula-ui"
        with pytest.raises(ConfigError, match="repos must be a list"):
            validate_config(cfg)

    def test_a_repository_cannot_sit_on_two_arms(self, cfg):
        cfg["galaxy_arms"][0]["repos"] = ["galaxy-dev/nebula-ui"]
        cfg["galaxy_arms"][1]["repos"] = ["Nebula-UI"]
        with pytest.raises(ConfigError, match="nebula-ui"):
            validate_config(cfg)

    def test_arm_repos_are_accepted(self, cfg):
        cfg["galaxy_arms"][2]["repos"] = ["infra-tools", "deploy-scripts"]
        assert validate_config(cfg)["galaxy_arms"][2]["repos"] == ["infra-tools", "deploy-scripts"]
