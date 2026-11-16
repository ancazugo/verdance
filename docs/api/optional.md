# Optional modules

Modules with extra dependencies or external services: canopy sources, vegetation
indices, tree-crown segmentation and the visibility engines.

## Canopy sources

::: verdance.optional.chm_sources
    options:
      heading_level: 3

::: verdance.optional.canopy_meta
    options:
      heading_level: 3

::: verdance.optional.canopy_gee
    options:
      heading_level: 3

## Tree segmentation

::: verdance.optional.tree_segmentation
    options:
      heading_level: 3

::: verdance.optional.tree_eval
    options:
      heading_level: 3

## Spectral indices

::: verdance.optional.spectral
    options:
      heading_level: 3

## Visibility

Two engines compute the same metric: `raster` casts rays over a DSM and scales,
`vector` uses exact Sedona geometry and serves as the reference.

::: verdance.optional.visibility.raster_engine
    options:
      heading_level: 3

::: verdance.optional.visibility.vector_engine
    options:
      heading_level: 3

::: verdance.optional.visibility.observers
    options:
      heading_level: 3

::: verdance.optional.visibility.targets
    options:
      heading_level: 3

::: verdance.optional.visibility.los
    options:
      heading_level: 3

::: verdance.optional.visibility.dsm
    options:
      heading_level: 3
