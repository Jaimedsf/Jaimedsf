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

    def test_a_changed_colour_is_an_override_and_nothing_else_is(self, cfg):
        cfg["theme"] = {"void": "#112233"}
        assert validate_config(cfg)["themes"]["overrides"] == {"void": "#112233"}

    def test_defaults_applied_for_optional_fields(self, cfg):
        del cfg["stats"]
        del cfg["languages"]
        del cfg["theme"]
        result = validate_config(cfg)
        assert "metrics" in result["stats"]
        assert "exclude" in result["languages"]
        assert result["themes"]["overrides"] == {}

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

    def test_the_nine_colours_of_the_old_generator_are_no_longer_made_up(self, cfg):
        cfg["theme"] = {"dark": "cyanotype", "void": "#112233"}
        result = validate_config(cfg)
        assert result["theme"] == {"dark": "cyanotype", "void": "#112233"}      # what the user wrote, as written
        del cfg["theme"]
        assert "theme" not in validate_config(cfg)

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


class TestProjectFields:
    def test_a_description_that_yaml_read_as_a_boolean_is_rejected_clearly(self, cfg):
        cfg["projects"][0]["description"] = False        # `description: No` in YAML
        with pytest.raises(ConfigError, match="description must be text"):
            validate_config(cfg)

    def test_a_project_pinned_to_one_arm_and_listed_in_another_is_rejected(self, cfg):
        cfg["projects"][0]["arm"] = 0                    # galaxy-dev/nebula-ui
        cfg["galaxy_arms"][1]["repos"] = ["nebula-ui"]
        with pytest.raises(ConfigError, match="nebula-ui"):
            validate_config(cfg)

    def test_a_project_pinned_and_listed_in_the_same_arm_is_fine(self, cfg):
        cfg["projects"][0]["arm"] = 0
        cfg["galaxy_arms"][0]["repos"] = ["nebula-ui"]
        validate_config(cfg)


class TestLegacyColours:
    """Most configs carry the nine old default colours, copied from the example. Those are not customisations."""

    def test_colours_equal_to_the_old_defaults_are_not_overrides(self, cfg):
        assert validate_config(cfg)["themes"]["overrides"] == {}

    def test_a_changed_colour_is_an_override_and_the_untouched_ones_are_not(self, cfg):
        cfg["theme"]["void"] = "#101010"
        assert validate_config(cfg)["themes"]["overrides"] == {"void": "#101010"}

    def test_default_in_another_letter_case_is_still_the_default(self, cfg):
        cfg["theme"]["synapse_cyan"] = "#00D4FF"
        assert validate_config(cfg)["themes"]["overrides"] == {}

    def test_customised_card_colours_are_reported_as_having_no_effect(self, cfg, caplog):
        cfg["theme"]["nebula"] = "#222222"
        with caplog.at_level("WARNING"):
            validate_config(cfg)
        assert "theme.nebula" in caplog.text and "no longer" in caplog.text


class TestStatsAndLanguages:
    """Sections a user may leave empty, or mistype: a clear message, never a traceback from deep inside."""

    @pytest.mark.parametrize("section", ["stats", "languages"])
    def test_a_section_left_empty_gets_its_defaults(self, cfg, section):
        cfg[section] = None
        result = validate_config(cfg)
        assert result["stats"]["metrics"] == ["commits", "stars", "prs", "issues", "repos"]
        assert result["languages"] == {"exclude": [], "max_display": 8} or section == "stats"

    @pytest.mark.parametrize("section", ["stats", "languages"])
    def test_a_section_that_is_not_a_mapping_is_rejected(self, cfg, section):
        cfg[section] = ["stars"]
        with pytest.raises(ConfigError, match=f"'{section}' must be a mapping"):
            validate_config(cfg)

    @pytest.mark.parametrize("metrics", ["stars", 5, [["stars"]], [1, 2]])
    def test_metrics_must_be_a_list_of_names(self, cfg, metrics):
        cfg["stats"] = {"metrics": metrics}
        with pytest.raises(ConfigError, match="stats.metrics"):
            validate_config(cfg)

    def test_metrics_left_empty_get_the_default(self, cfg):
        cfg["stats"] = {"metrics": None}
        assert validate_config(cfg)["stats"]["metrics"] == ["commits", "stars", "prs", "issues", "repos"]

    @pytest.mark.parametrize("exclude", ["TypeScript", 7, [1, 2]])
    def test_exclude_must_be_a_list_of_language_names(self, cfg, exclude):
        cfg["languages"] = {"exclude": exclude}
        with pytest.raises(ConfigError, match="languages.exclude"):
            validate_config(cfg)

    def test_exclude_left_empty_excludes_nothing(self, cfg):
        cfg["languages"] = {"exclude": None, "max_display": 5}
        assert validate_config(cfg)["languages"] == {"exclude": [], "max_display": 5}

    @pytest.mark.parametrize("value", ["8", 3.5, 0, -1, True, None])
    def test_max_display_must_be_a_whole_number_of_at_least_one(self, cfg, value):
        cfg["languages"] = {"max_display": value}
        if value is None:
            assert validate_config(cfg)["languages"]["max_display"] == 8
        else:
            with pytest.raises(ConfigError, match="languages.max_display"):
                validate_config(cfg)

    def test_a_max_display_beyond_what_the_band_can_show_is_lowered_not_rejected(self, cfg, caplog):
        cfg["languages"] = {"max_display": 50}
        with caplog.at_level("WARNING"):
            assert validate_config(cfg)["languages"]["max_display"] == 20
        assert "max_display" in caplog.text


class TestRepositoryNames:
    """A name without an owner is the user's own repository; two owners can each have a repository of one name."""

    def test_the_same_name_under_two_owners_can_sit_on_two_arms(self, cfg):
        cfg["galaxy_arms"][0]["repos"] = ["alice/tool"]
        cfg["galaxy_arms"][1]["repos"] = ["bob/tool"]
        validate_config(cfg)

    def test_a_bare_name_and_the_users_own_full_name_are_the_same_repository(self, cfg):
        cfg["galaxy_arms"][0]["repos"] = ["nebula-ui"]
        cfg["galaxy_arms"][1]["repos"] = ["Galaxy-Dev/Nebula-UI"]
        with pytest.raises(ConfigError, match="pick one arm"):
            validate_config(cfg)

    def test_a_project_of_one_owner_does_not_clash_with_a_pin_of_another(self, cfg):
        cfg["projects"] = [{"repo": "alice/tool", "arm": 0}]
        cfg["galaxy_arms"][1]["repos"] = ["bob/tool"]
        validate_config(cfg)

    def test_a_project_description_left_empty_is_the_same_as_none_written(self, cfg):
        cfg["projects"] = [{"repo": "galaxy-dev/nebula-ui", "description": None}]
        validate_config(cfg)

    @pytest.mark.parametrize("arm", [True, False, "0", 1.0])
    def test_a_project_arm_must_be_a_whole_number(self, cfg, arm):
        cfg["projects"] = [{"repo": "galaxy-dev/nebula-ui", "arm": arm}]
        with pytest.raises(ConfigError, match="arm must be an integer"):
            validate_config(cfg)
