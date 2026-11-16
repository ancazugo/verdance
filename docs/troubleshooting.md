# Troubleshooting

- **`UnsupportedClassVersionError`, or Spark fails to start** — the Java on `PATH` / in `JAVA_HOME` is too old (< 11) or too new (> 17). Point `JAVA_HOME` at a Java 17.
- **`Overpass server busy (HTTP 502)` warnings** — the public OpenStreetMap API is overloaded; verdance retries with growing waits (up to ~15 min). Responses that did arrive are cached, so rerunning later resumes.
- **The JVM runs out of memory (`OutOfMemoryError`, `Java heap space`)** — raise `SPARK_DRIVER_MEMORY`, or process fewer units at once (drop `--parallel`, or a coarser `--geo_level`).
- **Results ignore changed inputs or column mappings** — the parquet cache is reused; delete `<output.base_dir>/database/`.
- **`Missing consolidated outputs for: [...]`** from Merge — run the listed modules first, with the same `--dggs` options (a grid Merge needs T30 and Tree_count at that grid).
- **Home directory full** — move the caches with `VERDANCE_CACHE_DIR`, `VERDANCE_IVY_DIR`, `VERDANCE_DUCKDB_EXTENSIONS` and `TMPDIR` (see [Where files go](quickstart.md#where-files-go)).
