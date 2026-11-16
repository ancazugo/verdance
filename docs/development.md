# Development

```bash
git clone https://github.com/sdgresearch/verdance.git && cd verdance
uv sync                                   # project environment in .venv, with the dev tools
uv run pytest                             # ~240 tests, about a minute and a half (Spark tests need Java)
```

`uv sync` installs into `.venv` in the repository; to use an environment elsewhere, activate it and pass `--active` (`uv sync --active`, `uv add --active <package>`).

**End-to-end check.** [`scripts/make_synthetic_city.py`](https://github.com/sdgresearch/verdance/blob/master/scripts/make_synthetic_city.py) writes a small synthetic city (48 buildings, trees, parks, roads, a CHM and two census levels) and a config for it, so every module can run in a few minutes without downloads:

```bash
python scripts/make_synthetic_city.py /tmp/verdance_synth
verdance run -c /tmp/verdance_synth/config.yaml -p T3 --buffer 50   # likewise T30, T300, Tree_count, Visibility, ...
verdance run -c /tmp/verdance_synth/config.yaml -p Merge --t3_buffers 50
```

The other scripts in `scripts/` prepare inputs for particular cities and evaluate tree segmentation and building heights against reference data.

## Releasing

Releases are published to PyPI by GitHub Actions through [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so no API token is stored anywhere. To cut one:

1. Bump `__version__` in `src/verdance/__init__.py` — `[tool.hatch.version]` reads it from
   there, so it is the only place the version is set.
2. Move the `[Unreleased]` section of `CHANGELOG.md` under the new version number.
3. Open a pull request, and once it is merged tag the merge commit and push the tag:

   ```bash
   git tag -a v<version> -m "v<version>" && git push upstream v<version>
   ```

The tag triggers `.github/workflows/release.yml`, which builds the sdist and wheel and
uploads them. To check a build locally first:

```bash
rm -rf dist && uv build                   # dist/verdance-<version>.tar.gz and .whl
uvx twine check --strict dist/*
```


## Licence and data


verdance is released under the [MIT licence](https://github.com/sdgresearch/verdance/blob/master/LICENSE). The data it downloads keeps its own licence — notably GlobalBuildingAtlas heights (`gba`) are CC BY-NC 4.0 and FABDEM terrain is CC BY-NC-SA 4.0, both non-commercial only; the tables above list each source's licence. The bundled map viewer includes [MapLibre GL JS](https://maplibre.org/) (BSD-3-Clause).
