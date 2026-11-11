"""binarise_tiles refuses a CHM mosaic larger than RAM instead of being OOM-killed.

The chm_tiles_dir path builds the whole mosaic in driver memory, which suits
small survey tiles (Defra VOM: 5000x5000) but not globally-tiled models: one
Meta/WRI CHM tile is 32768x32768 (v2) or 65536x65536 (v1) pixels on its own.
"""

import numpy as np
import pytest

from test_tree_segmentation import write_tif

from verdance import t30


def _tiles(tmp_path, n=2, side=64):
    return [write_tif(tmp_path / f"t{i}.tif", np.full((side, side), 5.0, dtype="float32"),
                      origin=(500000 + i * side, 200000)) for i in range(n)]


def test_mosaic_larger_than_ram_raises_with_guidance(tmp_path, monkeypatch):
    paths = _tiles(tmp_path)
    # pretend the machine has 1 KB of RAM so the tiny mosaic trips the check
    monkeypatch.setattr(t30, "_total_ram_bytes", lambda: 1024)
    with pytest.raises(MemoryError) as e:
        t30.binarise_tiles(paths, 3, 60, target_crs="EPSG:27700")
    msg = str(e.value)
    assert "meta_chm" in msg, msg          # points at the right config for global tiles
    assert "geo_level" in msg, msg         # and at the other way out


def test_normal_mosaic_is_unaffected(tmp_path, monkeypatch):
    paths = _tiles(tmp_path)
    monkeypatch.setattr(t30, "_total_ram_bytes", lambda: 8 * 2**30)
    out = t30.binarise_tiles(paths, 3, 60, target_crs="EPSG:27700")
    # every pixel is 5 m, inside the 3-60 m canopy band
    vals = np.unique(out.values[np.isfinite(out.values)])
    assert set(vals.tolist()) == {1.0}


def test_unknown_ram_does_not_block(tmp_path, monkeypatch):
    paths = _tiles(tmp_path)
    monkeypatch.setattr(t30, "_total_ram_bytes", lambda: 0)
    assert t30.binarise_tiles(paths, 3, 60, target_crs="EPSG:27700") is not None
