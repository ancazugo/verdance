# Pipeline

Reading the configured inputs into Spark, laying out the outputs, and the discrete
global grid backends that can replace census units.

## Input loading and output layout

::: verdance.pipeline
    options:
      heading_level: 3

## Config loading

::: verdance.config.loader
    options:
      heading_level: 3

## Discrete global grids

Selected with the `dggs` config key. Each backend implements the same interface, so
H3, S2, geohash, A5 and rHEALPix are interchangeable.

::: verdance.dggs
    options:
      heading_level: 3

::: verdance.dggs.base
    options:
      heading_level: 3
