# API reference

verdance is usable as a library as well as a command line tool. Three names are
importable directly from the top-level package:

```python
import verdance

cfg = verdance.load_config("mycity.yaml")
verdance.run(cfg, "T3", buffer=50)      # writes T3 CSVs, returns {geo_code: DataFrame | None}
merged = verdance.run(cfg, "Merge")     # consolidates and returns the merged unit table
```

They are imported lazily, so `import verdance` — to read `verdance.__version__`, say —
does not pull in PySpark and the rest of the stack.

`VerdanceConfig` is documented alongside the YAML keys it mirrors, in the
[config reference](../configuration.md#reference).

The per-geo-code analysis modules (T3, T30, T30_buildings, T300, Tree_count) and Merge
are covered by `run()`. Trees, Heights, Spectral and the raster Visibility engine have
bespoke setup and remain CLI-only for now.

## Public API

::: verdance.api.run
    options:
      heading: verdance.run
      heading_level: 3
      show_root_heading: true

::: verdance.config.loader.load_config
    options:
      heading: verdance.load_config
      heading_level: 3
      show_root_heading: true

## The rest of the package

The pages below document the internals, for extending verdance or calling a single
stage directly.

- [Analysis modules](analysis.md) — the T3, T30, T300 and Tree_count processes, and Merge
- [Pipeline](pipeline.md) — input loading, output layout and the DGGS backends
- [Data sources](data-sources.md) — OSM, Overture, Open Buildings, building heights, terrain
- [Optional modules](optional.md) — canopy sources, spectral indices, tree segmentation, visibility
- [Utilities](utils.md) — Spark/Sedona setup, caching, run manifests and the map viewer
