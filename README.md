<!-- GitHub honours <picture> and swaps the logo with the colour scheme. PyPI's
     sanitiser drops the <source> but keeps the <img>, so the light logo shows
     there. Both need absolute URLs: relative paths break on PyPI. -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/sdgresearch/verdance/master/assets/logo/verdance-logo-dark.png">
    <img src="https://raw.githubusercontent.com/sdgresearch/verdance/master/assets/logo/verdance-logo-light.png" alt="verdance" width="320">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/verdance/"><img src="https://img.shields.io/pypi/v/verdance.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/verdance/"><img src="https://img.shields.io/pypi/pyversions/verdance.svg" alt="Python versions"></a>
  <a href="https://github.com/sdgresearch/verdance/actions/workflows/ci.yml"><img src="https://github.com/sdgresearch/verdance/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://sdgresearch.github.io/verdance/"><img src="https://img.shields.io/badge/docs-sdgresearch.github.io-2b8f4a" alt="Documentation"></a>
  <a href="https://github.com/sdgresearch/verdance/blob/master/LICENSE"><img src="https://img.shields.io/pypi/l/verdance.svg" alt="MIT licence"></a>
</p>

# verdance

Measure the **3-30-300 rule** of urban greening for any city, powered by [Apache Sedona](https://sedona.apache.org/).

The 3-30-300 rule ([Konijnendijk, 2023](https://doi.org/10.1007/s11676-022-01523-z)) states that every home should:

1. **See at least 3 trees** — measured here as the number of trees within a buffer of each building (**T3**), or the number visible from its windows (**Visibility**),
2. **Sit in a neighbourhood with at least 30 % canopy cover** (**T30**),
3. **Be within 300 m of a public green space** (**T300**).

verdance computes each metric per building and per census unit from standard geospatial inputs — or from global open data (Overture Maps, OpenStreetMap, the Meta/WRI canopy height model) where local data is missing — evaluates the rule for every building, merges everything into one analysis-ready table, and serves an interactive map of the results.

## 📖 Documentation

**[sdgresearch.github.io/verdance](https://sdgresearch.github.io/verdance/)** — installation, every config key, what each module does, and the Python API.

## Install

```bash
pip install verdance
```

Needs **Python 3.12+** and **Java 11–17** (Spark 3.5 runs on Java 17 at most). A [Docker image](https://sdgresearch.github.io/verdance/installation/#docker) bundles both. See [Installation](https://sdgresearch.github.io/verdance/installation/) for the details.

## Quick start

A study area is described by one YAML file. The smallest useful config needs only census boundaries of your own and takes everything else from global open data:

```yaml
# mycity.yaml
study_area_name: MyCity
crs: EPSG:32630                   # a projected CRS in metres covering the city

data:
  census_boundaries: /path/to/wards.gpkg   # one polygon per unit
  buildings: overture             # Overture Maps footprints
  parks_sites: overture           # Overture parks and recreation grounds
  parks_access: osm               # OSM entrances
  roads: osm                      # OSM walking network
  meta_chm: v1                    # Meta/WRI 1 m canopy height from AWS: the "30"
  trees_dir: /path/to/output/trees   # filled by `-p Trees`: the "3"

tree_segmentation:
  source: meta
  preset: meta

park_min_area_ha: 0.5             # ignore green spaces under 0.5 ha (WHO guidance)

columns:
  geo_levels: [district_code, ward_code]   # coarsest → finest

output:
  base_dir: /path/to/output
```

Then run the modules one at a time, `Merge` last, and open the map:

```bash
verdance validate -c mycity.yaml                      # check the config before a long run
verdance run -c mycity.yaml -p Trees                  # segment tree crowns from the CHM
verdance run -c mycity.yaml -p T3 --buffer 50         # trees within 50 m of each building
verdance run -c mycity.yaml -p T30                    # canopy cover per ward
verdance run -c mycity.yaml -p T300                   # distance to the nearest park
verdance run -c mycity.yaml -p Tree_count
verdance run -c mycity.yaml -p Merge --t3_buffers 50  # the rule per building and per unit
verdance viz -c mycity.yaml                           # interactive map at localhost:8765
```

The results are `database/T3_30_300_buildings.parquet` (one row per building, with `meets_3`, `meets_30`, `meets_300` and `meets_3_30_300`) and `database/T3_30_300_spectral.parquet` (one row per unit, with the share of buildings meeting each criterion).

[`examples/generic.yaml`](https://github.com/sdgresearch/verdance/blob/master/examples/generic.yaml) documents every config key.

## Modules

| Process | What it computes |
|---|---|
| `Trees` | Segments individual tree crowns from a canopy height model |
| `T3` | Trees within `--buffer` metres of each building |
| `T30` | Canopy cover % per census unit |
| `T30_buildings` | Canopy cover % within `--buffer` metres of each building |
| `T300` | Road-network and Euclidean distance from each building to the nearest park |
| `Tree_count` | Total tree count per census unit |
| `Heights` | A height for every building footprint, from an ordered chain of sources |
| `Visibility` *(optional)* | Trees in line of sight from each building's windows |
| `Spectral` *(optional)* | Spectral indices (NDVI, NDWI, …) per unit via Google Earth Engine |
| `Merge` | Evaluates the rule per building and consolidates every module's output |

Full details under [Modules](https://sdgresearch.github.io/verdance/modules/).

## Using it as a library

```python
import verdance

cfg = verdance.load_config("mycity.yaml")
verdance.run(cfg, "T3", buffer=50)
merged = verdance.run(cfg, "Merge")
```

See the [API reference](https://sdgresearch.github.io/verdance/api/).

## Contributing

See [CONTRIBUTING.md](https://github.com/sdgresearch/verdance/blob/master/CONTRIBUTING.md) and the [development guide](https://sdgresearch.github.io/verdance/development/).

## Citation

If verdance contributes to your research, please cite it — see [CITATION.cff](https://github.com/sdgresearch/verdance/blob/master/CITATION.cff).

## Licence

verdance is released under the [MIT licence](https://github.com/sdgresearch/verdance/blob/master/LICENSE). The data it downloads keeps its own licence — notably GlobalBuildingAtlas heights (`gba`) are CC BY-NC 4.0 and FABDEM terrain is CC BY-NC-SA 4.0, both **non-commercial only**. Every source's licence is listed under [data sources](https://sdgresearch.github.io/verdance/data-sources/). The bundled map viewer includes [MapLibre GL JS](https://maplibre.org/) (BSD-3-Clause).
