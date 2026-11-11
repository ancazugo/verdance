"""Regression tests for the optional-module hardening fixes.

Covers: translate_tile_name validation/case consistency, the VOM UDFs derived
from their plain functions staying serialisable, the CHM raster-index cache
keying on file mtime/size, build_vrt warning (not failing) on grid-phase
misalignment, and the vector engine's single-entry inputs cache.
"""

import os

import numpy as np
import pytest
from loguru import logger

from test_tree_segmentation import write_tif

CRS = "EPSG:27700"
PATTERN = "VOM_[A-Z][A-Z][0-9]*.tif"


# --------------------------------------------------------------------------- #
# vom_processing.translate_tile_name
# --------------------------------------------------------------------------- #

def test_translate_tile_name_roundtrips_with_consistent_case():
    from verdance.optional.vom_processing import translate_tile_name

    assert translate_tile_name("TL0045") == "TL04NW"
    assert translate_tile_name("TL04NW") == "TL0045"  # uppercase prefix both ways
    # both directions are inverses of each other
    assert translate_tile_name(translate_tile_name("TL0045")) == "TL0045"
    assert translate_tile_name(translate_tile_name("TL04NW")) == "TL04NW"
    # lowercase input is normalised, not echoed back in a different case
    assert translate_tile_name("tl04nw") == "TL0045"
    assert translate_tile_name("tl0045") == "TL04NW"


def test_translate_tile_name_raises_value_error_not_assert():
    """The length guard must survive `python -O` (assert would be stripped)."""
    from verdance.optional.vom_processing import translate_tile_name

    with pytest.raises(ValueError):
        translate_tile_name("TL45")
    with pytest.raises(ValueError):
        translate_tile_name("TL004500")


# --------------------------------------------------------------------------- #
# vom_processing UDFs derived from the plain functions
# --------------------------------------------------------------------------- #

def test_vom_plain_functions_still_correct():
    from verdance.optional import vom_processing as vom

    assert vom.extract_vom_type("a/VOM_HS_TL0000.tif") == "HS"
    assert vom.extract_vom_type("a/VOM_CHM_TL0000.tif") == "CHM"
    assert vom.extract_grid_reference("VOM_TL0045_2020.tif") == "TL0045"
    assert vom.extract_grid_reference("nope.tif") is None
    assert vom.extract_year("/data/2021/VOM_TL0045_2021.tif") == 2021
    assert vom.extract_year("/data/no-year/x.tif") is None


def test_vom_udfs_are_cloudpickle_serialisable():
    """The derived UDFs must serialise for Spark executors (cloudpickle is what Spark uses)."""
    import cloudpickle
    from functools import partial

    from verdance.optional import vom_processing as vom

    # module-level UDFs exist and wrap the plain functions
    assert callable(vom.extract_vom_type_udf)
    assert callable(vom.extract_year_udf)
    udf = vom.make_extract_grid_reference_udf()
    assert callable(udf)

    # the underlying callables round-trip through cloudpickle and keep behaving
    f = cloudpickle.loads(cloudpickle.dumps(vom.extract_vom_type))
    assert f("x/VOM_HS_a.tif") == "HS"
    g = cloudpickle.loads(cloudpickle.dumps(vom.extract_year))
    assert g("/2021/x.tif") == 2021
    h = cloudpickle.loads(cloudpickle.dumps(partial(vom.extract_grid_reference, pattern=vom._GRID_REF_PATTERN)))
    assert h("VOM_TL0045_2020.tif") == "TL0045"


# --------------------------------------------------------------------------- #
# chm_sources.raster_index cache invalidation on mtime/size
# --------------------------------------------------------------------------- #

def test_raster_index_reuses_cache_when_unchanged(tmp_path):
    from verdance.optional.chm_sources import raster_index

    tiles = tmp_path / "tiles"
    tiles.mkdir()
    write_tif(tiles / "VOM_TL0000.tif", np.zeros((10, 10), np.float32))
    cache = tmp_path / "cache"
    raster_index(tiles, PATTERN, cache)
    cached = next(cache.glob("raster_index_*.parquet"))
    mtime = cached.stat().st_mtime_ns
    raster_index(tiles, PATTERN, cache)
    assert cached.stat().st_mtime_ns == mtime  # reused, not rebuilt


