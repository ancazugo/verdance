# Installation

verdance needs **Python 3.12 or 3.13** and **Java 11–17** (Spark 3.5 runs on Java 17 at
most; newer Java versions fail).

```bash
pip install verdance          # or: uv pip install verdance / uv tool install verdance / pipx install verdance
verdance --version
```

## Java

Install a JDK 17 and make sure `java -version` reports it, or point `JAVA_HOME` at it:

```bash
sudo apt install openjdk-17-jre-headless          # Debian / Ubuntu
brew install openjdk@17                           # macOS (then follow brew's note to link it)
conda install -c conda-forge openjdk=17           # any OS, inside a conda environment
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # if another Java is the default
```

The first Spark-based run downloads the Sedona jars (~110 MB, once) into Spark's Ivy
cache (`~/.ivy2`, or `VERDANCE_IVY_DIR`), so it needs internet access.

!!! tip "No Java at hand?"

    Use the [Docker image](#docker), which bundles Java and the jars.

## Google Earth Engine (optional)

Some data sources are read from Earth Engine: the `Spectral` module,
`canopy_height_ee_path`, `data.buildings: open_buildings`, the remote building-height
sources and terrain for Visibility. They need a Google Cloud project with Earth Engine
enabled: authenticate once with `earthengine authenticate` (installed with verdance) and
set `gee_project: <your-project>` in the config.

Everything else — including the global open-data sources Overture, OpenStreetMap and the
Meta canopy height model from AWS — needs no account.

## Settings from a `.env` file

verdance reads a `.env` file in the working directory (or a parent directory) at
startup; variables already set in the environment win. Every setting is optional:

```bash
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64   # or JDK_HOME, see below
VERDANCE_CACHE_DIR=/big/disk/verdance_cache    # shared download cache
GEE_PROJECT_NAME=my-gee-project                # Earth Engine project when the config has no gee_project
```

## Environment variables

| Variable | Meaning |
|---|---|
| `JAVA_HOME` | The Java 11–17 installation Spark runs on. `JDK_HOME` takes precedence: an absolute path, or the name of a JDK directory under `~/.jdk/` (the layout of the [install-jdk](https://pypi.org/project/install-jdk/) package) |
| `SPARK_DRIVER_MEMORY` | Spark's heap (e.g. `16g`). Spark runs locally, so this is the memory for all its work. Default: three quarters of the machine's RAM, at most `64g` |
| `GEE_PROJECT_NAME` | Earth Engine project used when the config has no `gee_project` |
| `VERDANCE_CACHE_DIR` | Shared download cache for canopy tiles, Earth Engine rasters and OSM responses |
| `VERDANCE_IVY_DIR` | Where the Sedona/Spark jars are cached |
| `VERDANCE_DUCKDB_EXTENSIONS` | Where the DuckDB spatial extension is cached |
| `VERDANCE_SPARK_MASTER` | Spark master URL; defaults to `local[*]` |
| `TMPDIR` | Temporary files, including Spark shuffle and spill (`SPARK_LOCAL_DIRS` overrides it for shuffle files) |

Where each of these lands by default is covered in
[where files go](quickstart.md#where-files-go).

## Docker

The image bundles Python 3.12, OpenJDK 17, the Sedona jars and DuckDB's spatial
extension, so it runs without Java installed and without network access for them. Build
it from a clone of the repository:

```bash
git clone https://github.com/sdgresearch/verdance.git && cd verdance
docker build -t verdance .
docker run --rm verdance --version
```

Mount a project directory holding the config, the inputs and the output folder, and use
**container paths** in the config (e.g. `census_boundaries: /work/data/wards.gpkg`,
`base_dir: /work/output`). The image's entrypoint is `verdance`, so pass only its
arguments:

```bash
docker run --rm --user "$(id -u):$(id -g)" \
  -v "$PWD":/work \
  verdance run -c /work/mycity.yaml -p T3 --buffer 50
```

`--user "$(id -u):$(id -g)"` makes the output files yours on a standard Docker install.
With **rootless Docker** use `--user 0:0` instead: there the container's root is you,
while any other user maps to a host ID you can't write as. Docker Desktop needs neither.
To keep downloads between containers, add a cache mount:
`-v "$HOME/verdance_cache":/cache -e VERDANCE_CACHE_DIR=/cache`.

- **Memory.** The image defaults to `SPARK_DRIVER_MEMORY=4g`; raise it on a bigger host
  with `-e SPARK_DRIVER_MEMORY=32g`.
- **Earth Engine.** Authenticate once on the host (`earthengine authenticate`), then
  mount the credentials:
  `-v "$HOME/.config/earthengine":/home/verdance/.config/earthengine:ro`, and set
  `gee_project` in the config.
- **The map.** Publish the port and listen on all interfaces inside the container:
  `docker run --rm -p 8765:8765 -v "$PWD":/work verdance viz -c /work/mycity.yaml --host 0.0.0.0 --no-browser`,
  then open <http://localhost:8765>.
- **docker compose.** [`docker-compose.yml`](https://github.com/sdgresearch/verdance/blob/master/docker-compose.yml)
  mounts `./data` at `/data`, `./config` at `/config` and `./output` at `/output` (set
  `output.base_dir: /output`), and keeps a download cache in `./cache`:
  `docker compose run --rm verdance run -c /config/mycity.yaml -p T3 --buffer 50`.
