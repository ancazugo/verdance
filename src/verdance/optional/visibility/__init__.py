"""Visibility: trees visible from each building's windows, with obstruction by buildings and trees.

Two engines share the definitions in observers / targets / pairs / params:
the raster engine (raster_engine, default) casts rays over a building +
vegetation surface model; the vector engine (vector_engine, Sedona SQL) uses
exact footprint and crown prisms, as a reference for small areas.
"""


def process_geo_code(
    sedona,
    geo_level,
    geo_code,
    sub_geo_level,
    cfg,
    output_dir,
    buffer=100,
    tree_area=10,
    tree_height=3,
    overwrite=True,
    overlay_path=None,
):
    """Visible trees per building of one geo_code with the Sedona vector engine.

    Thin wrapper (dispatched by the CLI / verdance.run) that imports vector_engine
    lazily, so importing this package does not pull in pyspark — the raster
    engine, which needs no Spark, must not pay that cost. The explicit signature
    mirrors vector_engine.process_geo_code so the dispatch's signature-based
    kwarg filtering still works.
    """
    from .vector_engine import process_geo_code as _process_geo_code

    return _process_geo_code(
        sedona, geo_level, geo_code, sub_geo_level, cfg, output_dir,
        buffer=buffer, tree_area=tree_area, tree_height=tree_height,
        overwrite=overwrite, overlay_path=overlay_path,
    )
