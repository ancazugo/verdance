# Visualising results

`verdance viz` opens an interactive map of whatever has been computed so far:

```bash
verdance viz -c config.yaml            # opens http://localhost:8765
```

All controls sit in a sidebar on the left, split into **Map** (basemap, parks, trees, boundary lines), **Buildings** (one value per footprint) and **Areas** (one value per census unit or grid cell); a card in the top-right corner summarises the whole study area — buildings, trees, parks counted, canopy cover of the whole study area (total canopy ÷ total measured area, from T30), medians of the rule's inputs and the share of buildings meeting 3, 30, 300 and all three. When Merge kept both "3" metrics, the card shows the rule with 3 = trees nearby and with 3 = trees in view, the one `--rule_t3_metric` chose first.

- **Buildings** are coloured by any per-building metric (T3 tree counts, park distances, T30_buildings canopy, Visibility's trees in view — from any floor, from the ground floor, and the share of nearby trees in view — building heights and, after Merge, the `meets_*` rule flags, including the rule under each "3" metric). Each coloured layer has its own palette (ColorBrewer, viridis, magma, cividis; reversible) and classes: quantile, equal interval, natural breaks (Jenks), logarithmic, continuous rank-stretched colour (every part of a skewed distribution gets contrast) or **rule threshold**, with 3–9 classes. The rule threshold uses diverging colours centred on the 3-30-300 threshold (3 trees, 30 %, 300 m). A rule flag is drawn as a **gradient of the value it tests** — trees within the rule buffer, the canopy the rule used, the park distance, or for the combined rule the number of criteria met (0–3, counting the "3" of that rule) — with its pass/fail counts in the legend; switch to plain pass/fail there.
- **Areas** (every census level, plus any DGGS grid already built, e.g. "H3 res 9") can be filled with a unit metric — Merge's table at its level, T30/Tree_count/Spectral at the sub-geo level, and averages of the building metrics at every level — or outlined. **Boundaries** toggles outlines of any number of levels at once, e.g. ward borders over an H3 fill. Set `columns.geo_level_labels` / `geo_level_names` to show levels and units by name.
- **Parks** shows the green spaces T300 counts (solid; at least `park_min_area_ha`) and the smaller ignored ones (dashed); click one for its name and area.
- **Trees** from `data.trees_dir` are drawn to scale (crown radius from the area column or polygon area) or as dots when only points are available. Green is reserved for trees and purple for parks; the default metric ramps are blues, red–blue and orange–brown.
- Drag across the legend histogram to show only a value range; click a feature for all of its values.
- Basemaps (no API keys): none, OpenFreeMap Positron or Liberty, OpenStreetMap, Esri World Imagery (sub-metre in most cities; Esri attribution, and Esri's terms expect an ArcGIS account beyond light non-commercial use), or Sentinel-2 imagery (EOX, 10 m, non-commercial).

Merge is optional: module CSVs are read directly when its parquets are missing. The first start builds `database/viz.duckdb` (geometry reprojected and indexed, statistics precomputed), and later starts reuse it until an output changes; `--rebuild` forces a rebuild and `--no-trees` skips the tree layer. Buildings and trees appear from zoom 14 (a view about 3.5 km across), which keeps whole-city datasets responsive; zoomed further out, show units instead.

The server listens on `127.0.0.1` only. On a remote machine, forward the port (`ssh -L 8765:localhost:8765 host`) and pass `--no-browser`. DuckDB downloads its spatial extension on first use; set `VERDANCE_DUCKDB_EXTENSIONS=/some/dir` if your home directory is full or read-only.

## Output layout

```
<output.base_dir>/
├── T3/            T3_<code>_<buffer>m.csv
├── T30/           T30_<code>.csv
├── T30_buildings/ T30_buildings_<code>_<buffer>m.csv
├── T300/          T300_<code>.csv
├── Tree_count/    Tree_count_<code>.csv
├── Visibility/    Visibility_<code>_<buffer>m.csv (Visibility_vector/ with --vis_engine vector)
├── Spectral/      Spectral_<code>.csv
├── logs/          <module>_processing.log, viz.log
├── T30_h3_9/, Tree_count_h3_9/   same, per grid cell (runs with --dggs h3 --dggs_resolution 9)
└── database/      parquet cache + consolidated outputs
    ├── chm_cache/                   ← download cache (unless data.chm_cache_dir or VERDANCE_CACHE_DIR is set)
    ├── building_heights_<key>.parquet ← one height per building (Heights; per-source caches in heights/)
    ├── context_buildings.parquet    ← footprints in the context_buffer ring (remote building sources)
    ├── T3_30_300_buildings.parquet  ← per-building 3-30-300 evaluation
    ├── T3_30_300_spectral.parquet   ← final merged table
    ├── h3_boundaries_res9.parquet   ← grid cells (+ T3_30_300_*_h3_9.parquet from a grid Merge)
    └── viz.duckdb                   ← map store built by `verdance viz`
```
