"""Shared fixtures.

One Spark session serves the whole test session, deliberately.

`spark.jars.packages` is resolved when the JVM launches, not when a
`SparkSession` is built. The first session created in a process therefore fixes
the classpath for every session after it, and `getOrCreate()` silently hands
back that first context. So a plain `SparkSession` built by an early test left
Sedona's classes off the classpath for the rest of the run, and the Sedona test
later failed with:

    java.lang.ClassNotFoundException: org.apache.sedona.core.serde.SedonaKryoRegistrator

— while passing when run alone, which is the signature of exactly this problem.
Building the session once removes the ordering dependency and starts a single
JVM for the suite instead of one per module.

The session is built here rather than through `verdance.utils.sedona_config.get_spark`
because that function is tuned for real study areas: it takes every core, three
quarters of the machine's RAM, and `spark.default.parallelism = 200`. That last
one splits a three-row test frame into 200 partitions, and since it is a
SparkContext-level setting it cannot be lowered after the fact — it took the
suite from under a minute to over fourteen. Only the jar coordinates are shared
with production, so the classpath cannot drift.
"""

import os
import sys

import pytest

# Small frames, so one partition and two cores: everything here is a handful of
# rows, and the cost is per task, not per row.
TEST_SPARK_CONF = {
    "spark.ui.enabled": "false",
    "spark.sql.shuffle.partitions": "1",
    "spark.default.parallelism": "1",
    "spark.driver.memory": "2g",
    "spark.driver.bindAddress": "127.0.0.1",
}


def _sedona_session():
    """A Sedona-enabled session, or None when Sedona is not installed."""
    try:
        from sedona.spark import SedonaContext

        from verdance.utils.sedona_config import SEDONA_PACKAGES, SEDONA_REPOSITORIES
    except Exception:
        return None

    builder = (
        SedonaContext.builder()
        .master("local[2]")
        .appName("verdance-tests")
        .config("spark.jars.packages", SEDONA_PACKAGES)
        .config("spark.jars.repositories", SEDONA_REPOSITORIES)
    )
    if ivy := os.getenv("VERDANCE_IVY_DIR"):
        builder = builder.config("spark.jars.ivy", ivy)
    for key, value in TEST_SPARK_CONF.items():
        builder = builder.config(key, value)
    try:
        return SedonaContext.create(builder.getOrCreate())
    except Exception:
        return None


def _plain_session():
    """A Spark session without Sedona, for when Sedona is unavailable."""
    from pyspark.sql import SparkSession

    builder = SparkSession.builder.master("local[2]").appName("verdance-tests")
    for key, value in TEST_SPARK_CONF.items():
        builder = builder.config(key, value)
    return builder.getOrCreate()


@pytest.fixture(scope="session")
def spark():
    """The one Spark session for the suite, Sedona-enabled where possible."""
    pytest.importorskip("pyspark")
    from verdance.utils.constants import JAVA_HOME

    if JAVA_HOME:
        os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    session = _sedona_session() or _plain_session()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def sedona(spark):
    """The same session, under the name the Sedona-backed tests use."""
    return spark
