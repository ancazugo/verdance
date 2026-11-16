# Configuration

Each study area is described by a YAML config. [`examples/generic.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/generic.yaml)
is a fully commented template of every key, and the [reference](#reference) below is
generated from the config schema itself.

More examples live in [`examples/`](https://github.com/sdgresearch/verdance/tree/master/examples):
[`osm.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/osm.yaml) (every
layer from OpenStreetMap), [`open_buildings.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/open_buildings.yaml)
(Google Open Buildings), [`nairobi.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/nairobi.yaml)
(a whole city on global open data: Overture buildings and parks, OSM roads, Meta canopy
height, global building heights) and UK setups with local data (`westminster.yaml`,
`anglesey.yaml`, `england.yaml`). Their paths point to the author's machines: replace them
with yours.

The key sections:

```yaml
study_area_name: MyCity
crs: EPSG:32632          # projected CRS in metres

data:                    # paths to the inputs below
  buildings: /path/to/buildings.gpkg   # or "osm" / "overture" / "open_buildings"
  trees_dir: /path/to/trees/
  chm_tiles_dir: null    # alternative to trees_dir for T30
  ...

columns:                 # your column names → verdance's canonical names
  building_id: building_id
  tree_height_col: height
  tree_area_col: area
  geo_levels:            # geography hierarchy, coarsest → finest
    - district_code
    - tract_code

output:
  base_dir: /path/to/output/
```

!!! tip "Check a config before a long run"

    `verdance validate -c mycity.yaml` is a dry run that checks input files, geo-level
    columns, CRS and Java, so a typo fails in seconds rather than part-way through Spark.

## Input data

All inputs are vector files readable by GeoPandas (GeoPackage, Shapefile, GeoJSON,
(Geo)Parquet…).

- **Census boundaries** (required, always a file) — one polygon per unit of the *finest*
  geography, with a column for every level of the hierarchy (e.g. district and tract
  codes). They define the study area, including where remote layers are fetched.
- **Buildings** — footprint polygons with a unique id column (`columns.building_id`).
  Instead of a file, `data.buildings` also accepts `osm` (OpenStreetMap; `height` and
  `building:levels` tags are kept where mapped), `overture` (Overture Maps, global;
  `height` and `num_floors` are kept but sparse outside major cities), or
  `open_buildings` (Google Open Buildings v3 via GEE, needs `gee_project`; no heights,
  and covers Africa, South/Southeast Asia and Latin America & the Caribbean only —
  **not** Europe or North America). Visibility also needs building heights, which the
  `Heights` process attaches from global datasets when the footprints have none — see
  [Building heights](modules.md#building-heights-heights).
- **Trees** — canopy polygons with height and area attributes (a single file or a
  directory of tiles), or segment them from a CHM with the `Trees` process — see
  [Tree segmentation](modules.md#tree-segmentation-trees).
- **Canopy for T30** — one of: a directory of CHM raster tiles (`.tif`,
  `chm_tiles_dir`); the Meta/WRI global canopy height model from AWS (`meta_chm: v1` or
  `v2`, no account needed); a GEE canopy-height asset (`canopy_height_ee_path`, needs
  `gee_project`); or the tree polygons above. See
  [Canopy cover source](modules.md#canopy-cover-source-t30-t30_buildings).
- **Parks** — green-space polygons, plus access points (can be the same file), or
  `osm` / `overture` (parks) and `osm` (access points). Set `park_min_area_ha` to ignore
  small green spaces — the WHO guideline behind the 300 rule uses ≥ 0.5–1 ha. Access
  points are only filtered along with their parks when `columns.park_access_ref_col`
  links them.
- **Roads** — edges (and optionally nodes; nodes are derived from edge endpoints if
  absent), or `osm`. File-based networks must be **noded** (split at every intersection)
  and reduced to their **largest connected component**, or buildings snapping to
  isolated fragments get null network distances. `columns.road_edge_length` should hold
  edge lengths in metres; if the column is missing, lengths are computed from the
  geometry in the config CRS, with a warning.

On the first run, verdance converts everything to a parquet cache in
`<output.base_dir>/database/`, renaming your columns to canonical names. Delete that
folder to rebuild the cache after changing input data or column mappings.

## Reference

Generated from `verdance.config.schema`. Every key below is a YAML key in the config
file; nested sections map to the dataclasses that follow.

::: verdance.config.schema.VerdanceConfig
    options:
      heading_level: 3

### Sections

::: verdance.config.schema.DataPaths
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.ColumnMapping
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.OutputPaths
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.OSMConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.OvertureConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.OpenBuildingsConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.TreeSegmentationConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.HeightsConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.HeightSourceSpec
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.VisibilityConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.TerrainConfig
    options:
      heading_level: 4
      show_root_heading: true

::: verdance.config.schema.TileSystemConfig
    options:
      heading_level: 4
      show_root_heading: true
