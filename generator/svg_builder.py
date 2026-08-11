"""SVG Builder — orchestrator connecting config, stats, and templates."""

from generator.templates import galaxy_header, stats_card, tech_stack, projects_constellation
from generator.utils import calculate_language_percentages


class SVGBuilder:
    """Builds all SVG assets from config and GitHub data.

    Expects a config dict that has already been through validate_config(),
    which resolves theme defaults and applies missing optional fields.
    """

    def __init__(self, config: dict, stats: dict, languages: dict):
        self.config = config
        self.stats = stats
        self.languages = languages
        self.theme = config["theme"]
        self.galaxy_arms = config.get("galaxy_arms", [])
        self.projects = config.get("projects", [])

    def render_galaxy_header(self) -> str:
        return galaxy_header.render(
            config=self.config,
            theme=self.theme,
            galaxy_arms=self._arms_with_detected_languages(),
            projects=self.projects,
        )

    def _arms_with_detected_languages(self) -> list:
        """Swap each arm's static item list for real detected languages.

        Keeps arm name/color from config, round-robins the top detected
        languages across arms in order. Falls back to the configured items
        for an arm if no language landed on it (e.g. more arms than langs).
        """
        lang_config = self.config.get("languages", {})
        header_max = len(self.galaxy_arms) * 6  # matches old static density (6 items/arm)
        lang_data = calculate_language_percentages(
            self.languages, lang_config.get("exclude", []), header_max
        )
        if not lang_data or not self.galaxy_arms:
            return self.galaxy_arms

        names = [d["name"] for d in lang_data]
        n = len(self.galaxy_arms)
        return [
            {**arm, "items": names[i::n]} if names[i::n] else arm
            for i, arm in enumerate(self.galaxy_arms)
        ]

    def render_stats_card(self) -> str:
        metrics = self.config["stats"]["metrics"]
        return stats_card.render(
            stats=self.stats,
            metrics=metrics,
            theme=self.theme,
        )

    def render_tech_stack(self) -> str:
        lang_config = self.config.get("languages", {})
        return tech_stack.render(
            languages=self.languages,
            galaxy_arms=self.galaxy_arms,
            theme=self.theme,
            exclude=lang_config.get("exclude", []),
            max_display=lang_config.get("max_display", 8),
        )

    def render_projects_constellation(self) -> str:
        return projects_constellation.render(
            projects=self.projects,
            galaxy_arms=self.galaxy_arms,
            theme=self.theme,
        )
