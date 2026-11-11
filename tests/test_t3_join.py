"""T3's SQL spatial join: every building comes back, zero-filled when no tree is in range.

The only Sedona-backed test in the suite, so it is marked `spark` and can be
deselected with `-m "not spark"`. It pins the contract that made the SQL path
switch from a LEFT JOIN on ST_Intersects (which Sedona degenerates into a
nested loop) to an inner join plus a zero-fill.
"""

import pytest

pytest.importorskip("sedona")

from verdance.t3 import count_trees
from verdance.utils.data_processing import view_suffix

GEO = "TEST_AREA"
BUFFER = 50


@pytest.fixture(scope="module")
def sedona():
    from verdance.utils.sedona_config import get_spark

    s = get_spark()
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


@pytest.fixture(scope="module")
def scene(sedona):
    """Three buildings 50 m apart in reach terms: A has two trees, B and C none."""
    sfx = view_suffix(GEO)
    sedona.createDataFrame(
        [("A", 0.0, 0.0), ("B", 100.0, 0.0), ("C", 1000.0, 0.0)], ["building_id", "x", "y"]
    ).createOrReplaceTempView("pts")
    sedona.sql(
        f"SELECT building_id, ST_Buffer(ST_Point(x, y), {BUFFER}) AS geometry FROM pts"
    ).createOrReplaceTempView(f"buildings_buffers_{sfx}")

    # both trees sit within 50 m of A, 80-90 m from B, far from C
    sedona.createDataFrame([(1, 10.0, 0.0), (2, 20.0, 0.0)], ["tree_id", "x", "y"]) \
        .createOrReplaceTempView("tpts")
    sedona.sql("SELECT tree_id, ST_Point(x, y) AS geometry FROM tpts") \
        .createOrReplaceTempView(f"geo_trees_{sfx}")
    return sfx


@pytest.mark.spark
def test_every_building_returned_with_zero_fill(sedona, scene):
    df = count_trees(sedona, GEO).set_index("building_id")["tree_count"].to_dict()
    # no building is dropped for having no tree in range
    assert set(df) == {"A", "B", "C"}
    assert df["A"] == 2
    assert df["B"] == 0
    assert df["C"] == 0


@pytest.mark.spark
def test_tree_total_is_preserved(sedona, scene):
    df = count_trees(sedona, GEO)
    # each tree is credited to every building whose buffer reaches it (only A here)
    assert int(df["tree_count"].sum()) == 2
    assert len(df) == 3
