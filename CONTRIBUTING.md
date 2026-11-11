# Contributing to verdance

Thanks for your interest in improving verdance. This guide covers the git
workflow, local setup, tests and code style.

## Git workflow

The canonical repository is **[`sdgresearch/verdance`](https://github.com/sdgresearch/verdance)**.
Contributors work on a fork and open pull requests against it.

1. Fork `sdgresearch/verdance` on GitHub.
2. Clone your fork and add the org repo as `upstream`:

   ```bash
   git clone git@github.com:<you>/verdance.git && cd verdance
   git remote add upstream git@github.com:sdgresearch/verdance.git
   ```

3. Start every change on a new branch off an up-to-date `master`:

   ```bash
   git fetch upstream
   git switch master && git merge --ff-only upstream/master
   git switch -c my-feature master
   ```

4. Push the branch to your fork and open a pull request into
   `sdgresearch/verdance`. Keep pull requests focused and describe what changed
   and why. CI (tests + lint) must pass before review.

## Development setup

verdance needs **Python 3.12 or 3.13** and **Java 11-17** (Spark 3.5 runs on
Java 17 at most). The project is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # create .venv with runtime + dev dependencies
```

Make sure a Java 17 is visible to Spark, e.g.:

```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
java -version           # should report 17
```

The first Spark-based run downloads the Sedona jars (~110 MB, once). If you keep
the environment somewhere other than the repo's `.venv`, activate it and pass
`--active` (`uv sync --active`, `uv add --active <package>`).

## Running tests

```bash
uv run pytest           # the full suite (Spark tests need Java 17)
uv run pytest -q tests/test_merge_all.py   # a single file
```

Registered markers (see `pyproject.toml`): `slow`, `spark`, `network`. Use them
to select or skip, e.g. `uv run pytest -m "not network"`.

### Keep caches and temp files out of the repo and `$HOME`

verdance writes nothing to the directory you run it from, and on shared machines
the caches should go to a large disk. Point them there before running:

```bash
export TMPDIR=/scratch/<you>/tmp
export VERDANCE_CACHE_DIR=/scratch/<you>/verdance_cache
export VERDANCE_IVY_DIR=/scratch/<you>/ivy2
export VERDANCE_DUCKDB_EXTENSIONS=/scratch/<you>/duckdb-ext
```

Never commit caches, downloaded data, generated outputs or local city configs.

## Code style

Linting uses [ruff](https://docs.astral.sh/ruff/), configured in
`pyproject.toml`. The blocking check is:

```bash
uvx ruff check .
```

Formatting is not yet enforced repo-wide, so do not reformat files unrelated to
your change. You can preview formatting with `uvx ruff format --check .`. If you
introduce new code, keep it close to ruff's default formatting and keep imports
tidy so adopting `ruff format` and import sorting later is painless.

## Releasing (maintainers)

Releases are published to PyPI by the `release.yml` workflow when a `v*` tag is
pushed, using PyPI Trusted Publishing (no stored token). Bump `__version__` in
`src/verdance/__init__.py`, update `CHANGELOG.md`, then tag:

```bash
git tag -a v0.3.1 -m "verdance 0.3.1" && git push upstream v0.3.1
```

The Trusted Publisher must be configured once on PyPI before the first tagged
release (project `verdance`, owner `sdgresearch`, workflow `release.yml`,
environment `pypi`).
