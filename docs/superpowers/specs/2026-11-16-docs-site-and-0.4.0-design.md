# Design: verdance documentation site and the 0.4.0 release

**Date:** 2026-11-16
**Status:** awaiting approval

## Intent and why

verdance is published on PyPI (0.3.0) but has no home of its own. Everything a
user needs lives in a 478-line README, which is thorough but is the wrong shape
for someone deciding whether to try the package, and the wrong shape for looking
up one config key. A logo set was added to `assets/logo/` on 2026-11-16; the
request is to put it to work on GitHub and on a documentation site, and to cut
the next release.

The release is overdue in its own right: everything under CHANGELOG
`[Unreleased]` has now landed upstream (PR #3 `codebase-hardening`, PR #4, and
PR #5 `t3-join-perf`, merged as `451106c`), including a change to a default that
users will feel.

## Goals

1. A documentation site at a stable URL, themed from the new logo, that splits
   the README into pages someone can navigate and link to.
2. A **config reference and Python API reference generated from the source**, so
   neither can drift from the code.
3. The logos used wherever they earn their place: site chrome, site home page,
   README header, and the repo's social preview card.
4. A README that works as a landing page rather than a manual — it stops being
   the canonical document, and points at the site.
5. verdance 0.4.0 released on PyPI, with a CHANGELOG entry that tells a user
   what changed for them.

## Non-goals

- No new prose about the science or methods. The site is a restructuring of
  material that already exists, plus navigation and a short home page. Where
  README wording is already good, it moves across unchanged — **except where it
  is wrong**, see "Stale content to fix" below.
- No tutorial or notebook gallery. `osm-rasterizer` has one; verdance has no
  committed notebooks and generating them needs real city data and a Spark run.
- No versioned docs (`mike`). One published version is enough at this stage.
- No API docs for private modules or internal analysis functions. The documented
  surface is the public API plus the config schema.
- **No behaviour change.** This release ships the code that is already on
  `master`. `src/` is touched only for the version string, for docstrings, and
  for comment-to-docstring conversion — no logic, no signatures, no defaults.

## Anti-goals

Things that would make this a failure even if the site builds:

- **A site that disagrees with the README.** Two half-maintained copies of the
  install instructions is worse than one long README. The split must leave a
  single home for each fact.
- **A docs build that needs Spark, GDAL or Java.** If the site cannot build in
  under a minute on a clean runner, it will rot.
- **Broken deep links.** The README's own anchors are linked from its internal
  contents bar and from the 0.3.0 PyPI page; a reader arriving at
  `#configuration` should still land somewhere sensible.
- **A hand-maintained config table.** The config is the thing users look up most;
  a second copy of it in Markdown would be stale within one release.

## Constraints

- **House convention.** `ancazugo/osm-rasterizer` already establishes the
  pattern: MkDocs Material, `mkdocstrings` for the API, logos under
  `docs/assets/logos/`, and a `docs.yml` workflow running `mkdocs gh-deploy`.
  Follow it rather than introduce a second way of doing docs — but see F1 below,
  where its workflow has a flaw not to copy.
- **Git workflow.** Push to `origin` (the fork) only; this reaches
  `sdgresearch/verdance` as a pull request. Nothing is pushed to `upstream`.
- **Docstring style.** verdance docstrings are plain prose — no `Args:` or
  numpy `Parameters` sections anywhere in `src/verdance/`. The API page must
  not promise structured parameter tables that the source cannot produce.
- **Lazy top-level imports.** `src/verdance/__init__.py:17-32` exposes `run`,
  `load_config` and `VerdanceConfig` through `__getattr__`, deliberately, so
  `import verdance` does not pull in PySpark. These names do not exist
  statically, which constrains how the API page is written (see below).
- **Version source.** `[tool.hatch.version]` reads `src/verdance/__init__.py`,
  so `__version__` is the single place the version is set.
- **`*.png` is currently gitignored.** `.gitignore` on `master` contains `*.png`.
  The working tree already has an uncommitted removal of that line; committing it
  is a prerequisite for the PNG logos, the README `<picture>` header and the
  social preview. `assets/` and `docs/` are both untracked today. `site/` (the
  MkDocs build output) must be added to `.gitignore`.

## Approaches

Three ways to turn a 478-line README into a site were considered.

| Approach | What it is | Trade-off |
|---|---|---|
| **Split into pages** (chosen) | README broken into ~10 topic pages plus generated config and API references; README shrinks to a landing page | Most work now, and the README stops being self-contained — but each topic gets a linkable URL and the references maintain themselves |
| Thin wrapper | Themed home page plus the whole README included as one "Documentation" page | Cheap and nothing duplicates, but the site is one enormous scrolling page — a README with a logo on it |
| Landing page only | Single marketing page; no references, no structure | Cheapest, but gives a user nowhere to look up a config key, which is the main thing they need |

The user chose **split into pages**. The thin wrapper was the main rival and was
dropped because it does not solve the problem that prompted the request: the
README is hard to navigate, and wrapping it keeps it hard to navigate.

On *how it gets built*, the user handed me the choice, so these are my calls:
MkDocs Material (matches `osm-rasterizer`, and its navigation and palette
features are what makes the split worth doing), `mkdocstrings` with Griffe's
static analysis (no imports, so no Spark in the docs build), and GitHub Pages
via `mkdocs gh-deploy`.

## The design

### Site structure

`docs/` maps onto the README's existing sections, so each fact moves to exactly
one page:

| Page | From README section(s) |
|---|---|
| `index.md` | Title, the 3-30-300 explanation, a short pitch, quick start — plus the logo |
| `installation.md` | Installation; Docker; the whole environment-variable table (README.md:110-115) |
| `quickstart.md` | Quick start; where caches, temporary files and logs land |
| `configuration.md` | Configuration; Input data; **the generated config reference** |
| `modules.md` | Modules; Usage and all its `###` subsections — Canopy source, Tree segmentation, Building heights, Visibility, Merge, Per-building outputs |
| `data-sources.md` | The building-height (README.md:309), terrain (README.md:351) and canopy source tables, with their licences |
| `visualising.md` | Visualising results; Output layout |
| `troubleshooting.md` | Troubleshooting |
| `development.md` | Development; Releasing; Licence and data |
| `api/` | New — a navigable API section generated from docstrings (below) |

Navigation uses Material's `navigation.sections` so these appear as a flat,
scannable list rather than nested folders, matching `osm-rasterizer`.

**Resolved: tables vs prose (reviewer B1) — my call.** `data-sources.md` owns the
three source tables outright; `modules.md` keeps the prose that explains when to
use each source and links across to the table. One home per fact. The sentence at
README.md:477 ("the tables above list each source's licence") is reworded to link
to `data-sources.md` when it moves to `development.md`.

**Resolved: "Where files go" (reviewer B2) — my call.** The section splits on a
conceptual seam, not an arbitrary one: the environment-variable table moves whole
to `installation.md` (all of it — `JAVA_HOME`, `JDK_HOME`, `SPARK_DRIVER_MEMORY`,
`GEE_PROJECT_NAME` — because every entry is setup-time configuration), while
`quickstart.md` keeps the prose about where caches, temp files and logs actually
land when you run something. The Troubleshooting cross-link (README.md:446) is
repointed at `installation.md`.

**Resolved: README contents bar (reviewer F9) — my call.** The hand-maintained
`**Contents:**` anchor bar at README.md:13 is deleted, not migrated. The site nav
replaces it, and the shortened README has no need for it.

### The config reference

The user chose to convert the schema's `#` comments into attribute docstrings.
In `src/verdance/config/schema.py`, each field's leading `#` comment becomes a
string literal directly beneath the field — the standard way to document
dataclass attributes, and the form Griffe reads:

```python
# before
    # CRS all layers are reprojected to
    crs: str = "EPSG:27700"

# after
    crs: str = "EPSG:27700"
    """CRS all layers are reprojected to."""
```

This is a pure docs change — no logic, no defaults, no field order — and it makes
the config reference generate from the single source that already exists, which
is what the "no hand-maintained config table" anti-goal demands.

`configuration.md` renders `VerdanceConfig` **and the nested dataclasses it
refers to** — `DataPaths`, `ColumnMapping`, `OutputPaths`, `HeightsConfig`,
`VisibilityConfig`, `TerrainConfig`, `TileSystemConfig`, `OSMConfig`,
`OvertureConfig`, `OpenBuildingsConfig`, `TreeSegmentationConfig`
(schema.py:243-268). Documenting them is not optional politeness: unresolved
cross-references to them are warnings, and warnings fail `--strict` (reviewer F5).

### The API section

**Scope widened at the user's request** ("add the api docstring as part of the
website so it's easier to navigate"): the API reference covers the whole package,
not just the three public names. This is cheap because coverage is already high —
`t3`, `t30`, `t30_buildings`, `t300`, `tree_count`, `merge`, `pipeline`, `osm`,
`overture`, `utils/data_processing` and `utils/manifest` are at 100%.

~250 public objects on one page would be a wall, so the reference is a nav
section of six pages, grouped by what a reader is trying to do:

| Page | Covers |
|---|---|
| `api/index.md` | The public API: `run`, `load_config`, and a pointer to the config reference |
| `api/analysis.md` | `t3`, `t30`, `t30_buildings`, `t300`, `tree_count`, `merge` |
| `api/pipeline.md` | `pipeline`, `config.loader`, `dggs` |
| `api/data-sources.md` | `osm`, `overture`, `open_buildings`, `heights/*`, `terrain` |
| `api/optional.md` | `optional/*` — canopy sources, spectral, tree segmentation, visibility |
| `api/utils.md` | `utils/*`, `viz/*` |

Material's `navigation.indexes` makes `api/index.md` the section landing page, so
the section is one click from the top nav.

About 20 public objects have no docstring — `config.loader.load_config`, the five
`dggs` backends, four `heights` sources, `visibility.inputs` and
`visibility.params`, `terrain`, and three `viz` helpers. They get one-line
docstrings in the same docs-only pass as the schema conversion, since an API page
that renders bare signatures is worse than no API page.

Because the public names are lazy re-exports, `::: verdance.run` would fail —
Griffe reads the source statically and sees only `__getattr__` (reviewer F4
confirms). The page targets the real definitions and renames the headings:

```markdown
::: verdance.api.run
    options:
      heading: verdance.run
      heading_level: 2
      show_root_full_path: false
```

`heading_level` alone renames nothing (reviewer F3); `heading` is what does it.
Same treatment for `verdance.config.loader.load_config`. A note at the top of the
page records that all three names are importable directly from `verdance`.

`load_config` (loader.py:38) has no docstring and gets one, as part of the same
docs-only pass as the schema conversion.

Handler configuration, with `paths` at **handler level — a sibling of `options`,
not a member of it** (reviewer F2):

```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          paths: ["src"]
          options:
            docstring_style: google
            filters: ["!^_"]
            show_source: true
```

`paths: ["src"]` is what lets Griffe find the package without the project being
installed.

### Theme and logo usage

The palette comes from the mark. The **dark** logo variants use `#2b8f4a` and
`#52c065`; the **light** variants use `#3fa34d` and `#1f7a3f` (reviewer F6
corrected an error here — `#3fa34d` is lighter than `#2b8f4a`, not darker).
Primary is `#2b8f4a` in the light scheme and the lighter `#3fa34d` in the dark
scheme, so text on the navbar stays legible either way; accent is `#52c065`. Set
through `docs/assets/stylesheets/verdance.css` overriding `--md-primary-fg-color`
and `--md-accent-fg-color`.

Which logo goes where:

| Place | Asset |
|---|---|
| Site navbar | `verdance-icon-mono-inverse.svg` (white mark on the green bar, site name beside it) |
| Favicon | `verdance-icon-light.svg` |
| `index.md` hero | `verdance-logo-light.svg` / `verdance-logo-dark.svg` |
| README header | `verdance-logo-light.png` / `-dark.png` via a `<picture>` element with `prefers-color-scheme` |
| Repo social preview | `verdance-logo-light.png` — **uploaded by hand** in repo settings; GitHub has no API for it, so this is a step for the user, not the builder |

The hero pair uses Material's `#only-light` / `#only-dark` image suffixes, as
`osm-rasterizer/docs/index.md:3-4` already does, rather than bespoke CSS. This
needs `attr_list`, which is already in the markdown extensions.

**Asset location — my call.** `assets/logo/` stays the canonical brand kit with
all 24 files. MkDocs can only serve files under `docs/`, so the **four** variants
the site serves are copied to `docs/assets/logos/` (reviewer F7 — the two PNGs
are for GitHub, not the site, and are not copied). A copy, not a symlink: MkDocs'
symlink handling is version-dependent and these are small static files that change
rarely. The README references `assets/logo/` directly.

### Build and deployment

A `docs` dependency group in `pyproject.toml`: `mkdocs>=1.6` (pinned explicitly —
`exclude_docs` requires it, and `osm-rasterizer` pins it too), `mkdocs-material`,
`mkdocstrings[python]`.

**The workflow must not copy `osm-rasterizer`'s run step.** That repo runs a bare
`uv run mkdocs gh-deploy --force`, and a bare `uv run` re-syncs the default
environment — installing the project plus the `dev` group, which pins
`gdal==3.10.0` and drags in PySpark (reviewer F1). That is precisely the "docs
build that needs Spark, GDAL or Java" anti-goal. Both steps carry
`--only-group docs`:

```yaml
- run: uv sync --only-group docs
- run: uv run --only-group docs mkdocs gh-deploy --force
```

`.github/workflows/docs.yml` otherwise follows the house pattern: on push to
`master`, check out, configure the `github-actions[bot]` git identity, set up uv
with Python 3.12, restore the `mkdocs-material` cache, install, deploy.
`permissions: contents: write`, because `gh-deploy` pushes to `gh-pages`.

`mkdocs.yml` sets `exclude_docs: superpowers/` so these design documents are not
published as part of the site.

**Deployment target — the user chose `sdgresearch.github.io/verdance`**, the
canonical org repo, matching `Homepage` in `pyproject.toml`. Consequences,
recorded so they are not a surprise: the first deploy happens only after a PR
merges into `sdgresearch/verdance`, and only once an admin enables Pages (source
= `gh-pages`) and Actions write access there. Until both are done, the docs URL
and badge 404. These are handover steps for the user, not build steps.

### Stale content to fix

Two things found during review that are wrong today and must not be carried
across unchanged (they are corrections, not new prose):

- **README.md:393** says "T3's default `rdd` query path omits buildings with no
  tree in the buffer (the `sql` path reports them as 0)". The default is now
  `sql` — README.md:228 already says so, so the README contradicts itself.
- **README.md:465-473** ("Releasing") tells the reader to run
  `uvx twine upload dist/*`, which contradicts
  `.github/workflows/release.yml`'s trusted-publishing flow.

### The 0.4.0 release

- `__version__` → `0.4.0` in `src/verdance/__init__.py:12` (the only place).
- CHANGELOG `[Unreleased]` → `## [0.4.0] - 2026-11-16`, a fresh empty
  `[Unreleased]`, and the link block at the foot updated with a `0.4.0` compare
  link and release tag.
- CHANGELOG `Added` lines for the documentation site and the logo set.
- `pyproject.toml` gains
  `Documentation = "https://sdgresearch.github.io/verdance/"` under
  `[project.urls]`.
- README gains a badge row: PyPI version, Python versions, CI status, docs,
  licence.
- `.gitignore`: commit the `*.png` removal; add `site/`.

Minor-version rather than patch because `--query_method` now defaults to `sql`,
which changes the rows a T3 run writes per geo code. Under 0.x, a behaviour
change belongs in the minor position.

Publication itself is **not** part of this work. The release workflow uses PyPI
trusted publishing, which has not been configured on PyPI yet; tagging and
publishing stay with the user.

## What's left to the builder

- Exact prose on `index.md` beyond the material lifted from the README, and how
  much of the quick start to repeat there (some repetition on a landing page is
  accepted; it is the one place the anti-goal bends).
- Whether `troubleshooting.md` is large enough to stand alone or folds into
  `development.md` — judge it once the content is moved.
- Badge URLs and ordering.
- `repo_url` / `repo_name` and the nav titles for the ten pages.
- Nothing needs doing about README anchors in `examples/*.yaml`: the reviewer
  grepped and none contain one. Only README's own internal links matter, and
  both are handled above.

## Verification

- `uv run --only-group docs mkdocs build --strict` passes with no warnings.
  `--strict` is the real gate here: it catches both the moved-link breakage and
  the unresolved API cross-references described above. Note the reviewer could
  not run this (mkdocs is not in the active env), so the builder installs the
  docs group first; if the network blocks it, CI is the fallback and that must be
  stated plainly rather than claimed as passing.
- The config reference renders every `VerdanceConfig` field with its text, and
  the API page renders `run` and `load_config` under their public names.
- `uv run pytest -q` and `ruff check .` still pass — `src/` changes are
  docstrings and a version string, so nothing should move.
- The site is checked in both colour schemes for the logo swap and for text
  legibility on the green navbar.
