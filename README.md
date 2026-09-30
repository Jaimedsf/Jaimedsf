# galaxy-profile

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-brightgreen.svg)

A GitHub profile README generator. It reads your public repositories and your contribution calendar and draws them as four SVG images: a galaxy in which every star is one of your repositories, your year of contributions as a light curve, your languages as a spectrum, and your featured projects as a short catalogue of stars.

Nothing in the galaxy is there for decoration except the dust. Two profiles give two different galaxies.

## Preview

<div align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="./assets/generated/galaxy-header-mobile-light.svg">
    <source media="(max-width: 600px)" srcset="./assets/generated/galaxy-header-mobile.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/generated/galaxy-header-light.svg">
    <img src="./assets/generated/galaxy-header.svg" width="850" alt="A galaxy drawn from the sample profile: one star per repository, one arm per focus area">
  </picture>
</div>

<br/>

<div align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="./assets/generated/stats-card-mobile-light.svg">
    <source media="(max-width: 600px)" srcset="./assets/generated/stats-card-mobile.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/generated/stats-card-light.svg">
    <img src="./assets/generated/stats-card.svg" width="850" alt="Contributions over the last year, week by week">
  </picture>
</div>

<br/>

<div align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="./assets/generated/tech-stack-mobile-light.svg">
    <source media="(max-width: 600px)" srcset="./assets/generated/tech-stack-mobile.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/generated/tech-stack-light.svg">
    <img src="./assets/generated/tech-stack.svg" width="850" alt="Languages of the public repositories and the declared stack">
  </picture>
</div>

<br/>

<div align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: light)" srcset="./assets/generated/projects-constellation-mobile-light.svg">
    <source media="(max-width: 600px)" srcset="./assets/generated/projects-constellation-mobile.svg">
    <source media="(prefers-color-scheme: light)" srcset="./assets/generated/projects-constellation-light.svg">
    <img src="./assets/generated/projects-constellation.svg" width="850" alt="Featured projects">
  </picture>
</div>

These are generated from sample data (`python -m generator.main --demo`).

## How to read the galaxy

| What you see | What it is |
|---|---|
| A star | One public repository. Forks and the profile repository itself are left out. Up to 48 are drawn: featured projects first, then by stargazers. |
| How bright a star is | Its stargazers, on a logarithmic scale. Brighter means a wider glow and longer rays, not a bigger disc. |
| A star in the theme's accent colour | Pushed to in the last month. The brightest of these, and the named ones, have a glow that breathes. |
| A star in the plain colour | Pushed to in the last year. |
| A hollow ring | Dormant: no push for more than a year. |
| An arm | A focus area from your config that has at least one repository. An area with none is not drawn. If no repository matches any area, two unnamed arms are drawn and every star floats between them. |
| The length of an arm | How many repositories it has. |
| Where a star sits on its arm | The order of creation: the oldest near the core, the newest at the tip. |
| A star between the arms | A repository whose code matches none of your focus areas. |
| A name next to a star | Your featured projects and your brightest repository: at most four names. |
| Dust and the faint stars in the background | Nothing. They give the galaxy its body. |

A repository joins the focus area whose `items` account for the largest share of its code, if that share is 15% or more. You can also place it yourself (see the configuration reference).

The other three images:

- Contributions. Each dot is one week. The curve is a five-week moving average, and the star marks the busiest week. Beside the title, up to three counters.
- Languages. One band, split by bytes of code across your public repositories that are not forks (the profile repository itself is left out). Below it, the stack you declare in your focus areas: each area's items on up to two lines, cut with an ellipsis when there are more.
- Featured projects. Up to three, brightest first, lettered α, β, γ the way stars are named within a constellation. Each is drawn with the same star it has in the galaxy.

## Themes, phones and motion

Each image is written in four files:

| File | For |
|---|---|
| `galaxy-header.svg` | GitHub's dark theme, wide screens. This is the default. |
| `galaxy-header-light.svg` | GitHub's light theme. |
| `galaxy-header-mobile.svg` | Dark theme, narrow screens: a layout of its own, 390 units wide, with type you can read on a phone. |
| `galaxy-header-mobile-light.svg` | Light theme, narrow screens. |

[`README.profile.md`](README.profile.md) wraps each image in a `<picture>` element so the visitor's browser picks the right file. If you would rather keep things simple, use the `<img>` line alone and everyone gets the default.

There are two palettes, and you choose one for each theme:

