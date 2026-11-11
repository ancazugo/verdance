"""Regression tests for CSV header parsing in the viz catalog.

Covers two store-facing invariants: a quoted column name may contain a comma
(fix 2), and the column set of a CSV glob is the union across every matching
file, since the store loads them with `union_by_name = true` (fix 3).
"""

import csv

from verdance.viz.catalog import _columns, _csv_header


def _write_csv(path, header):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerow(header)


def test_csv_header_keeps_quoted_comma(tmp_path):
    # a quoted column name containing a comma must stay one column, not split in two
    f = tmp_path / "a.csv"
    _write_csv(f, ["id", "canopy, cover", "trees"])
    assert _csv_header(str(f)) == ["id", "canopy, cover", "trees"]


def test_columns_union_across_glob_preserving_order(tmp_path):
    # a column present only in a later file must still be discovered, and the
    # first-seen order (files are globbed sorted) is preserved
    _write_csv(tmp_path / "part_A.csv", ["id", "tree_count"])
    _write_csv(tmp_path / "part_B.csv", ["id", "tree_count", "canopy_cover"])
    cols = _columns(str(tmp_path / "part_*.csv"), "csv")
    assert cols == ["id", "tree_count", "canopy_cover"]


def test_columns_glob_unions_disjoint_headers(tmp_path):
    # columns unique to the first file survive too, each appearing once
    _write_csv(tmp_path / "g_A.csv", ["id", "only_a"])
    _write_csv(tmp_path / "g_B.csv", ["id", "only_b"])
    assert _columns(str(tmp_path / "g_*.csv"), "csv") == ["id", "only_a", "only_b"]


def test_columns_single_csv_is_its_header(tmp_path):
    f = tmp_path / "solo.csv"
    _write_csv(f, ["id", "value"])
    assert _columns(str(f), "csv") == ["id", "value"]
