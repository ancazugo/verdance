# Data sources

Every dataset verdance can read, with its coverage and licence. Which source each
layer uses is set in the [config](configuration.md); what each module does with it is
described under [modules](modules.md).

## Building height sources

Used by the [Heights](modules.md#building-heights-heights) process, in the order the
`heights.sources` chain lists them.

| Source | Dataset | Kind | Coverage | Licence |
|---|---|---|---|---|
| `native` | the footprints' own height / floor count | attribute | wherever mapped | that of the footprints |
| `gba` | [GlobalBuildingAtlas](https://github.com/zhu-xlab/GlobalBuildingAtlas) polygons (GEE sat-io, 5° tiles) | vector | global | **CC BY-NC 4.0 — non-commercial only** |
| `utglobus` | [UT-GLOBUS](https://www.nature.com/articles/s41597-024-03719-w) (GEE sat-io, one collection per city; `cambridge` is Cambridge, MA) | vector | ~1,100 cities | CC BY 4.0 |
| `open_buildings_temporal` | [Open Buildings 2.5D Temporal](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1), 2016–2023, fetched at 2 m | raster (~4 m) | Africa, S/SE Asia, Latin America & Caribbean | CC BY 4.0 |
| `ghs_built_h` | [GHS-BUILT-H R2023A](https://developers.google.com/earth-engine/datasets/catalog/JRC_GHSL_P2023A_GHS_BUILT_H), average net height (2018) | raster (100 m) | global | CC BY 4.0 |
| `file` | a local vector with a height column, or a raster file / directory (nDSM, GBA.Height 3 m) | either | — | — |

## Terrain sources

Ground elevation under buildings and trees, for the raster
[Visibility](modules.md#tree-visibility-visibility-optional) engine.

| Source | Dataset | Surface | Licence |
|---|---|---|---|
| `fabdem` (default) | [FABDEM](https://gee-community-catalog.org/projects/fabdem/), Copernicus GLO-30 with buildings and forests removed | bare earth | **CC BY-NC-SA 4.0 — non-commercial** |
| `copernicus` | Copernicus GLO-30 | surface model | Copernicus DEM licence |
| `nasadem` | NASADEM (SRTM) | surface model | public domain |

## Canopy cover sources

T30 and T30_buildings pick their canopy source by what is configured; the priority
order and the differences between the Meta/WRI releases are described under
[canopy cover source](modules.md#canopy-cover-source-t30-t30_buildings).

| Source | Config key | Coverage | Licence |
|---|---|---|---|
| Local CHM tiles | `data.chm_tiles_dir` | wherever you have them | that of your tiles |
| [Meta/WRI global canopy height](https://registry.opendata.aws/dataforgood-fb-forests/) | `data.meta_chm` (`v1`/`v2`) | global | CC BY 4.0 |
| GEE canopy-height asset | `data.canopy_height_ee_path` | depends on the asset | that of the asset |
| Tree polygons | `data.trees_dir` | wherever segmented | derived from the CHM used |

## Buildings, parks and roads

| Source | Config value | Coverage | Licence |
|---|---|---|---|
| [OpenStreetMap](https://www.openstreetmap.org/) | `osm` | global | ODbL |
| [Overture Maps](https://overturemaps.org/) | `overture` | global | varies by layer; see Overture |
| [Google Open Buildings v3](https://sites.research.google/open-buildings/) | `open_buildings` | Africa, S/SE Asia, Latin America & Caribbean | CC BY 4.0 |

!!! warning "Non-commercial datasets"

    GlobalBuildingAtlas heights (`gba`) are CC BY-NC 4.0 and FABDEM terrain is
    CC BY-NC-SA 4.0 — **non-commercial use only**. Every other source above permits
    commercial use under its own terms.
