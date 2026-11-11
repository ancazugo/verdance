#!/usr/bin/env python3
"""
verdance CLI — measure the 3-30-300 rule of urban greening.
"""

import inspect
import concurrent.futures
import time
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from tqdm import tqdm

from .config.loader import load_config
from .dggs import RESOLUTION_RANGES, SYSTEM_NAMES, get_system
from .pipeline import load_tables, setup_output_dirs, unit_output_name
from .utils.logging_config import setup_logger
from .utils.manifest import write_run_manifest
from .utils.sedona_config import get_spark

app = typer.Typer(help="verdance: 3-30-300 urban greening metrics")


def _print_version(value: bool) -> None:
    if value:
        from . import __version__
        typer.echo(f"verdance {__version__}")
        raise typer.Exit()


def _load_config_or_exit(config: Path):
    """Load the config, turning a bad/malformed config into a one-line error instead of a traceback."""
    import yaml

    try:
        return load_config(config)
    except (ValueError, yaml.YAMLError, OSError) as e:
        typer.echo(f"Error: invalid config {config}: {e}", err=True)
        raise typer.Exit(1)


@app.callback()
def _callback(
    version: bool = typer.Option(False, "--version", is_flag=True, callback=_print_version, is_eager=True, help="Show the version and exit"),
):
    """verdance: 3-30-300 urban greening metrics."""


# Per-geo dispatch map and helper are shared with the programmatic API (verdance.run)
from .api import PROCESS_FNS as _PROCESS_FNS
from .api import run_process_code as _run_process

# Flags that tune a per-geo-code module; warned about when the chosen process ignores them
_TUNABLE_FLAGS = {"buffer", "tree_area", "tree_height", "low_threshold", "high_threshold", "gee_scale", "query_method"}


