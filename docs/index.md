<div class="verdance-hero" markdown>
![verdance](assets/logos/verdance-logo-light.svg#only-light)
![verdance](assets/logos/verdance-logo-dark.svg#only-dark)
</div>

# verdance

Measure the **3-30-300 rule** of urban greening for any city, powered by
[Apache Sedona](https://sedona.apache.org/).

The 3-30-300 rule ([Konijnendijk, 2023](https://doi.org/10.1007/s11676-022-01523-z))
states that every home should:

1. **See at least 3 trees** — the number of trees within a buffer of each building
   (**T3**), or the number visible from its windows (**Visibility**),
2. **Sit in a neighbourhood with at least 30 % canopy cover** (**T30**),
3. **Be within 300 m of a public green space** (**T300**).

verdance computes each metric per building and per census unit from standard geospatial
inputs — or from global open data (Overture Maps, OpenStreetMap, the Meta/WRI canopy
height model) where local data is missing — evaluates the rule for every building,
merges everything into one analysis-ready table, and serves an interactive map of the
results.

---

## Install

```bash
pip install verdance
```

verdance runs on Python 3.12+ and needs a Java 11–17 runtime for Spark. See
[Installation](installation.md) for the Java setup, the optional extras and the Docker
image.

## A city in one config file

A study area is described by one YAML file. The smallest useful config needs only census
boundaries of your own — one polygon per unit, with a column for each level of the
hierarchy — and takes everything else from global open data:

```yaml
# mycity.yaml
study_area_name: MyCity
crs: EPSG:32630                   # a projected CRS in metres covering the city

data:
  census_boundaries: /path/to/wards.gpkg
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

The results are `database/T3_30_300_buildings.parquet` (one row per building, with
`meets_3`, `meets_30`, `meets_300` and `meets_3_30_300`) and
`database/T3_30_300_spectral.parquet` (one row per unit, with the share of buildings
meeting each criterion).

[Get started](quickstart.md){ .md-button .md-button--primary }
[Configuration reference](configuration.md){ .md-button }