- `deep-sky`: a night sky, with stars in their real colours (blue for the active ones, warm for the dormant).
- `cyanotype`: two inks, Prussian blue and paper white, with one warm colour for what is alive.

The images move. The galaxy gathers out of a scattered field of stars, then its dust streams along the arms while the spiral itself stays still; the contribution curve draws itself and a point of light runs along it; a sweep of light opens the language band. All of it is CSS animation inside the SVG, and:

- visitors whose system asks for reduced motion get still images, complete;
- `motion: false` in the config writes still images for everyone;
- an image that is off screen has its clock paused by the browser, so the entrance plays when you scroll to it (checked in Chrome).

A tool that captures an image at the very first instant of its animation (some screenshot and link-preview services) catches the entrance before the text has faded in. If you need captures, generate with `motion: false`.

Text is drawn as outlines of [Spectral](https://github.com/productiontype/Spectral), so it looks the same in every browser and needs no font on the visitor's side. Text the font does not cover (CJK, emoji and others) falls back to the system's serif.

## Quick Start

1. Fork this repo (or use "Use this template") and rename it to your GitHub username.
2. Create your config, by hand or with the wizard:
   ```bash
   cp config.example.yml config.yml        # then edit it
   # or
   pip install -r requirements.txt
   python -m generator.main init
   ```
3. Replace `README.md` with the contents of [`README.profile.md`](README.profile.md) and customize the social links.
4. Commit `config.yml` and push. The GitHub Action generates the images and commits them.

> This repo ships with `--demo` mode enabled in the GitHub Action so it works out of the box with sample data. After creating your `config.yml`, edit `.github/workflows/generate-profile.yml` and change the generate step from
> ```yaml
> run: python -m generator.main --demo
> ```
> to
> ```yaml
> run: python -m generator.main
> ```
> so it reads your real profile.

> The first run may need a manual trigger: Actions > "Generate Profile SVGs" > "Run workflow".

## Configuration Reference

All configuration lives in `config.yml`. See [`config.example.yml`](config.example.yml) for a commented template.

| Key | Description |
|---|---|
| `username` | Your GitHub username (required). |
| `profile` | `name` (required), `tagline` and `philosophy` are drawn in the header. `company`, `location` and `bio` are not drawn; they are kept for your own reference. |
| `social` | Email, LinkedIn handle, website URL. Not drawn either: write the links in your README. |
| `galaxy_arms` | Your focus areas. Each has a `name`, a list of `items` (languages and tools) and, optionally, `repos`: repository names to place on that arm whatever their languages say. |
| `projects` | Featured repositories. Each has `repo` (`owner/name`; another owner's repository is fine), an optional `description` (defaults to the repository's own) and an optional `arm` (index of a focus area, from 0) to place it yourself. |
| `theme.dark`, `theme.light` | `deep-sky` or `cyanotype`, chosen separately for GitHub's dark and light themes. Default: `deep-sky` for both. |
| `theme.<colour>` | Optional hex colours that adjust the dark palette: `void` (background), `text_bright` (text), `text_dim` (secondary text), `text_faint` (hairlines), `synapse_cyan` (active stars), `axon_amber` (dormant stars); these last two and `dendrite_violet` also recolour the dust, in the order the palette lists its dust colours. A colour equal to its version 1 default is ignored. |
| `motion` | `true` (default) or `false` for still images. |
| `stats.metrics` | Which counters go beside the contribution chart, in order: `stars`, `prs`, `issues`, `repos`. Up to three are shown. `commits` is accepted and is the chart's own title. |
| `languages` | Languages to `exclude` and how many to show (`max_display`, up to 20). |

## Migrating from version 1

An existing `config.yml` works without changes, and the four file names you already reference are still written. What you will notice:

- The images have new sizes. The header is 850×430 (it was 850×280), contributions 850×254 (850×120 without a calendar), languages 850×226 or taller, featured projects 850×214 (850×110 with none). An `<img>` with `width="850"` and no height adapts by itself.
- Twelve new files appear in `assets/generated/` next to the four you had. To use them, replace the image lines in your README with the `<picture>` blocks from [`README.profile.md`](README.profile.md). Run the generator once before you do, so the files exist.
- The galaxy is drawn from your repositories now. Which arm a repository sits on follows its languages; use `galaxy_arms[].repos` or `projects[].arm` to decide it yourself. A focus area with no repository is not an arm, though it still shows in the languages image.
- `galaxy_arms[].color` no longer has an effect, and the legend is gone: arms are told apart by their names, written along them.
- The nine `theme` colours are now adjustments to the dark palette. A colour left at its old default is ignored, so a config copied from the old example gets the new palette as designed. `nebula` and `star_dust` painted card backgrounds and borders, which no longer exist.
- The first counter of the old stats card, commits, is now the title of the contribution chart: contributions in the last year, from your contribution calendar.
- The contribution calendar needs a token. In GitHub Actions the workflow's own `GITHUB_TOKEN` is enough. Without one, that image shrinks to the counters alone.
- Language shares are computed over your 100 most-starred public repositories (the 40 most-starred when there is no token), and the profile repository itself no longer counts.
- If GitHub cannot be reached or answers with an error, the run now fails and leaves the previous images in place. Version 1 wrote images full of zeros.

## Local Development

```bash
git clone https://github.com/YOUR_USERNAME/galaxy-profile.git
cd galaxy-profile
make install        # creates .venv and installs the development requirements
make test
make demo           # writes the sixteen sample images to assets/generated/
```

Without `make`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m generator.main --demo
pytest
```

Generating from a real profile:

```bash
cp config.example.yml config.yml                           # and edit it
GITHUB_TOKEN=ghp_your_token_here python -m generator.main
```

To create a token: [github.com/settings/tokens](https://github.com/settings/tokens) > Generate new token (classic) > select the `read:user` scope. Without a token the generator uses the public REST API: no contribution calendar, languages read for your 40 most-starred repositories only, and at most 60 requests an hour. If that limit is reached the run stops and says so.

To look at the result, open any file in `assets/generated/` in a browser.

The tests need no network and no token. They render every image in every variant from the sample data and check, among other things, that nothing is invisible once the animation has played, that every text stays inside its image, that the same input gives the same bytes, and that each file stays under its size budget.

## How the GitHub Action Works

The workflow (`.github/workflows/generate-profile.yml`) runs:

- every 12 hours;
- on push, when `config.yml` or `generator/**` change;
- manually, from the Actions tab.

It generates the images and commits them with the message `chore: update profile SVGs [skip ci]`. The output only changes when your data does, so most runs commit nothing.

## Troubleshooting

- "Could not read the profile from GitHub". The token is invalid or expired, the username is wrong, GitHub answered with an error, or the rate limit was reached without a token. The message says which. The previous images are kept.
- The contribution image shows only numbers. The run had no token, so there was no calendar to draw.
- A repository is on the wrong arm, or on none. List it under `repos` in the focus area where it belongs. A name that matches no star is reported in the log.
- A repository is missing from the galaxy. Forks are left out unless you feature them in `projects`, and only the 48 brightest are drawn.
- Text looks different from the rest. It has characters Spectral does not cover and was drawn in the system's serif.

## Contributing

1. Bug reports: open an issue with steps to reproduce and what you expected.
2. Feature suggestions: open an issue describing the feature and why it is useful.
3. Pull requests: fork, branch from `main`, run `make test`, look at the images in a browser, and open a PR with a clear description.

Each image is one module in `generator/plates/`: a pure function of its data, a theme and two flags. `tests/contract/` holds the rules every image must keep in every variant; a new image gets them by being listed in `generator/build.py`. When a change to the output is intended, `UPDATE_GOLDEN=1 pytest tests/contract -k digest` records the new reference and `make demo` refreshes the previews.

## Architecture

```
generator/
├── main.py         # Command line: config in, sixteen SVG files out
├── cli_init.py     # The `init` wizard
├── config.py       # Config validation and defaults
├── data.py         # GitHub GraphQL and REST, and the sample data: one snapshot of a profile
├── model.py        # What each image shows: arms and stars, weekly series, language shares, featured projects
├── build.py        # Every image in every variant
├── themes.py       # The two palettes, dark and light
├── typeset.py      # Text as glyph outlines: measure, set on a line, set along a curve
├── svg.py          # Shared pieces: particles, the repository star, the travelling light, the frame
├── motion.py       # The motion switch and the animation catalogue
├── fonts/          # Glyph outlines and metrics, built by tools/build_font_atlas.py
└── plates/
    ├── galaxy.py         # The galaxy header
    ├── contributions.py  # The contribution light curve
    ├── languages.py      # The language band and the declared stack
    └── featured.py       # Featured projects
```

## Credits

Type is [Spectral](https://github.com/productiontype/Spectral) by Production Type, with Greek letters from [Noto Serif](https://github.com/notofonts/noto-fonts), both under the SIL Open Font License (see `assets/fonts/`).
