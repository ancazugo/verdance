"""Programmatic entry point mirroring the ``verdance run`` CLI, for notebooks and scripts.

    import verdance
    cfg = verdance.load_config("city.yaml")
    verdance.run(cfg, "T3", buffer=50)      # writes T3 CSVs, returns {geo_code: DataFrame | None}
    merged = verdance.run(cfg, "Merge")     # consolidates and returns the merged unit table

The per-geo-code analysis modules (T3, T30, T30_buildings, T300, Tree_count) and
Merge are covered here. Trees, Heights, Spectral and the raster Visibility engine
have bespoke setup and remain CLI-only for now.
"""

import inspect
import time

from loguru import logger

from . import t3 as _t3
from . import t30 as _t30
from . import t30_buildings as _t30b
from . import t300 as _t300
from . import tree_count as _tc
from .config.loader import load_config
from .config.schema import VerdanceConfig
from .dggs import get_system
from .optional import visibility as _vis
from .pipeline import load_tables, unit_output_name
from .utils.manifest import write_run_manifest
from .utils.sedona_config import get_spark

# Per-geo-code modules dispatched through run() and the CLI's run loop
PROCESS_FNS = {
    "T3": _t3.process_geo_code,
    "T30": _t30.process_geo_code,
    "T30_buildings": _t30b.process_geo_code,
    "T300": _t300.process_geo_code,
    "Tree_count": _tc.process_geo_code,
    "Visibility": _vis.process_geo_code,
}

# Where each per-geo module writes its CSVs (key into pipeline.setup_output_dirs)
_OUTPUT_DIR_KEY = {
    "T3": "t3", "T30": "t30", "T30_buildings": "t30_buildings",
    "T300": "t300", "Tree_count": "tree_count", "Visibility": "visibility_vector",
}


def run_process_code(process: str, args_dict: dict, geo_code: str) -> object:
    """Dispatch one geo_code to the module's process_geo_code, passing only the kwargs it accepts."""
    fn = PROCESS_FNS[process]
    valid_params = set(inspect.signature(fn).parameters.keys())
    filtered = {k: v for k, v in args_dict.items() if k in valid_params}
    filtered["geo_code"] = geo_code
    return fn(**filtered)


def run(
    config,
    process: str,
    *,
    sedona=None,
    geo_level: str | None = None,
    sub_geo_level: str | None = None,
    geo_code: str | None = None,
    query_method: str = "sql",
    buffer: int = 100,
    tree_area: int = 10,
    tree_height: int = 3,
    low_threshold: int = 3,
    high_threshold: int = 60,
    gee_scale: float = 1.0,
    overwrite: bool = True,
    dggs: str | None = None,
    dggs_resolution: int | None = None,
    t3_buffers=(10, 25, 50, 75, 100),
    rule_t3_buffer: int = 50,
    rule_t30_buffer: int | None = None,
    rule_distance: str = "euclidean",
    rule_t3_metric: str = "proximity",
):
    """Run one verdance process programmatically and return its result.

    `config` is a path or a loaded `VerdanceConfig`. `process` is one of T3,
    T30, T30_buildings, T300, Tree_count or Merge. A Spark session is created
    (and reused via `getOrCreate`) unless one is passed as `sedona`.

    Merge returns the merged unit `DataFrame`; the per-geo modules write their
    CSVs, record a run manifest, and return `{geo_code: DataFrame | None}` (None
    for a region that failed). For Trees, Heights, Spectral and raster
    Visibility, use the `verdance` CLI.
    """
    if process != "Merge" and process not in PROCESS_FNS:
        raise NotImplementedError(
            f"verdance.run does not cover {process!r} — use the `verdance` CLI for Trees, Heights, "
            f"Spectral and raster Visibility. Programmatic processes: {sorted(PROCESS_FNS) + ['Merge']}."
        )

    cfg = config if isinstance(config, VerdanceConfig) else load_config(config)
    geo_levels = cfg.columns.geo_levels
    dggs = dggs if dggs is not None else cfg.dggs
    dggs_resolution = dggs_resolution if dggs_resolution is not None else cfg.dggs_resolution
    sedona = sedona or get_spark()

    if process == "Merge":
        from .merge import merge_output_csv, process_data

        t3b = list(t3_buffers)
        merge_output_csv(sedona, cfg, t3b, dggs=dggs, dggs_resolution=dggs_resolution)
        if dggs is not None:
            merge_geo = geo_level or sub_geo_level or get_system(dggs).column_name(dggs_resolution)
            merge_sub = sub_geo_level or get_system(dggs).column_name(dggs_resolution)
        else:
            merge_geo = geo_level or (geo_levels[-2] if len(geo_levels) > 1 else geo_levels[0])
            merge_sub = sub_geo_level or geo_levels[-1]
        return process_data(
            sedona, cfg, merge_geo, merge_sub, t3b, dggs=dggs, dggs_resolution=dggs_resolution,
            rule_t3_buffer=rule_t3_buffer, rule_t30_buffer=rule_t30_buffer,
            rule_distance=rule_distance, rule_t3_metric=rule_t3_metric,
        )

    # only T300 walks the road network and parks; the rest skip ~900 MB of reads
    tables = load_tables(sedona, cfg, dggs=dggs, dggs_resolution=dggs_resolution,
                         load_roads_parks=(process == "T300"))
    dirs = tables["output_dirs"]
    gl = geo_level or geo_levels[0]
    sgl = sub_geo_level or (geo_levels[-1] if len(geo_levels) > 1 else geo_levels[0])
    output_dir = dirs[_OUTPUT_DIR_KEY[process]]
    if dggs is not None:
        sgl = get_system(dggs).column_name(dggs_resolution)
        if process in ("T30", "Tree_count"):
            # grid runs sit beside the census-unit outputs instead of overwriting them
            output_dir = dirs["base"] / unit_output_name(process, dggs, dggs_resolution)
            output_dir.mkdir(parents=True, exist_ok=True)

    args_dict = {
        "sedona": sedona, "geo_level": gl, "sub_geo_level": sgl, "cfg": cfg, "output_dir": output_dir,
        "query_method": query_method, "buffer": buffer, "tree_area": tree_area, "tree_height": tree_height,
        "low_threshold": low_threshold, "high_threshold": high_threshold, "gee_scale": gee_scale,
        "overwrite": overwrite, "road_nodes_gdf": tables.get("road_nodes_gdf"),
        "road_edges_gdf": tables.get("road_edges_gdf"),
        # already filtered by load_tables; passing them keeps T300 from re-reading
        # and re-filtering the parks datasets once per geo code
        "parks_sites_gdf": tables.get("parks_sites_gdf"),
        "parks_access_gdf": tables.get("parks_access_gdf"),
    }
    codes = list([geo_code] if geo_code else tables["census_boundaries_gdf"][gl].unique())
    start = time.time()
    results, failed = {}, []
    for code in codes:
        try:
            result = run_process_code(process, args_dict, code)
        except Exception:
            logger.exception(f"{process}: error processing {code}")
            result = None
        results[code] = result
        if result is None:
            failed.append(code)
    write_run_manifest(
        output_dir, process, codes, [c for c in codes if c not in failed], failed,
        cfg=cfg, duration_s=time.time() - start,
        extra={"geo_level": gl, "sub_geo_level": sgl, "buffer": buffer},
    )
    return results