def _warn_ignored_flags(process: str) -> None:
    """Warn once when the user set --flags the chosen process silently ignores (dispatch drops them)."""
    import sys

    if process not in _PROCESS_FNS:
        return
    passed = {arg[2:].split("=")[0].replace("-", "_") for arg in sys.argv if arg.startswith("--")}
    accepted = set(inspect.signature(_PROCESS_FNS[process]).parameters)
    ignored = (passed & _TUNABLE_FLAGS) - accepted
    if ignored:
        logger.warning(f"{process} ignores these flags you set: {sorted('--' + f for f in ignored)}")


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False, readable=True, help="Path to study-area YAML config file"),
    process: str = typer.Option(..., "--process", "-p", help="Module to run: Trees, Heights, T3, T30, T30_buildings, T300, Tree_count, Visibility, Spectral, Merge"),
    geo_level: str = typer.Option(None, "--geo_level", help="Geography column to process (must be in config.columns.geo_levels)"),
    sub_geo_level: str = typer.Option(None, "--sub_geo_level", help="Sub-geography column results are reported at (default: finest level in config.columns.geo_levels)"),
    dggs: Optional[str] = typer.Option(None, "--dggs", help="Aggregate to DGGS cells instead of the finest census level: h3, s2, geohash, a5 or rhealpix; overrides config"),
    dggs_resolution: Optional[int] = typer.Option(None, "--dggs_resolution", help="Cell resolution for --dggs (h3 0-15, s2 0-30, geohash 1-12, a5 0-30, rhealpix 0-15)"),
    h3_resolution: Optional[int] = typer.Option(None, "--h3_resolution", help="[deprecated] Alias for --dggs h3 --dggs_resolution N"),
    geo_code: Optional[str] = typer.Option(None, "--geo_code", help="Single geography code to process; omit to process all"),
    query_method: str = typer.Option("rdd", "--query_method", help="Sedona query method: sql or rdd"),
    buffer: int = typer.Option(100, "--buffer", help="Buffer radius in metres around each building (T3, T30_buildings; 0 = footprint only)"),
    tree_area: int = typer.Option(10, "--tree_area", help="Trees count only if canopy area (m²) is strictly greater than this (T3, Visibility)"),
    tree_height: int = typer.Option(3, "--tree_height", help="Trees count only if height (m) is strictly greater than this (T3, Visibility)"),
    vis_engine: Optional[str] = typer.Option(None, "--vis_engine", help="Visibility engine: raster (DSM ray casting, default) or vector (exact Sedona geometry, small areas); overrides visibility.engine"),
    observer_mode: Optional[str] = typer.Option(None, "--observer_mode", help="[deprecated, ignored] Visibility observers are facade points at every floor (see the visibility config section)"),
    low_threshold: int = typer.Option(3, "--low_threshold", help="Min canopy height in metres for T30 binarisation"),
    high_threshold: int = typer.Option(60, "--high_threshold", help="Max canopy height in metres for T30 binarisation"),
    gee_scale: float = typer.Option(1.0, "--gee_scale", help="Download scale in metres for the T30 GEE canopy source (coarser scales store canopy fraction per pixel)"),
    start_date: str = typer.Option("2024-01-01", "--start_date", help="GEE imagery start date"),
    end_date: str = typer.Option("2024-12-31", "--end_date", help="GEE imagery end date"),
    imagery_ee_path: str = typer.Option("COPERNICUS/S2_HARMONIZED", "--imagery_ee_path", help="GEE imagery collection path"),
    cloud_coverage: float = typer.Option(10.0, "--cloud_coverage", help="Max cloud coverage percentage"),
    spectral_indexes: list[str] = typer.Option(["NDVI", "NDWI", "NDBI"], "--spectral_indexes", help="Spectral indices to compute"),
    composite: str = typer.Option("max", "--composite", help="Spectral temporal composite over the date range: max (default) or median"),
    t3_buffers: list[int] = typer.Option([10, 25, 50, 75, 100], "--t3_buffers", help="T3 buffer sizes for Merge step"),
    rule_t3_buffer: int = typer.Option(50, "--rule_t3_buffer", help="Merge: T3 buffer (m) whose count must be >= 3 for the rule's '3'"),
    rule_t30_buffer: Optional[int] = typer.Option(None, "--rule_t30_buffer", help="Merge: use T30_buildings canopy within this buffer (m) for the rule's '30' instead of the building's sub-geo unit canopy"),
    rule_distance: str = typer.Option("euclidean", "--rule_distance", help="Merge: park distance for the rule's '300': euclidean (straight line, WHO) or network"),
    rule_t3_metric: str = typer.Option("proximity", "--rule_t3_metric", help="Merge: the rule's '3' counts T3 trees within --rule_t3_buffer (proximity) or trees visible from some floor (visibility, needs Visibility at that buffer); both flags are reported"),
    parallel: bool = typer.Option(False, "--parallel", is_flag=True, help="Run geo codes in parallel"),
    n_workers: int = typer.Option(2, "--n_workers", help="Number of parallel workers"),
    log_level: str = typer.Option("INFO", "--log_level", help="Logging level"),
    overwrite: bool = typer.Option(True, "--overwrite/--no-overwrite", help="Overwrite existing output files (--no-overwrite resumes, returning cached CSVs)"),
):
    """Run one verdance module over a study area.

    Heights attaches a height to every building from the heights.sources chain
    (database/building_heights_<key>.parquet; Visibility builds it when missing).
    T3, T30, T30_buildings, T300, Tree_count and Visibility iterate over every
    code of --geo_level (default: the coarsest level in config.columns.geo_levels)
    and write one CSV per code, aggregated at --sub_geo_level (default: the
    finest level; T30_buildings reports per building instead).
    Spectral does the same via Google Earth Engine. Merge consolidates all
    module CSVs into `<output.base_dir>/database/T3_30_300_spectral.parquet`
    and must run last.
    """
    cfg = _load_config_or_exit(config)
    geo_levels = cfg.columns.geo_levels

    valid_processes = {"Trees", "Heights", "T3", "T30", "T30_buildings", "T300", "Tree_count", "Visibility", "Spectral", "Merge"}
    if process not in valid_processes:
        typer.echo(f"Error: --process must be one of {sorted(valid_processes)}", err=True)
        raise typer.Exit(1)

    if query_method not in ("sql", "rdd"):
        typer.echo(f"Error: --query_method must be 'sql' or 'rdd', got '{query_method}'", err=True)
        raise typer.Exit(1)

    if rule_distance not in ("euclidean", "network"):
        typer.echo(f"Error: --rule_distance must be 'euclidean' or 'network', got '{rule_distance}'", err=True)
        raise typer.Exit(1)

    if rule_t3_metric not in ("proximity", "visibility"):
        typer.echo(f"Error: --rule_t3_metric must be 'proximity' or 'visibility', got '{rule_t3_metric}'", err=True)
        raise typer.Exit(1)

    if composite not in ("max", "median"):
        typer.echo(f"Error: --composite must be 'max' or 'median', got '{composite}'", err=True)
        raise typer.Exit(1)

    if observer_mode is not None:
        logger.warning("--observer_mode is deprecated and ignored: observers are facade points at every floor")
    vis_engine = vis_engine or cfg.visibility.engine
    if vis_engine not in ("raster", "vector"):
        typer.echo(f"Error: --vis_engine must be 'raster' or 'vector', got '{vis_engine}'", err=True)
        raise typer.Exit(1)

    if geo_level and geo_level not in geo_levels:
        typer.echo(f"Error: --geo_level '{geo_level}' not in config.columns.geo_levels: {geo_levels}", err=True)
        raise typer.Exit(1)

    if h3_resolution is not None:
        if dggs is not None or dggs_resolution is not None:
            typer.echo("Error: --h3_resolution cannot be combined with --dggs/--dggs_resolution — use only the latter", err=True)
            raise typer.Exit(1)
        logger.warning("--h3_resolution is deprecated; use --dggs h3 --dggs_resolution N instead")
        dggs, dggs_resolution = "h3", h3_resolution

    dggs_from_cli = dggs is not None or dggs_resolution is not None
    if dggs is None:
        dggs = cfg.dggs
    if dggs_resolution is None:
        dggs_resolution = cfg.dggs_resolution
    if (dggs is None) != (dggs_resolution is None):
        typer.echo("Error: --dggs and --dggs_resolution must be provided together (or via config)", err=True)
        raise typer.Exit(1)
    if dggs is not None and process == "Spectral":
        # Spectral aggregates server-side on a GEE boundaries asset, so grid cells don't apply
        if dggs_from_cli:
            typer.echo("Error: Spectral uses a GEE boundaries asset and does not support --dggs", err=True)
            raise typer.Exit(1)
        logger.warning("Spectral does not support DGGS aggregation — ignoring dggs from config")
        dggs = dggs_resolution = None
    if dggs is not None:
        if dggs not in SYSTEM_NAMES:
            typer.echo(f"Error: --dggs must be one of {SYSTEM_NAMES}, got '{dggs}'", err=True)
            raise typer.Exit(1)
        lo, hi = RESOLUTION_RANGES[dggs]
        if not lo <= dggs_resolution <= hi:
            typer.echo(f"Error: --dggs_resolution for {dggs} must be between {lo} and {hi}, got {dggs_resolution}", err=True)
            raise typer.Exit(1)
        if sub_geo_level:
            typer.echo("Error: --sub_geo_level cannot be combined with --dggs (grid cells replace the sub-geography)", err=True)
            raise typer.Exit(1)
        sub_geo_level = get_system(dggs).column_name(dggs_resolution)

    log_dir = Path(cfg.output.base_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    setup_logger(log_dir / f"{process}_processing.log", log_level)

    if process == "Merge":
        from .merge import merge_output_csv, process_data
        sedona = get_spark()
        merge_output_csv(sedona, cfg, t3_buffers, dggs=dggs, dggs_resolution=dggs_resolution)
        if dggs is not None:
            # one output row per cell unless the user aggregates up to a census level
            merge_geo_level = geo_level or sub_geo_level
        else:
            merge_geo_level = geo_level or (geo_levels[-2] if len(geo_levels) > 1 else geo_levels[0])
        process_data(
            sedona, cfg, merge_geo_level, sub_geo_level or geo_levels[-1], t3_buffers,
            dggs=dggs, dggs_resolution=dggs_resolution,
            rule_t3_buffer=rule_t3_buffer, rule_t30_buffer=rule_t30_buffer, rule_distance=rule_distance,
            rule_t3_metric=rule_t3_metric,
        )
        return

    if process == "Trees":
        _run_trees(cfg, geo_level or geo_levels[0], geo_code, n_workers if parallel else 1, overwrite)
        return

    if process == "Heights":
        _run_heights(cfg, overwrite)
        return

    if process == "Visibility" and vis_engine == "raster":
        _run_visibility_raster(
            cfg, geo_level or geo_levels[0], sub_geo_level or geo_levels[-1], geo_code,
            buffer, tree_area, tree_height, dggs, dggs_resolution, n_workers if parallel else None, overwrite,
        )
        return

    if process == "Spectral":
        from .optional.spectral import setup_gee, process_geo_code as process_spectral
        if not cfg.gee_boundaries_asset:
            typer.echo("Error: Spectral requires gee_boundaries_asset in the config", err=True)
            raise typer.Exit(1)
        sedona = get_spark()
        tables = load_tables(sedona, cfg)
        setup_gee(cfg.gee_project)
        spectral_geo_level = geo_level or geo_levels[0]
        codes = [geo_code] if geo_code else tables["census_boundaries_gdf"][spectral_geo_level].unique()
        for code in tqdm(codes, desc="Regions"):
            process_spectral(
                code, spectral_geo_level, sub_geo_level or geo_levels[-1],
                imagery_ee_path, start_date, end_date, cloud_coverage,
                spectral_indexes,
                output_dir=tables["output_dirs"]["spectral"],
                composite=composite,
                gee_boundaries_asset=cfg.gee_boundaries_asset,
                overwrite=overwrite,
            )
        return

    sedona = get_spark()
    tables = load_tables(sedona, cfg, dggs=dggs, dggs_resolution=dggs_resolution)
    dirs = tables["output_dirs"]

    output_dir_map = {"T3": dirs["t3"], "T30": dirs["t30"], "T30_buildings": dirs["t30_buildings"], "T300": dirs["t300"], "Tree_count": dirs["tree_count"], "Visibility": dirs["visibility_vector"]}
    output_dir = output_dir_map[process]
    if dggs is not None and process in ("T30", "Tree_count"):
        # grid runs sit beside the census-unit outputs instead of overwriting them
        output_dir = dirs["base"] / unit_output_name(process, dggs, dggs_resolution)
        output_dir.mkdir(parents=True, exist_ok=True)

    args_dict = {
        "sedona": sedona,
        "geo_level": geo_level or geo_levels[0],
        "sub_geo_level": sub_geo_level or (geo_levels[-1] if len(geo_levels) > 1 else geo_levels[0]),
        "cfg": cfg,
        "output_dir": output_dir,
        "query_method": query_method,
        "buffer": buffer,
        "tree_area": tree_area,
        "tree_height": tree_height,
        "low_threshold": low_threshold,
        "high_threshold": high_threshold,
        "gee_scale": gee_scale,
        "overwrite": overwrite,
        "road_nodes_gdf": tables.get("road_nodes_gdf"),
        "road_edges_gdf": tables.get("road_edges_gdf"),
    }

    _warn_ignored_flags(process)
    codes = list([geo_code] if geo_code else tables["census_boundaries_gdf"][geo_level or geo_levels[0]].unique())
    logger.info(f"Running {process} for {len(codes)} regions")

    start = time.time()
    succeeded, failed = [], []

    def _record(code, result) -> None:
        # process_geo_code catches its own errors and returns None; a cached CSV
        # (no-overwrite resume) is a DataFrame, so it counts as success
        (succeeded if result is not None else failed).append(code)

    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
            future_to_code = {executor.submit(_run_process, process, args_dict, code): code for code in codes}
            for future in tqdm(concurrent.futures.as_completed(future_to_code), total=len(codes), desc="Regions"):
                code = future_to_code[future]
                try:
                    _record(code, future.result())
                except Exception:
                    logger.exception(f"{process}: error processing {code}")
                    failed.append(code)
    else:
        for code in tqdm(codes, desc="Regions"):
            try:
                _record(code, _run_process(process, args_dict, code))
            except Exception:
                logger.exception(f"{process}: error processing {code}")
                failed.append(code)

    write_run_manifest(
        output_dir, process, codes, succeeded, failed, cfg=cfg, duration_s=time.time() - start,
        extra={"geo_level": args_dict["geo_level"], "sub_geo_level": args_dict["sub_geo_level"], "buffer": buffer},
    )
    logger.info(f"{process} completed: {len(succeeded)}/{len(codes)} regions")


def _run_heights(cfg, overwrite: bool) -> None:
    """Attach a height to every building from the heights.sources chain (no Spark needed)."""
    from .heights.enrich import build_building_heights
    from .pipeline import _setup_parquet_files, ensure_context_buildings

    db_dir = setup_output_dirs(cfg)["database"]
    if not (db_dir / "buildings.parquet").exists():
        _setup_parquet_files(cfg, db_dir)
    ensure_context_buildings(cfg)
    build_building_heights(cfg, overwrite=overwrite)


def _run_visibility_raster(
    cfg, geo_level: str, sub_geo_level: str, geo_code: str | None, buffer: int, tree_area: int, tree_height: int,
    dggs: str | None, dggs_resolution: int | None, n_threads: int | None, overwrite: bool,
) -> None:
    """Visibility with the raster engine: geo codes in turn, each ray-cast on n_threads threads (no Spark
    unless a DGGS overlay has to be built)."""
    import os

    import numba
    import pandas as pd

    from .optional.visibility.inputs import VisibilityInputs
    from .optional.visibility.params import VisibilityParams
    from .optional.visibility.raster_engine import process_geo_code_raster
    from .pipeline import _setup_parquet_files, ensure_dggs_files

    if not cfg.data.trees_dir:
        raise typer.BadParameter("Visibility needs data.trees_dir (tree crowns with heights)")
    dirs = setup_output_dirs(cfg)
    db_dir = dirs["database"]
    if not (db_dir / "buildings.parquet").exists():
        _setup_parquet_files(cfg, db_dir)
    boundaries_path, overlay_path = db_dir / "census_boundaries.parquet", db_dir / "census_buildings_overlay.parquet"
    if dggs is not None:
        boundaries_path, overlay_path = ensure_dggs_files(get_spark(), db_dir, cfg, dggs, dggs_resolution)

    numba.set_num_threads(min(n_threads or min(os.cpu_count() or 1, 16), numba.config.NUMBA_NUM_THREADS))
    params = VisibilityParams.from_cfg(cfg, buffer, tree_area, tree_height)
    inputs = VisibilityInputs.load(cfg, overlay_path)
    codes = [geo_code] if geo_code else pd.read_parquet(boundaries_path, columns=[geo_level])[geo_level].dropna().unique()
    logger.info(f"Visibility (raster): {len(codes)} regions, buffer {buffer} m, {numba.get_num_threads()} threads")
    start = time.time()
    codes = list(codes)
    failed = [
        code for code in tqdm(codes, desc="Regions")
        if process_geo_code_raster(geo_level, code, sub_geo_level, cfg, inputs, params, dirs["visibility"], overwrite) is None
    ]
    write_run_manifest(
        dirs["visibility"], "Visibility", codes, [c for c in codes if c not in failed], failed,
        cfg=cfg, duration_s=time.time() - start,
        extra={"geo_level": geo_level, "sub_geo_level": sub_geo_level, "buffer": buffer, "engine": "raster"},
    )


def _run_trees(cfg, geo_level: str, geo_code: str | None, n_workers: int, overwrite: bool) -> None:
    """Segment CHM trees per geo_code into data.trees_dir (no Spark needed), then the context ring
    (`--geo_code context` segments only the ring)."""
    import geopandas as gpd
    import pandas as pd
    from .optional.tree_segmentation import process_geo_code as process_trees, chm_source

    census_parquet = setup_output_dirs(cfg)["database"] / "census_boundaries.parquet"
    if census_parquet.exists():
        boundaries = gpd.read_parquet(census_parquet)
    else:
        from .pipeline import _read_vector
        boundaries = _read_vector(cfg.data.census_boundaries).to_crs(cfg.crs)
    # "context" = the context_buffer ring around the study area, whose trees count for edge buildings
    codes = [geo_code] if geo_code else list(boundaries[geo_level].dropna().unique()) + ["context"]
    if "context" in codes and cfg.context_buffer > 0:
        from .pipeline import context_ring
        ring = context_ring(boundaries.to_crs(cfg.crs), cfg.context_buffer)
        context = gpd.GeoDataFrame({geo_level: ["context"]}, geometry=[ring], crs=cfg.crs)
        boundaries = pd.concat([boundaries.to_crs(cfg.crs), context], ignore_index=True)
    elif "context" in codes:
        codes.remove("context")
    logger.info(f"Trees: segmenting {len(codes)} regions from {chm_source(cfg)} with {n_workers} workers")
    start = time.time()
    codes = list(codes)
    failed = [
        code for code in tqdm(codes, desc="Regions")
        if process_trees(geo_level, code, cfg, boundaries, n_workers=n_workers, overwrite=overwrite) is None
    ]
    write_run_manifest(
        Path(cfg.data.trees_dir), "Trees", codes, [c for c in codes if c not in failed], failed,
        cfg=cfg, duration_s=time.time() - start, extra={"geo_level": geo_level},
    )


@app.command()
def viz(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False, readable=True, help="Path to study-area YAML config file"),
    port: int = typer.Option(8765, "--port", help="Port to serve the map on (0 = pick a free port)"),
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind (default: this machine only)"),
    rebuild: bool = typer.Option(False, "--rebuild", is_flag=True, help="Rebuild the map store even if outputs are unchanged"),
    no_browser: bool = typer.Option(False, "--no-browser", is_flag=True, help="Don't open a browser tab"),
    no_trees: bool = typer.Option(False, "--no-trees", is_flag=True, help="Skip loading trees (faster first build)"),
    log_level: str = typer.Option("INFO", "--log_level", help="Logging level"),
):
    """Open an interactive map of the results in <output.base_dir>.

    Shows whatever has been computed so far — module CSVs are read directly, so
    Merge is optional. The first start builds `database/viz.duckdb` (rebuilt
    automatically when outputs change); over SSH, forward the port
    (`ssh -L 8765:localhost:8765 host`) and open http://localhost:8765.
    """
    from .viz.catalog import build_catalog
    from .viz.server import serve
    from .viz.store import connect, ensure_store, read_meta
    from .viz.tiles import TileStore

    cfg = _load_config_or_exit(config)
    log_dir = Path(cfg.output.base_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    setup_logger(log_dir / "viz.log", log_level)
    try:
        catalog = build_catalog(cfg)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    path = ensure_store(catalog, rebuild=rebuild, include_trees=not no_trees)
    con = connect(path, read_only=True)
    try:
        meta = read_meta(con)
    finally:
        con.close()
    serve(TileStore(path, meta), host=host, port=port, open_browser=not no_browser)


def _vector_columns(path: Path, layer: str | None = None) -> set[str] | None:
    """Column names of a vector file without reading its features; None if it can't be read."""
    try:
        p = Path(path)
        if p.suffix.lower() in (".parquet", ".geoparquet"):
            import pyarrow.parquet as pq
            return set(pq.read_schema(p).names)
        import geopandas as gpd
        kwargs = {"layer": layer} if layer else {}
        return set(gpd.read_file(p, rows=0, **kwargs).columns)
    except Exception:
        return None


@app.command()
def validate(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False, readable=True, help="Path to study-area YAML config file"),
):
    """Dry-run a config: load it, check input files and columns exist, and print the resolved settings.

    Catches the common first-run failures (bad YAML, missing data files, a
    geo_level column that isn't in the census file, a geographic CRS, missing
    Java) before a long Spark run starts. Exits non-zero if anything is wrong.
    """
    from .config.schema import building_source, is_osm, is_overture

    cfg = _load_config_or_exit(config)
    errors: list[str] = []
    warnings: list[str] = []

    # Input files that are real paths (not remote-source sentinels like osm/overture)
    file_paths: list[tuple[str, str]] = [("data.census_boundaries", cfg.data.census_boundaries)]
    for name, value, is_remote in [
        ("data.buildings", cfg.data.buildings, building_source(cfg.data.buildings) is not None),
        ("data.parks_sites", cfg.data.parks_sites, is_osm(cfg.data.parks_sites) or is_overture(cfg.data.parks_sites)),
        ("data.parks_access", cfg.data.parks_access, is_osm(cfg.data.parks_access)),
        ("data.roads", cfg.data.roads, is_osm(cfg.data.roads)),
    ]:
        if value and not is_remote:
            file_paths.append((name, value))
    if cfg.data.road_nodes:
        file_paths.append(("data.road_nodes", cfg.data.road_nodes))
    for name, value in file_paths:
        if not Path(value).exists():
            errors.append(f"{name}: file not found: {value}")

    for name, value in [("data.trees_dir", cfg.data.trees_dir), ("data.chm_tiles_dir", cfg.data.chm_tiles_dir)]:
        if value and not Path(value).is_dir():
            warnings.append(f"{name}: directory not found (needed by the processes that use it): {value}")

    # Census columns: every geo_level (and any geo_level_names value) must be present
    if Path(cfg.data.census_boundaries).exists():
        cols = _vector_columns(cfg.data.census_boundaries)
        if cols is None:
            warnings.append(f"Could not read columns of data.census_boundaries: {cfg.data.census_boundaries}")
        else:
            for level in cfg.columns.geo_levels:
                if level not in cols:
                    errors.append(f"columns.geo_levels: '{level}' is not a column of the census file (has: {sorted(cols)})")
            for level, name_col in cfg.columns.geo_level_names.items():
                if name_col not in cols:
                    warnings.append(f"columns.geo_level_names[{level}]: '{name_col}' is not in the census file")

    # Buildings id column, when buildings come from a file
    if building_source(cfg.data.buildings) is None and Path(cfg.data.buildings).exists():
        cols = _vector_columns(cfg.data.buildings, cfg.columns.building_layer)
        if cols is not None and cfg.columns.building_id and cfg.columns.building_id not in cols:
            errors.append(f"columns.building_id: '{cfg.columns.building_id}' is not a column of the buildings file")

    # Java is needed for every Spark-based process
    import shutil
    from .utils.constants import JAVA_HOME
    if not (JAVA_HOME or shutil.which("java")):
        warnings.append("No Java found (JAVA_HOME unset and `java` not on PATH) — Spark processes will fail. Install JDK 17.")

    # GEE-backed sources need authentication + a project
    gee_sources = [n for n, v in [
        ("data.buildings: open_buildings", cfg.data.buildings == "open_buildings"),
        ("data.canopy_height_ee_path", bool(cfg.data.canopy_height_ee_path)),
        ("gee_boundaries_asset (Spectral)", bool(cfg.gee_boundaries_asset)),
    ] if v]
    if gee_sources and not (cfg.gee_project or __import__("os").getenv("GEE_PROJECT_NAME")):
        warnings.append(f"GEE sources configured ({gee_sources}) but no gee_project set — run `earthengine authenticate` and set gee_project")

    typer.echo(f"\nResolved config for '{cfg.study_area_name}':")
    typer.echo(f"  crs:        {cfg.crs}")
    typer.echo(f"  geo_levels: {cfg.columns.geo_levels}")
    typer.echo(f"  buildings:  {cfg.data.buildings}")
    typer.echo(f"  output:     {cfg.output.base_dir}")
    typer.echo(f"  heights:    {[s.label for s in cfg.heights.sources]}")
    if cfg.dggs:
        typer.echo(f"  dggs:       {cfg.dggs} @ res {cfg.dggs_resolution}")

    for w in warnings:
        typer.echo(f"  ! {w}", err=True)
    if errors:
        for e in errors:
            typer.echo(f"  ✗ {e}", err=True)
        typer.echo(f"\n{len(errors)} error(s) found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"\nConfig OK ({len(warnings)} warning(s)).")


def main():
    app()


if __name__ == "__main__":
    main()
