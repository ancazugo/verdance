# Quick start

A study area is described by one YAML file. The smallest useful config needs only census
boundaries of your own — one polygon per unit, with a column for each level of the
hierarchy — and takes everything else from global open data:

```yaml
# mycity.yaml
study_area_name: MyCity
crs: EPSG:32630                   # a projected CRS in metres covering the city (e.g. its UTM zone)

data:
  census_boundaries: /path/to/wards.gpkg   # one polygon per unit, e.g. columns district_code, ward_code
  buildings: overture             # Overture Maps footprints
  parks_sites: overture           # Overture parks and recreation grounds
  parks_access: osm               # OSM entrances, else where park boundaries meet roads
  roads: osm                      # OSM walking network
  meta_chm: v1                    # Meta/WRI 1 m canopy height from AWS: the "30"
  trees_dir: /path/to/output/trees   # filled by `-p Trees` below: the "3"

tree_segmentation:
  source: meta                    # segment the trees from the same canopy height model
  preset: meta

park_min_area_ha: 0.5             # ignore green spaces under 0.5 ha (WHO guidance)
terrain:
  source: null                    # flat ground for Visibility (the fabdem default needs GEE)

columns:
  geo_levels: [district_code, ward_code]   # coarsest → finest

output:
  base_dir: /path/to/output
```

Check it before committing to a long run:

```bash
verdance validate -c mycity.yaml
```

Then run the modules one at a time, `Merge` last, and open the map:

```bash
verdance run -c mycity.yaml -p Trees                  # segment tree crowns from the canopy height model
verdance run -c mycity.yaml -p T3 --buffer 50         # trees within 50 m of each building
verdance run -c mycity.yaml -p T30                    # canopy cover per ward
verdance run -c mycity.yaml -p T300                   # distance to the nearest park
verdance run -c mycity.yaml -p Tree_count
verdance run -c mycity.yaml -p Visibility --buffer 50 # optional: trees in view from the windows
verdance run -c mycity.yaml -p Merge --t3_buffers 50  # the rule per building and per unit
verdance viz -c mycity.yaml                           # interactive map at http://localhost:8765
```

The first run fetches the buildings, parks and roads once and caches them as parquet
under `<output.base_dir>/database/`. The results are
`database/T3_30_300_buildings.parquet` (one row per building, with `meets_3`,
`meets_30`, `meets_300` and `meets_3_30_300`) and
`database/T3_30_300_spectral.parquet` (one row per unit, with the share of buildings
meeting each criterion).

[`examples/generic.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/generic.yaml)
documents every config key; download it with

```bash
curl -O https://raw.githubusercontent.com/sdgresearch/verdance/master/examples/generic.yaml
```

## Where files go

verdance writes nothing to the directory you run it from. Everything goes to the places
below; on a shared machine or a small home directory, point the caches at a large disk.

| What | Default location | Change it with |
|---|---|---|
| Results, parquet cache of the inputs, `viz.duckdb` | `<output.base_dir>/` and `<output.base_dir>/database/` | `output.base_dir` in the config |
| Logs (one file per module, plus `viz.log`) | `<output.base_dir>/logs/` | — |
| Downloads shared between runs: canopy-height tiles, Earth Engine rasters (heights, terrain, canopy), OpenStreetMap responses | `<output.base_dir>/database/chm_cache/` | `data.chm_cache_dir` in the config, else the `VERDANCE_CACHE_DIR` environment variable |
| Sedona/Spark jars (~110 MB, downloaded once) | `~/.ivy2` | `VERDANCE_IVY_DIR` |
| DuckDB spatial extension for `verdance viz` (downloaded once) | `~/.duckdb/extensions` | `VERDANCE_DUCKDB_EXTENSIONS` |
| Temporary files: Spark shuffle and spill files, JVM temp files, Spark's warehouse directory | the system temp directory | `TMPDIR` (`SPARK_LOCAL_DIRS` overrides it for Spark's shuffle files) |
| Earth Engine credentials | `~/.config/earthengine/` | `earthengine authenticate` |

The environment variables themselves are listed under
[installation](installation.md#environment-variables).

!!! warning "Rebuild the cache after changing inputs"

    The parquet cache under `database/` is built once from the inputs. **Delete
    `<output.base_dir>/database/` after changing input files or column mappings** so it
    is rebuilt.
