"""Config loader guards (empty/unknown-key/geographic CRS) and the `verdance validate` doctor command."""

import geopandas as gpd
import pytest
from shapely.geometry import Point, box
from typer.testing import CliRunner

from verdance.cli import app
from verdance.config.loader import load_config

runner = CliRunner()

_BASE = """study_area_name: X
crs: EPSG:32630
data: {{buildings: {b}, parks_sites: {p}, parks_access: {a}, roads: {r}, census_boundaries: {c}}}
columns: {{geo_levels: [LAD, OA], building_id: bid}}
output: {{base_dir: {out}}}
"""


def _write_inputs(d):
    gpd.GeoDataFrame({"OA": ["a", "b"], "LAD": ["x", "x"]}, geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=32630).to_parquet(d / "census.parquet")
    gpd.GeoDataFrame({"bid": [1, 2]}, geometry=[Point(0.5, 0.5), Point(1.5, 0.5)], crs=32630).to_parquet(d / "b.parquet")
    for n in ("p", "a", "r"):
        gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 1, 1)], crs=32630).to_parquet(d / f"{n}.parquet")


def _cfg(d, **repl):
    text = _BASE.format(b=d / "b.parquet", p=d / "p.parquet", a=d / "a.parquet", r=d / "r.parquet",
                        c=d / "census.parquet", out=d / "out")
    for k, v in repl.items():
        text = text.replace(k, v)
    path = d / "cfg.yaml"
    path.write_text(text)
    return path


def test_empty_config_rejected(tmp_path):
    p = tmp_path / "e.yaml"
    p.write_text("")
    with pytest.raises(ValueError, match="empty"):
        load_config(p)


def test_unknown_top_level_key_rejected(tmp_path):
    _write_inputs(tmp_path)
    path = _cfg(tmp_path)
    path.write_text(path.read_text() + "contex_buffer: 5\n")
    with pytest.raises(ValueError, match="Unknown top-level config keys"):
        load_config(path)


def test_geographic_crs_rejected(tmp_path):
    _write_inputs(tmp_path)
    path = _cfg(tmp_path, **{"EPSG:32630": "EPSG:4326"})
    with pytest.raises(ValueError, match="geographic"):
        load_config(path)


def test_validate_ok(tmp_path):
    _write_inputs(tmp_path)
    result = runner.invoke(app, ["validate", "-c", str(_cfg(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "Config OK" in result.output


def test_validate_flags_missing_geo_level_column(tmp_path):
    _write_inputs(tmp_path)
    path = _cfg(tmp_path, **{"[LAD, OA]": "[LAD, NOPE]"})
    result = runner.invoke(app, ["validate", "-c", str(path)])
    assert result.exit_code == 1
    assert "NOPE" in result.output


def test_validate_flags_missing_file(tmp_path):
    _write_inputs(tmp_path)
    path = _cfg(tmp_path)
    (tmp_path / "b.parquet").unlink()
    result = runner.invoke(app, ["validate", "-c", str(path)])
    assert result.exit_code == 1
    assert "data.buildings" in result.output
