"""SQL literal escaping (quotes in census codes) and per-module run manifests."""

import os
import sys

import pandas as pd
import pytest

from verdance.utils.data_processing import sql_str
from verdance.utils.manifest import read_run_manifest, warn_on_incomplete_runs, write_run_manifest


def test_sql_str_escapes_quotes_and_backslashes():
    assert sql_str("E01000001") == "'E01000001'"
    assert sql_str("King's Cross") == r"'King\'s Cross'"
    assert sql_str(123) == "'123'"
    assert sql_str("a\\b") == r"'a\\b'"
    # no raw single quote survives unescaped (would break/inject the query)
    assert "'" not in sql_str("L'Hospitalet")[1:-1].replace("\\'", "")


def test_write_and_read_manifest(tmp_path):
    path = write_run_manifest(
        tmp_path, "T3", attempted=["A", "B", "C"], succeeded=["A", "C"], failed=["B"],
        duration_s=1.23, extra={"geo_level": "LAD"},
    )
    assert path.name == "_manifest.json"
    manifest = read_run_manifest(tmp_path)
    assert manifest["process"] == "T3"
    assert manifest["n_attempted"] == 3
    assert manifest["n_failed"] == 1
    assert manifest["failed"] == ["B"]
    assert manifest["geo_level"] == "LAD"
    assert manifest["duration_s"] == 1.23


def test_manifest_stringifies_numeric_codes(tmp_path):
    write_run_manifest(tmp_path, "T30", attempted=[1, 2], succeeded=[1, 2], failed=[])
    assert read_run_manifest(tmp_path)["succeeded"] == ["1", "2"]


def test_read_manifest_absent_returns_none(tmp_path):
    assert read_run_manifest(tmp_path) is None


def test_warn_on_incomplete_runs_flags_failures(tmp_path):
    good, bad = tmp_path / "T30", tmp_path / "T3"
    write_run_manifest(good, "T30", attempted=["A"], succeeded=["A"], failed=[])
    write_run_manifest(bad, "T3", attempted=["A", "B"], succeeded=["A"], failed=["B"])
    incomplete = warn_on_incomplete_runs(tmp_path, {"T30": good, "T3": bad, "T300": tmp_path / "missing"})
    assert incomplete == ["T3"]


@pytest.fixture(scope="module")
def spark():
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    from verdance.utils.constants import JAVA_HOME

    if JAVA_HOME:
        os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    s = (SparkSession.builder.master("local[1]").appName("verdance-sqlstr-test")
         .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1").getOrCreate())
    yield s
    s.stop()


def test_sql_str_round_trips_through_spark(spark):
    # a code with an apostrophe must filter correctly, not raise a parse error
    spark.createDataFrame(
        pd.DataFrame({"geo": ["L'Hospitalet", "Barcelona", "King's Lynn"], "n": [1, 2, 3]})
    ).createOrReplaceTempView("places")
    for code, expected in [("L'Hospitalet", 1), ("King's Lynn", 3), ("Barcelona", 2)]:
        rows = spark.sql(f"SELECT n FROM places WHERE geo = {sql_str(code)}").collect()
        assert [r["n"] for r in rows] == [expected]
