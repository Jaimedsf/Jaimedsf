# Changelog

## 2.0.0

The galaxy is now drawn from your data. A full description of what each image shows, and of what changes for an existing setup, is in the README ("How to read the galaxy" and "Migrating from version 1").

Added
- The header is a galaxy generated from your public repositories: one star per repository, brightness from stargazers, state from the last push, one arm per focus area that has repositories.
- A contribution chart drawn from the contribution calendar, replacing the stats card.
- Two palettes, `deep-sky` and `cyanotype`, each in a dark and a light version, chosen per theme with `theme.dark` and `theme.light`.
- A narrow layout of every image for phones. Each image is written in four files, and `README.profile.md` selects among them with `<picture>`.
- `motion: false` for still images. Visitors who ask for reduced motion always get still images.
- `galaxy_arms[].repos` to place repositories on an arm by hand; `projects[].arm` is now optional.
- Text drawn as glyph outlines (Spectral), measured exactly, so it looks the same everywhere.
- Every image carries a title and a description of its data for screen readers.
- A `Makefile` with `install`, `test`, `lint` and `demo`.

Changed
- Image sizes: the header is 850×430, contributions 850×254, languages 850×226 or taller, featured projects 850×214.
- Which arm a repository belongs to follows its languages.
- `galaxy_arms[].color` and the theme colours `nebula` and `star_dust` no longer have an effect. The other theme colours adjust the dark palette, and only when changed from their old defaults.
- The `init` wizard asks for palettes and motion instead of colours, and editing an existing config keeps everything the wizard does not ask about.
- The profile repository's own code no longer counts in the language shares.
- A run that cannot read the profile from GitHub fails and keeps the previous images, instead of writing zeros.
- With a token, all data comes from one GraphQL request.

Removed
- The arm legend, the radar chart of focus sectors, and the card frames.

## Before 2.0.0

The first version, from February 2026, was never tagged: four animated SVG images (galaxy header, stats card, tech stack, featured projects) generated from `config.yml`.
