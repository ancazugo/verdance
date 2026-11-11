import getpass
import os
import sys
import tempfile
from pathlib import Path

from loguru import logger
from sedona.spark import SedonaContext
from pyspark.sql.session import SparkSession

from .constants import JAVA_HOME


def _default_driver_memory() -> str:
    """Three quarters of this machine's RAM, capped at 64 GB (Spark runs locally, so the driver does all the work)."""
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return "8g"
    return f"{max(1, min(64, int(total * 0.75 / 2**30)))}g"


def _user() -> str:
    try:
        return getpass.getuser()
    except (KeyError, OSError):  # a container run with an arbitrary --user has no passwd entry
        return str(os.getuid())


def get_spark() -> SparkSession:
    """Create (or reuse) a local Sedona-enabled SparkSession with the project's JAR packages.

    Memory comes from SPARK_DRIVER_MEMORY / SPARK_EXECUTOR_MEMORY when set.
    Spark's scratch files and the JVM's temp files go to the system temp
    directory (TMPDIR; SPARK_LOCAL_DIRS still wins for Spark's own). The
    Sedona jars are downloaded once into Spark's Ivy cache: ~/.ivy2, or
    $VERDANCE_IVY_DIR when that is set.
    """
    logger.debug("Setting up Apache Sedona")

    if JAVA_HOME:
        os.environ["JAVA_HOME"] = JAVA_HOME
    # Spark's Python workers default to the first `python3` on PATH, which outside an
    # activated environment (pipx, `uv tool`, a venv's bin/verdance) is a different interpreter
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    # Spark's shuffle and spill files: the system temp directory (honours TMPDIR) unless set
    os.environ.setdefault("SPARK_LOCAL_DIRS", tempfile.gettempdir())
    # Spark runs locally: bind to loopback instead of resolving the machine's hostname,
    # which fails offline, in containers without a network and on some VPNs
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("SPARK_LOCAL_HOSTNAME", "localhost")

    driver_mem = os.getenv("SPARK_DRIVER_MEMORY") or _default_driver_memory()
    executor_mem = os.getenv("SPARK_EXECUTOR_MEMORY", "32g")
    # Local master: all cores by default, overridable for small laptops or big servers
    # (e.g. VERDANCE_SPARK_MASTER="local[4]"). The old fixed "local[10,0]" oversubscribed
    # small machines and wasted most cores on large ones.
    master = os.getenv("VERDANCE_SPARK_MASTER") or os.getenv("SPARK_MASTER") or "local[*]"
    tmp = Path(tempfile.gettempdir())

    builder = (
        SedonaContext.builder()
        .config(
            "spark.jars.packages",
            "org.apache.sedona:sedona-spark-shaded-3.5_2.12:1.9.0,"
            "org.datasyslab:geotools-wrapper:1.9.0-33.5",
        )
        .config(
            "spark.jars.repositories",
            "https://artifacts.unidata.ucar.edu/repository/unidata-all",
        )
        .config("spark.sql.debug.maxToStringFields", 10000)
        .config("spark.default.parallelism", 200)
        .config("spark.sql.adaptive.coalescePartitions.enabled", False)
        .config("spark.executor.memory", executor_mem)
        .config("spark.driver.memory", driver_mem)
        .config("spark.driver.maxResultSize", "15g")
        # keep Spark's files out of the working directory
        .config("spark.driver.extraJavaOptions", f"-Djava.io.tmpdir={tmp}")
        .config("spark.sql.warehouse.dir", str(tmp / f"verdance-{_user()}" / "spark-warehouse"))
        .master(master)
    )
    if ivy := os.getenv("VERDANCE_IVY_DIR"):
        builder = builder.config("spark.jars.ivy", ivy)

    return SedonaContext.create(builder.getOrCreate())
