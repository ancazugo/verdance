# Data sources

Fetching buildings, parks and roads from global open data, attaching building heights,
and reading ground elevation. Which source each layer uses is set in the
[config](../configuration.md); the licence of each dataset is listed under
[data sources](../data-sources.md).

## OpenStreetMap

::: verdance.osm
    options:
      heading_level: 3

## Overture Maps

::: verdance.overture
    options:
      heading_level: 3

## Google Open Buildings

::: verdance.open_buildings
    options:
      heading_level: 3

## Building heights

An ordered chain of sources; for each building the first valid height wins.

::: verdance.heights
    options:
      heading_level: 3

::: verdance.heights.base
    options:
      heading_level: 3

::: verdance.heights.enrich
    options:
      heading_level: 3

::: verdance.heights.match
    options:
      heading_level: 3

## Terrain

::: verdance.terrain
    options:
      heading_level: 3
