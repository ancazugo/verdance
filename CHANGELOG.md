# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `verdance.run(config, process, ...)` — a programmatic entry point mirroring the
  CLI for notebooks and scripts — plus `verdance.load_config` and
  `verdance.VerdanceConfig` as public exports (`import verdance` stays lightweight).
- `verdance validate -c config.yaml` — a dry-run that checks input files,
  geo-level columns, CRS and Java before a long Spark run starts.
- Per-module run manifests (`_manifest.json`): each run records which geo codes
  it attempted, completed and failed, and `Merge` warns when a module left
  regions unfinished instead of silently consolidating an incomplete table.
- Continuous integration (GitHub Actions, Python 3.12/3.13 with Java 17, ruff),
  a trusted-publishing release workflow, `CITATION.cff`, `CONTRIBUTING.md`,
  a `py.typed` marker, and ruff configuration.

### Changed

- The local Spark master is now `local[*]` by default and overridable via
  `VERDANCE_SPARK_MASTER` (was a fixed `local[10,0]`). Unused PostGIS/JDBC jars
  are no longer downloaded on first run.
- Google Earth Engine downloads retry transient errors with backoff, and
  initialisation fails with a clear "run `earthengine authenticate`" message
  instead of blocking on an interactive flow.

### Performance

Validated against a full England run (23.9M buildings, 308 districts):

- T3's SQL path no longer degenerates into a nested loop. A `LEFT JOIN` on
  `ST_Intersects` cannot use a spatial index, so Sedona compared every
  building–tree pair; it now uses an inner spatial join plus a zero-fill.
  On one district (46k buildings x 68k trees) this cut the join from **1156 s
  to 3.4 s (~340x)** with byte-identical output — same rows, same tree total.
- `load_tables` only reads the road and park datasets for T300, the one module
  that uses them (`load_roads_parks`). For England that skips **898 MB of the
  1,887 MB** it previously read for every module, plus registering two Spark
  views built from 483k park features that nothing queried.
- T300 takes the already-filtered parks from `load_tables` instead of re-reading
  and re-filtering them once per geo code — 308 redundant passes over the parks
  datasets on an England run.
- `binarise_tiles` no longer forces every CHM tile fully resident before merging
  them, roughly halving peak memory; English districts reach 244 overlapping
  1 m tiles (median 18, p90 60) at ~95 MB each.

### Fixed

- Census codes containing quotes (e.g. `L'Hospitalet`) are now escaped in every
  Spark SQL query instead of breaking or distorting it.
- Config loading rejects empty files, unknown keys and geographic (degree-based)
  CRSs with actionable messages.
- A fully-null object column no longer leaks the literal string "None" into Spark;
  `save_temp_file` fails loudly rather than dropping rows when asked to coalesce
  more than one partition.
- Setting up logging no longer removes an embedding application's own loguru sinks.

## [0.3.0] - 2026-11-10

First release on PyPI under the name **verdance** (renamed from `greenpy`); the
import package, console command and PyPI name are all `verdance`.

### Added

- Per-building and per-census-unit evaluation of the 3-30-300 rule — 3 trees
  near every home (`T3`), 30 % neighbourhood canopy cover (`T30`), a public
  green space within 300 m (`T300`) — consolidated by `Merge` into
  analysis-ready tables.
- Distributed geospatial processing on [Apache Sedona](https://sedona.apache.org/)
  / PySpark (Java 11-17).
- Global open-data sources so a city can be analysed without local inputs:
  Overture Maps and OpenStreetMap buildings, parks and roads, and the Meta/WRI
  canopy height model from AWS.
- Tree-crown segmentation from a canopy height model (`Trees`), tree counts
  (`Tree_count`) and per-building canopy (`T30_buildings`).
- Building heights from an ordered chain of sources (footprint attributes,
  GlobalBuildingAtlas, UT-GLOBUS, Open Buildings 2.5D Temporal, GHS-BUILT-H,
  local files) via the `Heights` module.
- Optional `Visibility` module (raster and vector engines) for trees in line of
  sight from a building's windows, and an optional `Spectral` module for
  vegetation indices via Google Earth Engine.
- Aggregation to discrete global grids (H3, S2, geohash, A5, rHEALPix) as an
  alternative to census units.
- An interactive map server (`verdance viz`) for exploring the results.
- A Docker image bundling Python 3.12, OpenJDK 17, the Sedona jars and DuckDB's
  spatial extension.

[Unreleased]: https://github.com/sdgresearch/verdance/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/sdgresearch/verdance/releases/tag/v0.3.0
