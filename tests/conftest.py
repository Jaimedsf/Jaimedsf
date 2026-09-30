"""Shared fixtures for galaxy-profile tests."""

import copy

import pytest



@pytest.fixture
def sample_config():
    """A valid config in the shape version 1 documented: three arms with colours, the nine theme colours."""
    return {
        "username": "galaxy-dev",
        "profile": {
            "name": "Nyx Orion",
            "tagline": "Full Stack Developer & Open Source Explorer",
            "company": "Stellar Labs",
            "location": "San Francisco, CA",
            "bio": "Building tools that make developers' lives easier.",
            "philosophy": "The best code is the code that empowers others.",
        },
        "social": {
            "email": "nyx@stellarlabs.dev",
            "linkedin": "nyxorion",
            "website": "https://nyxorion.dev",
        },
        "galaxy_arms": [
            {"name": "Frontend", "color": "dendrite_violet", "items": ["TypeScript", "React", "CSS"]},
            {"name": "Backend", "color": "synapse_cyan", "items": ["Python", "Node.js", "PostgreSQL"]},
            {"name": "DevOps", "color": "axon_amber", "items": ["Docker", "GitHub Actions", "AWS"]},
        ],
        "projects": [
            {"repo": "galaxy-dev/nebula-ui", "arm": 0, "description": "A component library."},
            {"repo": "galaxy-dev/stargate-api", "arm": 1, "description": "High-performance API gateway."},
        ],
        "theme": {
            "void": "#080c14",
            "nebula": "#0f1623",
            "star_dust": "#1a2332",
            "synapse_cyan": "#00d4ff",
            "dendrite_violet": "#a78bfa",
            "axon_amber": "#ffb020",
            "text_bright": "#f1f5f9",
            "text_dim": "#94a3b8",
            "text_faint": "#64748b",
        },
        "stats": {"metrics": ["commits", "stars", "prs", "issues", "repos"]},
        "languages": {"exclude": ["HTML", "CSS", "Shell", "Makefile"], "max_display": 8},
    }


@pytest.fixture
def cfg(sample_config):
    """Return a deep copy of sample_config for mutation-safe tests."""
    return copy.deepcopy(sample_config)