def test_raster_index_rebuilds_when_tile_contents_change(tmp_path):
    """Replacing a tile's contents under the same name must not serve a stale extent."""
    from verdance.optional.chm_sources import raster_index

    tiles = tmp_path / "tiles"
    tiles.mkdir()
    tile = tiles / "VOM_TL0000.tif"
    write_tif(tile, np.zeros((10, 10), np.float32), origin=(500000, 200000))
    cache = tmp_path / "cache"
    idx1 = raster_index(tiles, PATTERN, cache)
    bounds1 = tuple(round(v, 3) for v in idx1.geometry.iloc[0].bounds)

    # same filename, different extent, newer mtime (bumped so the test is robust to clock granularity)
    write_tif(tile, np.zeros((10, 10), np.float32), origin=(600000, 300000))
    newer = tile.stat().st_mtime_ns + 1_000_000_000
    os.utime(tile, ns=(newer, newer))

    idx2 = raster_index(tiles, PATTERN, cache)
    bounds2 = tuple(round(v, 3) for v in idx2.geometry.iloc[0].bounds)
    assert bounds1 != bounds2  # a stale cache would still report bounds1


# --------------------------------------------------------------------------- #
# chm_sources.build_vrt grid-phase alignment
# --------------------------------------------------------------------------- #

def _warnings_during(fn):
    captured = []
    sink = logger.add(captured.append, level="WARNING", format="{message}")
    try:
        result = fn()
    finally:
        logger.remove(sink)
    return result, [str(m) for m in captured]


def test_build_vrt_warns_but_does_not_fail_on_grid_phase_offset(tmp_path):
    from verdance.optional.chm_sources import build_vrt

    a = write_tif(tmp_path / "a.tif", np.zeros((10, 10), np.float32), origin=(500000.0, 200000.0))
    # offset by 0.3 px horizontally: same CRS and pixel size, but off the shared grid
    b = write_tif(tmp_path / "b.tif", np.zeros((10, 10), np.float32), origin=(500010.3, 200000.0))
    vrt, msgs = _warnings_during(lambda: build_vrt([str(a), str(b)], tmp_path / "m.vrt"))
    assert vrt.exists()  # does not hard-fail
    assert any("off the pixel grid" in m for m in msgs)


def test_build_vrt_silent_when_tiles_share_grid(tmp_path):
    from verdance.optional.chm_sources import build_vrt

    a = write_tif(tmp_path / "a.tif", np.zeros((10, 10), np.float32), origin=(500000.0, 200000.0))
    b = write_tif(tmp_path / "b.tif", np.zeros((10, 10), np.float32), origin=(500010.0, 200000.0))
    vrt, msgs = _warnings_during(lambda: build_vrt([str(a), str(b)], tmp_path / "m.vrt"))
    assert vrt.exists()
    assert not any("off the pixel grid" in m for m in msgs)


# --------------------------------------------------------------------------- #
# vector_engine single-entry inputs cache
# --------------------------------------------------------------------------- #

def test_vector_engine_inputs_cache_is_capped_to_one(monkeypatch):
    from verdance.optional.visibility import vector_engine as ve

    ve._INPUTS.clear()
    calls = []

    class FakeInputs:
        @staticmethod
        def load(cfg, overlay):
            calls.append((cfg.output.base_dir, overlay))
            return ("inputs", cfg.output.base_dir, overlay)

    monkeypatch.setattr(ve, "VisibilityInputs", FakeInputs)

    class Cfg:
        def __init__(self, base):
            self.output = type("Out", (), {"base_dir": base})()

    c1, c2 = Cfg("/a"), Cfg("/b")
    ve._inputs(c1, None)
    assert len(ve._INPUTS) == 1 and len(calls) == 1
    ve._inputs(c1, None)  # same key: reused, no reload, still one entry
    assert len(ve._INPUTS) == 1 and len(calls) == 1
    ve._inputs(c2, None)  # new key: evicts the previous config
    assert len(ve._INPUTS) == 1 and len(calls) == 2
    ve._INPUTS.clear()
