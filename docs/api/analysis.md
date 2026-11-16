# Analysis modules

The per-geo-code processes that compute each part of the 3-30-300 rule, and the `Merge`
step that consolidates them. Each module exposes a `process_geo_code` entry point, which
[`verdance.run`](index.md#verdance.api.run) dispatches to.

## T3 — trees near each building

::: verdance.t3
    options:
      heading_level: 3

## T30 — neighbourhood canopy cover

::: verdance.t30
    options:
      heading_level: 3

## T30_buildings — per-building canopy cover

::: verdance.t30_buildings
    options:
      heading_level: 3

## T300 — distance to green space

::: verdance.t300
    options:
      heading_level: 3

## Tree_count — trees per unit

::: verdance.tree_count
    options:
      heading_level: 3

## Merge — the 3-30-300 rule

::: verdance.merge
    options:
      heading_level: 3
