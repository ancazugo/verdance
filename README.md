# verdance

Measure the **3-30-300 rule** of urban greening for any city, powered by [Apache Sedona](https://sedona.apache.org/).

The 3-30-300 rule ([Konijnendijk, 2023](https://doi.org/10.1007/s11676-022-01523-z)) states that every home should:

1. **See at least 3 trees** — measured here as the number of trees within a buffer of each building (**T3**), or the number visible from its windows (**Visibility**),
2. **Sit in a neighbourhood with at least 30 % canopy cover** (**T30**),
3. **Be within 300 m of a public green space** (**T300**).

verdance computes each metric per building and per census unit from standard geospatial inputs — or from global open data (Overture Maps, OpenStreetMap, the Meta/WRI canopy height model) where local data is missing — evaluates the rule for every building, merges everything into one analysis-ready table, and serves an interactive map of the results.

**Contents:** [Installation](#installation) · [Quick start](#quick-start) · [Where files go](#where-files-go-caches-temporary-files-and-logs) · [Docker](#docker) · [Modules](#modules) · [Input data](#input-data) · [Configuration](#configuration) · [Usage](#usage) · [Merge and the rule](#merge-and-the-3-30-300-rule) · [Visualising results](#visualising-results) · [Output layout](#output-layout) · [Troubleshooting](#troubleshooting) · [Development](#development)

## Installation

verdance needs **Python 3.12 or 3.13** and **Java 11–17** (Spark 3.5 runs on Java 17 at most; newer Java versions fail).

```bash
pip install verdance          # or: uv pip install verdance / uv tool install verdance / pipx install verdance
verdance --version
```

**Java.** Install a JDK 17 and make sure `java -version` reports it, or point `JAVA_HOME` at it:

```bash
sudo apt install openjdk-17-jre-headless          # Debian / Ubuntu
brew install openjdk@17                           # macOS (then follow brew's note to link it)
conda install -c conda-forge openjdk=17           # any OS, inside a conda environment
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # if another Java is the default
```

The first Spark-based run downloads the Sedona jars (~110 MB, once) into Spark's Ivy cache (`~/.ivy2`, or `VERDANCE_IVY_DIR`), so it needs internet access. No Java at hand? Use the [Docker image](#docker), which bundles Java and the jars.

**Google Earth Engine (optional).** Some data sources are read from Earth Engine: the `Spectral` module, `canopy_height_ee_path`, `data.buildings: open_buildings`, the remote building-height sources and terrain for Visibility. They need a Google Cloud project with Earth Engine enabled: authenticate once with `earthengine authenticate` (installed with verdance) and set `gee_project: <your-project>` in the config. Everything else — including the global open-data sources Overture, OpenStreetMap and the Meta canopy height model from AWS — needs no account.

**Settings from a `.env` file.** verdance reads a `.env` file in the working directory (or a parent directory) at startup; variables already set in the environment win. Every setting is optional:

```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # or JDK_HOME, see "Where files go"
VERDANCE_CACHE_DIR=/big/disk/verdance_cache    # shared download cache
GEE_PROJECT_NAME=my-gee-project                # Earth Engine project when the config has no gee_project
```

## Quick start

A study area is described by one YAML file. The smallest useful config needs only census boundaries of your own — one polygon per unit, with a column for each level of the hierarchy — and takes everything else from global open data:

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

The first run fetches the buildings, parks and roads once and caches them as parquet under `<output.base_dir>/database/`. The results are `database/T3_30_300_buildings.parquet` (one row per building, with `meets_3`, `meets_30`, `meets_300` and `meets_3_30_300`) and `database/T3_30_300_spectral.parquet` (one row per unit, with the share of buildings meeting each criterion). [`examples/generic.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/generic.yaml) documents every config key; download it with

```bash
curl -O https://raw.githubusercontent.com/sdgresearch/verdance/master/examples/generic.yaml
```

## Where files go: caches, temporary files and logs

verdance writes nothing to the directory you run it from. Everything goes to the places below; on a shared machine or a small home directory, point the caches at a large disk.

| What | Default location | Change it with |
|---|---|---|
| Results, parquet cache of the inputs, `viz.duckdb` | `<output.base_dir>/` and `<output.base_dir>/database/` | `output.base_dir` in the config |
| Logs (one file per module, plus `viz.log`) | `<output.base_dir>/logs/` | — |
| Downloads shared between runs: canopy-height tiles, Earth Engine rasters (heights, terrain, canopy), OpenStreetMap responses | `<output.base_dir>/database/chm_cache/` | `data.chm_cache_dir` in the config, else the `VERDANCE_CACHE_DIR` environment variable |
| Sedona/Spark jars (~110 MB, downloaded once) | `~/.ivy2` | `VERDANCE_IVY_DIR` |
| DuckDB spatial extension for `verdance viz` (downloaded once) | `~/.duckdb/extensions` | `VERDANCE_DUCKDB_EXTENSIONS` |
| Temporary files: Spark shuffle and spill files, JVM temp files, Spark's warehouse directory | the system temp directory | `TMPDIR` (`SPARK_LOCAL_DIRS` overrides it for Spark's shuffle files) |
| Earth Engine credentials | `~/.config/earthengine/` | `earthengine authenticate` |

Other environment variables:

| Variable | Meaning |
|---|---|
| `JAVA_HOME` | The Java 11–17 installation Spark runs on. `JDK_HOME` takes precedence: an absolute path, or the name of a JDK directory under `~/.jdk/` (the layout of the [install-jdk](https://pypi.org/project/install-jdk/) package) |
| `SPARK_DRIVER_MEMORY` | Spark's heap (e.g. `16g`). Spark runs locally, so this is the memory for all its work. Default: three quarters of the machine's RAM, at most `64g` |
| `GEE_PROJECT_NAME` | Earth Engine project used when the config has no `gee_project` |

The parquet cache under `database/` is built once from the inputs. **Delete `<output.base_dir>/database/` after changing input files or column mappings** so it is rebuilt.

## Docker

The image bundles Python 3.12, OpenJDK 17, the Sedona jars and DuckDB's spatial extension, so it runs without Java installed and without network access for them. Build it from a clone of the repository:

```bash
git clone https://github.com/sdgresearch/verdance.git && cd verdance
docker build -t verdance .
docker run --rm verdance --version
```

Mount a project directory holding the config, the inputs and the output folder, and use **container paths** in the config (e.g. `census_boundaries: /work/data/wards.gpkg`, `base_dir: /work/output`). The image's entrypoint is `verdance`, so pass only its arguments:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  verdance run -c /work/mycity.yaml -p T3 --buffer 50
```

`--user "$(id -u):$(id -g)"` makes the output files yours on a standard Docker install. With **rootless Docker** use `--user 0:0` instead: there the container's root is you, while any other user maps to a host ID you can't write as. Docker Desktop needs neither. To keep downloads between containers, add a cache mount: `-v "$HOME/verdance_cache":/cache -e VERDANCE_CACHE_DIR=/cache`.

- **Memory.** The image defaults to `SPARK_DRIVER_MEMORY=4g`; raise it on a bigger host with `-e SPARK_DRIVER_MEMORY=32g`.
- **Earth Engine.** Authenticate once on the host (`earthengine authenticate`), then mount the credentials: `-v "$HOME/.config/earthengine":/home/verdance/.config/earthengine:ro`, and set `gee_project` in the config.
- **The map.** Publish the port and listen on all interfaces inside the container: `docker run --rm -p 8765:8765 -v "$PWD":/work verdance viz -c /work/mycity.yaml --host 0.0.0.0 --no-browser`, then open http://localhost:8765.
- **docker compose.** [`docker-compose.yml`](https://github.com/sdgresearch/verdance/blob/master/docker-compose.yml) mounts `./data` at `/data`, `./config` at `/config` and `./output` at `/output` (set `output.base_dir: /output`), and keeps a download cache in `./cache`: `docker compose run --rm verdance run -c /config/mycity.yaml -p T3 --buffer 50`.

## Modules

| Process | What it computes | Output (one CSV per geo code) |
|---|---|---|
| `Trees` | Segments individual tree crowns from a canopy height model (local CHM tiles or the global Meta/WRI 1 m CHM) into `data.trees_dir`, for T3/Tree_count/Visibility | `trees_<geo_code>.parquet`: `treeID`, `height`, `area`, `top_x`, `top_y`, crown geometry |
| `T3` | Trees (height and area strictly above `--tree_height`/`--tree_area`) whose centroid lies within `--buffer` metres of each building | `building_id`, `tree_count_<buffer>m`, sub-geo code |
| `T30` | Canopy cover % per sub-geo unit, from CHM raster tiles, the Meta canopy height model on AWS, a GEE canopy-height asset, or tree polygons | sub-geo code, `canopy_cover`, `total_pixels` |
| `T30_buildings` | Canopy cover % within `--buffer` metres of each building (distributed Sedona `RS_ZonalStats` for raster sources), same canopy sources as T30 | `building_id`, `tree_pixels`, `total_pixels`, `canopy_cover` |
| `T300` | Road-network and Euclidean distance from each building to the nearest park | `building_id`, distances, closest park ids, sub-geo code |
| `Tree_count` | Total tree count per sub-geo unit, each tree counted once in the unit containing its centroid (no size filter, unlike T3) | sub-geo code, `tree_count` |
| `Heights` | A height for every building footprint from an ordered chain of sources (footprint attributes, GlobalBuildingAtlas, UT-GLOBUS, Open Buildings 2.5D Temporal, GHS-BUILT-H, local files) | `database/building_heights_<key>.parquet`: `building_height`, `height_source`, `height_quality` |
| `Visibility` *(optional)* | Trees within `--buffer` metres that can be seen from some window of each building, with buildings and trees blocking the view | `building_id`, `visible_trees`, `visible_trees_ground`, `candidate_trees`, `n_floors`, `building_height`, `height_source`, sub-geo code |
| `Spectral` *(optional)* | Spectral indices (NDVI, NDWI, …) per sub-geo unit via Google Earth Engine: a per-pixel temporal composite over the date range (`--composite max`, the default, or `median`), then the spatial median over each unit | sub-geo code, one column per index |
| `Merge` | Evaluates the 3-30-300 rule per building and consolidates all module outputs into `database/T3_30_300_spectral.parquet` | one row per geo unit (see *Merge* below) |

## Input data

All inputs are vector files readable by GeoPandas (GeoPackage, Shapefile, GeoJSON, (Geo)Parquet…):

- **Census boundaries** (required, always a file) — one polygon per unit of the *finest* geography, with a column for every level of the hierarchy (e.g. district and tract codes). They define the study area, including where remote layers are fetched
- **Buildings** — footprint polygons with a unique id column (`columns.building_id`). Instead of a file, `data.buildings` also accepts `osm` (OpenStreetMap; `height` and `building:levels` tags are kept where mapped), `overture` (Overture Maps, global; `height` and `num_floors` are kept but sparse outside major cities), or `open_buildings` (Google Open Buildings v3 via GEE, needs `gee_project`; no heights, and covers Africa, South/Southeast Asia and Latin America & the Caribbean only — **not** Europe or North America). Visibility also needs building heights, which the `Heights` process attaches from global datasets when the footprints have none (see *Building heights* below)
- **Trees** — canopy polygons with height and area attributes (a single file or a directory of tiles), or segment them from a CHM with the `Trees` process (see *Tree segmentation* below)
- **Canopy for T30** — one of: a directory of CHM raster tiles (`.tif`, `chm_tiles_dir`); the Meta/WRI global canopy height model from AWS (`meta_chm: v1` or `v2`, no account needed); a GEE canopy-height asset (`canopy_height_ee_path`, needs `gee_project`); or the tree polygons above. See *Canopy cover source* below
- **Parks** — green-space polygons, plus access points (can be the same file), or `osm` / `overture` (parks) and `osm` (access points). Set `park_min_area_ha` (top-level config key) to ignore small green spaces — the WHO guideline behind the 300 rule uses ≥ 0.5–1 ha. Access points are only filtered along with their parks when `columns.park_access_ref_col` links them
- **Roads** — edges (and optionally nodes; nodes are derived from edge endpoints if absent), or `osm`. File-based networks must be **noded** (split at every intersection — nodes are derived from segment endpoints only) and reduced to their **largest connected component**, or buildings snapping to isolated fragments get null network distances. `columns.road_edge_length` should hold edge lengths in metres; if the column is missing, lengths are computed from the geometry in the config CRS (with a warning)

On the first run, verdance converts everything to a parquet cache in `<output.base_dir>/database/`, renaming your columns to canonical names. Delete that folder to rebuild the cache after changing input data or column mappings.

## Configuration

Each study area is described by a YAML config — see [`examples/generic.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/generic.yaml) for a fully commented template of every key. More examples in [`examples/`](https://github.com/sdgresearch/verdance/tree/master/examples): [`osm.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/osm.yaml) (every layer from OpenStreetMap), [`open_buildings.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/open_buildings.yaml) (Google Open Buildings), [`nairobi.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/nairobi.yaml) (a whole city on global open data: Overture buildings and parks, OSM roads, Meta canopy height, global building heights) and UK setups with local data (`westminster.yaml`, `anglesey.yaml`, `england.yaml`). Their paths point to the author's machines: replace them with yours. The key sections:

```yaml
study_area_name: MyCity
crs: EPSG:32632          # projected CRS in metres

data:                    # paths to the inputs above
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

## Usage

Run one module at a time; `Merge` last. `verdance run --help` lists every option.

```bash
verdance run -c config.yaml -p Trees      # optional: segment trees from a CHM into trees_dir
verdance run -c config.yaml -p T3 --buffer 100
verdance run -c config.yaml -p T30
verdance run -c config.yaml -p T30_buildings --buffer 100
verdance run -c config.yaml -p T300
verdance run -c config.yaml -p Tree_count
verdance run -c config.yaml -p Heights         # building heights (Visibility builds them if missing)
verdance run -c config.yaml -p Visibility --buffer 50   # optional: trees in view
verdance run -c config.yaml -p Spectral        # optional, needs GEE
verdance run -c config.yaml -p Merge
verdance viz -c config.yaml                    # interactive map, see "Visualising results"
```

Useful options:

- `--geo_level` / `--sub_geo_level` — which levels of `columns.geo_levels` to iterate over / aggregate to (defaults: coarsest / finest); Merge's `--geo_level` defaults to the second-finest level instead
- `--dggs h3|s2|geohash|a5|rhealpix --dggs_resolution N` — aggregate to grid cells instead of the finest census level (also settable as `dggs`/`dggs_resolution` in the config). Grid runs sit beside census-unit runs: T30, Tree_count and Merge write grid-suffixed outputs (`T30_h3_9/`, `database/T3_30_300_spectral_h3_9.parquet`), and the per-building modules (T3, T300, …) need not be re-run — Merge aggregates them through the grid's buildings overlay. With a grid, the rule's "30" uses each building's cell canopy. To add H3 res 9 to an existing run: `-p T30`, `-p Tree_count` and `-p Merge`, each with `--dggs h3 --dggs_resolution 9`
- `--geo_code CODE` — process a single geography instead of all
- `--parallel --n_workers 4` — process geo codes concurrently (per-geo Spark views are isolated, so results match sequential runs)
- `--no-overwrite` — skip geo codes whose output CSV already exists (resume an interrupted run)
- `--query_method sql|rdd` — Sedona join strategy for T3 (default `sql`). `sql` uses an indexed spatial join and returns a row for *every* building, with `tree_count` 0 where no tree is in range; `rdd` omits those buildings (Merge zero-fills them, so merged totals match, but its per-geo CSVs are incomplete on their own). On the London region (2.83M buildings × 2.58M trees) `sql` took 47 s against 74 s for `rdd`
- `--tree_area` / `--tree_height` — a tree counts in T3 and Visibility only if its canopy area (m²) and height (m) are *strictly greater* than these (defaults 10 and 3)
- `--vis_engine raster|vector` — Visibility engine (default `visibility.engine`, i.e. `raster`; see *Tree visibility* below)
- `--low_threshold` / `--high_threshold` — canopy-height band in metres for T30/T30_buildings binarisation (default 3–60)
- `--gee_scale` — download resolution in metres for the T30/T30_buildings GEE canopy source (default `1.0`; raise to e.g. `10` for faster, lighter downloads over large regions — canopy is still thresholded at native resolution and each coarse pixel stores its canopy fraction, so cover stays unbiased)
- `--composite max|median` — Spectral temporal composite (default `max`)
- `--rule_t3_buffer`, `--rule_t3_metric`, `--rule_t30_buffer`, `--rule_distance` — how Merge evaluates the rule per building (see *Merge* below)

### Canopy cover source (T30, T30_buildings)

T30 and T30_buildings pick their canopy source by what's configured, in priority order:

1. **CHM raster tiles** (`chm_tiles_dir`) — local `.tif` tiles, binarised to a canopy/no-canopy mask between `--low_threshold` and `--high_threshold` metres.
2. **Meta/WRI canopy height from AWS** (`meta_chm: v1` or `v2`) — the tiles covering the area are downloaded once from Meta's public bucket into the CHM cache (`data.chm_cache_dir`, else `$VERDANCE_CACHE_DIR`), cropped, binarised at native ~1 m resolution and reprojected to the config CRS; masks are cached under `<base_dir>/database/meta_canopy/`, named by geo code, release and height band.

   ```yaml
   data:
     meta_chm: v2
   ```

   - `v1` — the original release (Tolan et al. 2024; `forests/v1/alsgedi_global_v6_float`, zoom-9 tiles of ~150–400 MB). The same data as the GEE asset below: over a 600 m Cambridge square, v1 from AWS gives 7.63 % cover and v1 through GEE 7.62 %. Like v2, v1 tiles declare **no nodata** — but v1 ships no imagery footprints, so there is nothing to mask with: unimaged pixels read 0 and count as mapped-but-treeless, which deflates cover wherever imagery is missing inside a unit (open water, gaps). Prefer `v2` where that matters.
   - `v2` — `forests/v2/global/dinov3_global_chm_v2_ml3` (zoom-10 tiles of ~20–250 MB, heights in whole metres). The same Cambridge square gives 12.78 %, so v1 and v2 results are not interchangeable. v2 tiles declare no nodata, so unimaged pixels (e.g. open sea) read 0 like bare ground; verdance masks pixels outside each tile's imagery footprints (`metadata/<quadkey>.geojson`) as nodata on download and keeps the footprints beside the tile. Footprints can include near-shore sea, which then still counts as no canopy — mostly relevant for T30_buildings buffers on the coast, since census units are usually clipped to the coastline. Imagery dates differ by area (e.g. 2011–2018 in one Norfolk tile); each run logs the range for the area it reads.

   Both releases are tiled in EPSG:3857 at 1.1943 units/pixel, so the *ground* sampling is `1.1943 × cos(latitude)` m — about 0.74 m at Cambridge's 52°N but 1.19 m near the equator. Cover itself stays unbiased (tiles are binarised at native resolution, then reprojected to the config's metric CRS, so the counted pixels are equal-area), but the same config resolves narrow crowns better at higher latitudes — worth keeping in mind when comparing cities at very different latitudes.

   `meta_chm` also selects the release wherever the `meta` CHM source is read (`tree_segmentation.source: meta`, raster Visibility); unset, those use v1.
3. **GEE canopy-height asset** (`canopy_height_ee_path`) — binarised *server-side* in Google Earth Engine and downloaded with [xee](https://github.com/google/Xee); no local canopy data required. Needs `gee_project` in the config. Example asset (global 1 m Meta/WRI canopy height):

   ```yaml
   data:
     canopy_height_ee_path: projects/sat-io/open-datasets/facebook/meta-canopy-height
   gee_project: my-gee-project
   ```

   Downloaded rasters are cached under `<base_dir>/database/gee_canopy/`, named by geo code, height band and scale. At the native 1 m scale large regions can be slow — use `--gee_scale 10` to trade detail for speed: the mask is binarised at the native 1 m and averaged to canopy fraction per 10 m pixel server-side, so cover estimates stay consistent with 1 m runs.
4. **Tree polygons** (`trees_dir`) — canopy cover as the area of the union of crowns clipped to each unit / unit area (a crown straddling two units counts only its own part in each; overlapping crowns are not double-counted); used when no raster or GEE source is set. Point trees fall back to their `tree_area` attribute.

Where T30 reports canopy per sub-geo unit, `T30_buildings` reports it per building, within `--buffer` metres of each footprint (`--buffer 0` for the footprint alone). Raster sources run distributed through Sedona (`RS_TileExplode` + `RS_ZonalStats`), so large CHM tile sets scale across Spark workers; the vector source uses an `ST_Intersection` area ratio. CHM nodata pixels are excluded from `total_pixels` in both modules. Where CHM tiles overlap (e.g. several survey years), `data.chm_overlap` decides which heights are used — `latest` (default; the last path in sorted order, i.e. the latest year for `<dir>/<year>/` layouts) or `max` (per-pixel maximum) — in T30, T30_buildings and Trees alike; T30_buildings first composites overlapping tiles into non-overlapping chunks under the CHM cache, since it sums pixel counts per tile. One difference to keep in mind: T30_buildings counts every pixel *touching* a buffer while T30 counts pixels whose *centre* falls in the unit. CHM tiles are searched recursively under `chm_tiles_dir`, matching `data.chm_pattern` (default `*.tif`); Defra VOM hillshades (`VOM_HS_*`, stored beside every height tile) are always skipped. In `Merge`, per-building canopy is averaged up to the geo level as `building_canopy_cover_<buffer>m` (included automatically when T30_buildings output exists).

### Tree segmentation (Trees)

`Trees` derives the crowns T3 counts from a canopy height model, so the "3" can be measured anywhere a CHM exists:

```bash
verdance run -c config.yaml -p Trees --parallel --n_workers 32   # writes data.trees_dir/trees_<geo_code>.parquet
verdance run -c config.yaml -p T3 --buffer 50
```

The CHM is smoothed, treetops are found with a height-dependent circular local-maximum window, and crowns are grown from them with Dalponte & Coomes (2016) region growing — a numpy/scipy port of the lidR pipeline used for the Defra VOM trees (`preset: legacy_vom` reproduces it: ~99.7 % of crowns match lidR one-to-one, at ~6× lidR's speed on one core). Large areas are processed in blocks with a halo, in parallel; a tree belongs to the block and geo code containing its treetop, so blocks and neighbouring geo codes never duplicate or cut trees.

Sources (`tree_segmentation.source`): `chm_tiles` mosaics the tiles under `data.chm_tiles_dir` — where tiles overlap, e.g. several survey years, `data.chm_overlap: latest` keeps the last path in sorted order (the latest year for `<dir>/<year>/` layouts) and `max` takes the per-pixel maximum across them, so a tree seen in any survey counts (in London, Defra's December 2020 VOM shows canopy at 36–49 % of surveyed street trees vs 49–77 % in 2018; `max` raised the share of inventory trees visible in the CHM from 52 % to 77 %); `meta` downloads the [Meta/WRI global canopy height](https://registry.opendata.aws/dataforgood-fb-forests/) tiles covering the area from AWS (release set by `data.meta_chm`, default v1: ~240 MB per zoom-9 tile; v2: ~20–250 MB per zoom-10 tile; cached) and segments them on their native grid, with lengths converted to ground metres.

Presets (`tree_segmentation.preset`, individual values overridable under `params`) were tuned with `scripts/tune_tree_segmentation.py`, scoring only trees T3 would count (crown > 10 m², height > 3 m) against the London borough tree inventory (recall on surveyed trees visible in the CHM; precision inside surveyed crowns, since council inventories omit private trees) and NeonTreeEvaluation (full precision/recall), with London boroughs split into tuning and held-out sets. Held-out results:

| Preset | CHM | London F1 | London recall | NEON precision / recall |
|---|---|---|---|---|
| `legacy_vom` | Defra VOM (`chm_overlap: max`) | 0.48 | 0.32 | 0.84 / 0.19 |
| `vom` | Defra VOM (`chm_overlap: max`) | 0.58 | 0.46 | 0.87 / 0.46 |
| `legacy_vom` | Meta | 0.41 | 0.33 | — |
| `meta` | Meta | 0.48 | 0.43 | — |

On an independent check — Cambridge City Council's 2024 inventory (20,779 trees, not used in tuning; `scripts/evaluate_trees_survey.py`) — `vom` raised the share of surveyed trees matched within 3 m from 34 % to 46 % (F1 0.56 → 0.68), while `meta` matched 23 %, little better than `legacy_vom` on Meta: the gain on Meta did not transfer beyond London.

Meta's smoother, whole-metre heights still split about one surveyed crown in two, so expect its T3 counts to run higher than LiDAR's (over Cambridge: 147k vs 120k T3-eligible trees with the tuned presets).

### Building heights (Heights)

Visibility needs a height for every building. `Heights` attaches one from an ordered chain of sources — for each building the first source with a valid height wins (`heights.min_height`–`heights.max_height`, default 2–300 m), and buildings no source covers get `heights.default_height` (6 m), flagged `height_source: default`, so they still block views:

```yaml
heights:
  sources:                      # first valid height wins
    - native                    # the footprints' own height (Overture, OSM, columns.building_height_col),
                                #   else floor count x storey_height (num_floors, or options levels_col)
    - gba                       # GlobalBuildingAtlas polygons
    - {source: utglobus, city: bogota}
    - {source: open_buildings_temporal, year: 2023}
    - ghs_built_h               # coarse global fallback
    - {source: file, path: /data/ndsm.tif, stat: median, name: lidar}
  default_height: 6.0
  storey_height: 3.0            # metres per floor, also Visibility's floor spacing
  min_overlap: 0.3              # vector sources: share of the footprint they must cover
```

| Source | Dataset | Kind | Coverage | Licence |
|---|---|---|---|---|
| `native` | the footprints' own height / floor count | attribute | wherever mapped | that of the footprints |
| `gba` | [GlobalBuildingAtlas](https://github.com/zhu-xlab/GlobalBuildingAtlas) polygons (GEE sat-io, 5° tiles) | vector | global | **CC BY-NC 4.0 — non-commercial only** |
| `utglobus` | [UT-GLOBUS](https://www.nature.com/articles/s41597-024-03719-w) (GEE sat-io, one collection per city; `cambridge` is Cambridge, MA) | vector | ~1,100 cities | CC BY 4.0 |
| `open_buildings_temporal` | [Open Buildings 2.5D Temporal](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1), 2016–2023, fetched at 2 m | raster (~4 m) | Africa, S/SE Asia, Latin America & Caribbean | CC BY 4.0 |
| `ghs_built_h` | [GHS-BUILT-H R2023A](https://developers.google.com/earth-engine/datasets/catalog/JRC_GHSL_P2023A_GHS_BUILT_H), average net height (2018) | raster (100 m) | global | CC BY 4.0 |
| `file` | a local vector with a height column, or a raster file / directory (nDSM, GBA.Height 3 m) | either | — | — |

Vector sources lend each footprint the area-weighted height of the source polygons covering it (so a block the source splits into several buildings still matches), when they cover at least `min_overlap` of it. Raster sources give the median (GHS: mean) of the pixels whose centre lies inside the footprint, or of every touched pixel for footprints smaller than a pixel; GHS cells are sampled on a 10 m grid so the mean approximates an area-weighted mean. Remote sources come through Google Earth Engine (`gee_project`) and are cached under the CHM cache directory (`data.chm_cache_dir`, else `$VERDANCE_CACHE_DIR`): rasters as tiles aligned to a fixed grid, polygons as small lon/lat chunks, so reruns and neighbouring study areas reuse them. Each source's heights are cached per source (`database/heights/`), and the combined table is `database/building_heights_<key>.parquet`, keyed by the chain and the buildings cache — a new chain builds a new table rather than reusing a stale one. The run logs the share of buildings each source supplied.

`scripts/evaluate_heights.py` compares the cached sources against reference heights. Against Verisk heights in Cambridge (45,719 buildings; `--levels_col premise_floor_count`):

| Source | Coverage | MAE (m) | Bias (m) | Spearman |
|---|---|---|---|---|
| `ghs_built_h` | 95 % | 3.3 | −2.9 | 0.29 |
| `gba` | 89 % | 4.1 | −3.9 | 0.38 |
| floor count × 3 m | 99 % | 2.6 | −2.5 | 0.30 |

Both global datasets run 3–4 m below Verisk, whose two-storey median of 8.9 m suggests it measures to the roof ridge, and rank buildings only weakly. Over Bogotá's 2.17 M Overture footprints the chain above took heights from GBA for 81 %, Open Buildings Temporal 10 %, GHS-BUILT-H 4 %, UT-GLOBUS 1 % and Overture 0.1 %, leaving 4 % at the default (16 min, 8 GB peak memory).

### Tree visibility (Visibility, optional)

Where T3 counts trees *near* a building, `Visibility` counts the ones that can be *seen* from it. It looks from the windows: observer points every `visibility.facade_spacing` metres (5) around each footprint, `facade_offset` (0.5 m) outside the wall, at the eye height of every floor (`floor i: i × heights.storey_height + eye_height`, 1.5 m up; at least one floor). Walls shared with a neighbour (terraced houses) have no windows. It looks at each tree's treetop (`top_x`, `top_y` from `Trees`, else a point inside the crown) and `crown_points` (4) points on its crown at `crown_point_height` (2/3) of its height. A tree is visible when some window sees some target point over every obstacle — every building, the observer's own included, at its `Heights` height, and the vegetation — as flat-topped prisms on flat ground (grazing contact blocks). Inside the target tree's own crown only buildings block, so a tree never hides itself, nor do crowns overlapping it. The candidates are the trees T3 counts — centroid within `--buffer` m, above `--tree_area`/`--tree_height` — with the distance measured exactly, whereas T3's polygonal `ST_Buffer` trims up to ~2 % of the radius at the corners, so `candidate_trees` can exceed `tree_count_<b>m` by a tree or two (3 % of Bogotá's buildings at 50 m, 11 % at 100 m). Smaller trees still block views.

Since visibility only improves with height, each building–tree pair reduces to the lowest eye height from which the tree is visible. Per building the output has `visible_trees` (seen from some floor), `visible_trees_ground` (from the ground floor), `candidate_trees` (T3's count), `n_floors`, `building_height` and `height_source`.

Two engines share these definitions:

- **`raster`** (default) — casts the sightlines over a surface model on a `visibility.resolution` grid (1 m): buildings burned at their heights plus the vegetation, which is the canopy height model when one is configured (`data.chm_tiles_dir` or `tree_segmentation.source`; Meta's CHM is cleared on roofs, `mask_chm_buildings`) and the tree crowns at their heights otherwise (`vegetation: auto|chm|crowns`). A numba kernel visits every pixel each sightline crosses, in parallel (`--parallel --n_workers N` sets the threads, default 16); buildings are processed in `tile_size` tiles (2 km). It needs no Spark. Edges are only as sharp as the grid: a sightline that clips a building corner by less than a pixel may be judged differently from exact geometry (set `resolution: 0.5` to tighten).
- **`vector`** (`--vis_engine vector`) — the exact computation in Sedona SQL, intersecting every sightline with every footprint and crown polygon; a reference for small areas, writing `Visibility_vector/` so Merge never mixes engines. On the synthetic city both engines agree on 47 of 48 buildings (the other differs by one ground-floor tree, a sightline grazing a building corner); on three Cambridge output areas (312 buildings) they agree on `meets_3` for 99.7 % of buildings, with the raster engine seeing 2.5 % fewer trees on average, at ~1 s per area against ~50 s.

Building heights come from the `Heights` chain (built on the first Visibility run when missing) and tree heights from `tree_height_col`. Visibility needs crowns in `data.trees_dir`, and by default reads terrain from Earth Engine (below): set `terrain.source: null` for flat ground without GEE.

**Terrain.** The raster engine stands everything on the ground: buildings sit flat at the ground under their representative point plus their height, vegetation on the ground, windows and targets on the ground under them (floors stay relative to it), and the bare ground itself — a hill, a ridge — blocks sightlines. The ground comes from `terrain.source`:

```yaml
terrain:
  source: fabdem      # fabdem (default) | copernicus | nasadem | /path/to/dtm.tif or directory | null (flat)
  resolution: 30      # GEE download resolution (m), resampled bilinearly onto the visibility grid
```

| Source | Dataset | Surface | Licence |
|---|---|---|---|
| `fabdem` (default) | [FABDEM](https://gee-community-catalog.org/projects/fabdem/), Copernicus GLO-30 with buildings and forests removed | bare earth | **CC BY-NC-SA 4.0 — non-commercial** |
| `copernicus` | Copernicus GLO-30 | surface model | Copernicus DEM licence |
| `nasadem` | NASADEM (SRTM) | surface model | public domain |

Use a bare-earth model: surface models already contain rooftops and canopy in cities, so building and tree heights would be counted twice (in central Bogotá Copernicus reads 8 m above FABDEM). DEM tiles are cached under the CHM cache directory. The vector engine always assumes flat ground. In Cambridge (flat) terrain changed the visible-tree count of 1.2 % of buildings and `meets_3` for 12 of 45,682.

**Study-area edges.** `context_buffer` (default 100 m, a top-level key; 0 disables) gathers context in a ring around the study area, so edge buildings are judged like any other:

- *Buildings* — with a remote building source (`osm`, `overture`, `open_buildings`) the ring's footprints are fetched once into `database/context_buildings.parquet`. They get heights from the Heights chain and block views, but belong to no unit, so they are never observers and appear in no output. A building file is used whole, so extend it past the study area to cover the ring.
- *Trees* — a full `-p Trees` run also segments the ring into `trees_context.parquet` (`--geo_code context` does only the ring, e.g. for an existing run), so trees just across the boundary count for edge buildings in T3 and Visibility; Tree_count and T30 still count only trees inside each unit. A tree file is used whole.
- The canopy height model and the DEM are read past the boundary anyway.

First results (raster engine, 16 threads):

| Study area | Buffer | Run time | Candidates | Visible (ground floor) | Meets 3: proximity → visibility |
|---|---|---|---|---|---|
| Cambridge — 45,682 buildings, Verisk heights, VOM crowns | 50 m | 1.5 min | 16.9 | 11.0 (9.9) | 96.9 % → 92.2 % |
| | 100 m | 1.8 min | 62.8 | 21.9 (17.1) | 99.5 % → 97.2 % |
| Cambridge, GBA heights instead | 50 m | 1.6 min | 16.9 | 10.8 (10.3) | 96.9 % → 93.0 % |
| Bogotá — 2.17 M buildings, global heights, Meta CHM | 50 m | 8 min | 4.7 | 1.2 (1.0) | 28.9 % → 10.7 % |
| | 100 m | 9 min | 20.9 | 2.8 (2.1) | 60.7 % → 17.5 % |

These runs used flat ground and no context ring. With FABDEM terrain and the 100 m ring (210 k ring trees, 10.6 k ring buildings), Bogotá took 13 min per buffer; the share meeting the 3 by visibility barely moved (10.7 % → 10.7 % at 50 m, 17.5 % → 17.6 % at 100 m) — most of the city sits on the flat Sabana — but terrain changed the visible-tree count of 27–34 % of buildings on the eastern hillsides (Chapinero, La Candelaria, Santa Fe) against 6–8 % on the plain, and the ring added candidates for 0.3 % (50 m) and 0.9 % (100 m) of buildings. Rerunning T3 with the ring trees raised the count of 6,328 edge buildings at 50 m (the share meeting the 3 by proximity went from 28.9 % to 29.0 %). After Merge, 0.2 % of Bogotá's buildings meet 3-30-300 with 3 = trees nearby and 0.1 % with 3 = trees in view — the 30 is the binding criterion (0.3 % of buildings have 30 % canopy within 100 m) — and per UPZ 21–36 % of the trees within 50 m of a building are in view from it (10–19 % within 100 m). Peak memory was 0.6 GB (Cambridge) and 4.3 GB (Bogotá). Swapping Verisk for GBA heights in Cambridge changed `meets_3` for 1.6 % of buildings. Where vegetation comes from the CHM, every canopy pixel blocks — street trees hide each other — so a smaller share of the candidates is visible than with crown polygons.

### Merge and the 3-30-300 rule

`Merge` accepts `--t3_buffers`, repeated once per buffer (e.g. `--t3_buffers 50 --t3_buffers 100`; default 10, 25, 50, 75 and 100), and combines whichever T3 buffer runs exist; Spectral, T30_buildings and Visibility outputs are included only if present. It aggregates to `--geo_level`, which for Merge defaults to the **second-finest** level of `columns.geo_levels` (the finest with a DGGS), reading sub-geo results at `--sub_geo_level` (default: finest).

Per unit it reports means — `tree_count_<b>m`, `canopy_cover` (area-weighted), `park_distance_manhattan` (road network) and `park_distance_euclidean`, plus `building_canopy_cover_<b>m`, `visible_trees_<b>m` and `visible_trees_ground_<b>m` when available — and `total_trees`. With Visibility it also reports `share_visible_<b>m`: the % of the unit's building–tree pairs within the buffer where the tree is in view (Σ visible ÷ Σ candidates).

Because the rule is a test every home should pass, Merge also evaluates it **per building** and writes `database/T3_30_300_buildings.parquet` with `meets_3`, `meets_30`, `meets_300` and `meets_3_30_300`. The per-unit table gains `pct_meets_3`, `pct_meets_30`, `pct_meets_300` and `pct_meets_3_30_300` (% of buildings passing):

- **3** — at least 3 trees within `--rule_t3_buffer` metres (default `50`): counted by T3 (`--rule_t3_metric proximity`, the default) or visible from some floor (`--rule_t3_metric visibility`, needs Visibility at that buffer). Whenever both outputs exist the table keeps `meets_3_proximity` and `meets_3_visibility` beside `meets_3`, and the combined rule under each, `meets_3_30_300_proximity` and `meets_3_30_300_visibility` (with `pct_` of all four per unit), and the parquet's `verdance_rule` metadata records which metric and columns the rule used
- **30** — canopy cover of the building's sub-geo unit (the neighbourhood reading of the rule) is ≥ 30 %; with `--rule_t30_buffer N`, T30_buildings canopy within N metres of the building instead
- **300** — distance to the nearest park is ≤ 300 m, straight-line by default (`--rule_distance euclidean`, as in the WHO guideline) or `network`

A criterion with missing input is left null and excluded from that percentage; the combined rule is only evaluated where all three are known. T3 and Visibility counts are proxies for "seeing" trees: T3 counts trees near the building, Visibility checks line of sight.

### Per-building outputs

Each building belongs to exactly one census unit — the one containing its representative point — and is output only by that unit's run, including buildings that straddle unit boundaries. Buildings whose representative point lies outside every unit are skipped. T3's default `rdd` query path omits buildings with no tree in the buffer (the `sql` path reports them as 0); Merge fills them with 0. T300 keeps every building: with no reachable park within `osm.fetch_buffer` (default 2 km) its distances are null.

## Visualising results

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

## Troubleshooting

- **`UnsupportedClassVersionError`, or Spark fails to start** — the Java on `PATH` / in `JAVA_HOME` is too old (< 11) or too new (> 17). Point `JAVA_HOME` at a Java 17.
- **`Overpass server busy (HTTP 502)` warnings** — the public OpenStreetMap API is overloaded; verdance retries with growing waits (up to ~15 min). Responses that did arrive are cached, so rerunning later resumes.
- **The JVM runs out of memory (`OutOfMemoryError`, `Java heap space`)** — raise `SPARK_DRIVER_MEMORY`, or process fewer units at once (drop `--parallel`, or a coarser `--geo_level`).
- **Results ignore changed inputs or column mappings** — the parquet cache is reused; delete `<output.base_dir>/database/`.
- **`Missing consolidated outputs for: [...]`** from Merge — run the listed modules first, with the same `--dggs` options (a grid Merge needs T30 and Tree_count at that grid).
- **Home directory full** — move the caches with `VERDANCE_CACHE_DIR`, `VERDANCE_IVY_DIR`, `VERDANCE_DUCKDB_EXTENSIONS` and `TMPDIR` (see [Where files go](#where-files-go-caches-temporary-files-and-logs)).

## Development

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

**Releasing.** Bump `__version__` in `src/verdance/__init__.py`, then build from a clean checkout (the sdist lists its files explicitly, but a clean tree avoids surprises) and check before uploading:

```bash
rm -rf dist && uv build                   # dist/verdance-<version>.tar.gz and .whl
uvx twine check --strict dist/*
uvx twine upload dist/*                   # or: uv publish
```

## Licence and data

verdance is released under the [MIT licence](https://github.com/sdgresearch/verdance/blob/master/LICENSE). The data it downloads keeps its own licence — notably GlobalBuildingAtlas heights (`gba`) are CC BY-NC 4.0 and FABDEM terrain is CC BY-NC-SA 4.0, both non-commercial only; the tables above list each source's licence. The bundled map viewer includes [MapLibre GL JS](https://maplibre.org/) (BSD-3-Clause).
