# Modules

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
| `Merge` | Evaluates the 3-30-300 rule per building and consolidates all module outputs into `database/T3_30_300_spectral.parquet` | one row per geo unit (see [Merge](#merge-and-the-3-30-300-rule)) |


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
verdance viz -c config.yaml                    # interactive map, see [Visualising results](visualising.md)
```

Useful options:

- `--geo_level` / `--sub_geo_level` — which levels of `columns.geo_levels` to iterate over / aggregate to (defaults: coarsest / finest); Merge's `--geo_level` defaults to the second-finest level instead
- `--dggs h3|s2|geohash|a5|rhealpix --dggs_resolution N` — aggregate to grid cells instead of the finest census level (also settable as `dggs`/`dggs_resolution` in the config). Grid runs sit beside census-unit runs: T30, Tree_count and Merge write grid-suffixed outputs (`T30_h3_9/`, `database/T3_30_300_spectral_h3_9.parquet`), and the per-building modules (T3, T300, …) need not be re-run — Merge aggregates them through the grid's buildings overlay. With a grid, the rule's "30" uses each building's cell canopy. To add H3 res 9 to an existing run: `-p T30`, `-p Tree_count` and `-p Merge`, each with `--dggs h3 --dggs_resolution 9`
- `--geo_code CODE` — process a single geography instead of all
- `--parallel --n_workers 4` — process geo codes concurrently (per-geo Spark views are isolated, so results match sequential runs)
- `--no-overwrite` — skip geo codes whose output CSV already exists (resume an interrupted run)
- `--query_method sql|rdd` — Sedona join strategy for T3 (default `sql`). `sql` uses an indexed spatial join and returns a row for *every* building, with `tree_count` 0 where no tree is in range; `rdd` omits those buildings (Merge zero-fills them, so merged totals match, but its per-geo CSVs are incomplete on their own). On the London region (2.83M buildings × 2.58M trees) `sql` took 47 s against 74 s for `rdd`
- `--tree_area` / `--tree_height` — a tree counts in T3 and Visibility only if its canopy area (m²) and height (m) are *strictly greater* than these (defaults 10 and 3)
- `--vis_engine raster|vector` — Visibility engine (default `visibility.engine`, i.e. `raster`; see [Tree visibility](#tree-visibility-visibility-optional))
- `--low_threshold` / `--high_threshold` — canopy-height band in metres for T30/T30_buildings binarisation (default 3–60)
- `--gee_scale` — download resolution in metres for the T30/T30_buildings GEE canopy source (default `1.0`; raise to e.g. `10` for faster, lighter downloads over large regions — canopy is still thresholded at native resolution and each coarse pixel stores its canopy fraction, so cover stays unbiased)
- `--composite max|median` — Spectral temporal composite (default `max`)
- `--rule_t3_buffer`, `--rule_t3_metric`, `--rule_t30_buffer`, `--rule_distance` — how Merge evaluates the rule per building (see [Merge](#merge-and-the-3-30-300-rule))

## Canopy cover source (T30, T30_buildings)

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

## Tree segmentation (Trees)

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

## Building heights (Heights)

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


The sources themselves, with their coverage and licences, are listed under [data sources](data-sources.md#building-height-sources).

Vector sources lend each footprint the area-weighted height of the source polygons covering it (so a block the source splits into several buildings still matches), when they cover at least `min_overlap` of it. Raster sources give the median (GHS: mean) of the pixels whose centre lies inside the footprint, or of every touched pixel for footprints smaller than a pixel; GHS cells are sampled on a 10 m grid so the mean approximates an area-weighted mean. Remote sources come through Google Earth Engine (`gee_project`) and are cached under the CHM cache directory (`data.chm_cache_dir`, else `$VERDANCE_CACHE_DIR`): rasters as tiles aligned to a fixed grid, polygons as small lon/lat chunks, so reruns and neighbouring study areas reuse them. Each source's heights are cached per source (`database/heights/`), and the combined table is `database/building_heights_<key>.parquet`, keyed by the chain and the buildings cache — a new chain builds a new table rather than reusing a stale one. The run logs the share of buildings each source supplied.

`scripts/evaluate_heights.py` compares the cached sources against reference heights. Against Verisk heights in Cambridge (45,719 buildings; `--levels_col premise_floor_count`):

| Source | Coverage | MAE (m) | Bias (m) | Spearman |
|---|---|---|---|---|
| `ghs_built_h` | 95 % | 3.3 | −2.9 | 0.29 |
| `gba` | 89 % | 4.1 | −3.9 | 0.38 |
| floor count × 3 m | 99 % | 2.6 | −2.5 | 0.30 |

Both global datasets run 3–4 m below Verisk, whose two-storey median of 8.9 m suggests it measures to the roof ridge, and rank buildings only weakly. Over Bogotá's 2.17 M Overture footprints the chain above took heights from GBA for 81 %, Open Buildings Temporal 10 %, GHS-BUILT-H 4 %, UT-GLOBUS 1 % and Overture 0.1 %, leaving 4 % at the default (16 min, 8 GB peak memory).

## Tree visibility (Visibility, optional)

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

The terrain sources and their licences are listed under [data sources](data-sources.md#terrain-sources).

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

## Merge and the 3-30-300 rule

`Merge` accepts `--t3_buffers`, repeated once per buffer (e.g. `--t3_buffers 50 --t3_buffers 100`; default 10, 25, 50, 75 and 100), and combines whichever T3 buffer runs exist; Spectral, T30_buildings and Visibility outputs are included only if present. It aggregates to `--geo_level`, which for Merge defaults to the **second-finest** level of `columns.geo_levels` (the finest with a DGGS), reading sub-geo results at `--sub_geo_level` (default: finest).

Per unit it reports means — `tree_count_<b>m`, `canopy_cover` (area-weighted), `park_distance_manhattan` (road network) and `park_distance_euclidean`, plus `building_canopy_cover_<b>m`, `visible_trees_<b>m` and `visible_trees_ground_<b>m` when available — and `total_trees`. With Visibility it also reports `share_visible_<b>m`: the % of the unit's building–tree pairs within the buffer where the tree is in view (Σ visible ÷ Σ candidates).

Because the rule is a test every home should pass, Merge also evaluates it **per building** and writes `database/T3_30_300_buildings.parquet` with `meets_3`, `meets_30`, `meets_300` and `meets_3_30_300`. The per-unit table gains `pct_meets_3`, `pct_meets_30`, `pct_meets_300` and `pct_meets_3_30_300` (% of buildings passing):

- **3** — at least 3 trees within `--rule_t3_buffer` metres (default `50`): counted by T3 (`--rule_t3_metric proximity`, the default) or visible from some floor (`--rule_t3_metric visibility`, needs Visibility at that buffer). Whenever both outputs exist the table keeps `meets_3_proximity` and `meets_3_visibility` beside `meets_3`, and the combined rule under each, `meets_3_30_300_proximity` and `meets_3_30_300_visibility` (with `pct_` of all four per unit), and the parquet's `verdance_rule` metadata records which metric and columns the rule used
- **30** — canopy cover of the building's sub-geo unit (the neighbourhood reading of the rule) is ≥ 30 %; with `--rule_t30_buffer N`, T30_buildings canopy within N metres of the building instead
- **300** — distance to the nearest park is ≤ 300 m, straight-line by default (`--rule_distance euclidean`, as in the WHO guideline) or `network`

A criterion with missing input is left null and excluded from that percentage; the combined rule is only evaluated where all three are known. T3 and Visibility counts are proxies for "seeing" trees: T3 counts trees near the building, Visibility checks line of sight.

## Per-building outputs

Each building belongs to exactly one census unit — the one containing its representative point — and is output only by that unit's run, including buildings that straddle unit boundaries. Buildings whose representative point lies outside every unit are skipped. T3's default `sql` query path returns a row for every building, with `tree_count` 0 where no tree is in the buffer; `--query_method rdd` omits those buildings instead, and Merge fills them with 0. T300 keeps every building: with no reachable park within `osm.fetch_buffer` (default 2 km) its distances are null.
