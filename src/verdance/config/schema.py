from dataclasses import dataclass, field


# Remote sources accepted by data.buildings instead of a file path
BUILDING_SOURCE_SENTINELS = ("osm", "overture", "open_buildings")


def _sentinel(source: str | None) -> str | None:
    return source.strip().lower() if isinstance(source, str) else None


def is_osm(source: str | None) -> bool:
    """True when a config data path requests the OSM source instead of a file."""
    return _sentinel(source) == "osm"


def is_overture(source: str | None) -> bool:
    """True when data.buildings requests Overture Maps building footprints."""
    return _sentinel(source) == "overture"


def is_open_buildings(source: str | None) -> bool:
    """True when data.buildings requests Google Open Buildings v3 polygons (via GEE)."""
    return _sentinel(source) == "open_buildings"


def building_source(source: str | None) -> str | None:
    """Sentinel name when data.buildings names a remote source, else None (file path)."""
    s = _sentinel(source)
    return s if s in BUILDING_SOURCE_SENTINELS else None


@dataclass
class ColumnMapping:
    """Which column of each input layer holds each value verdance needs."""

    building_id: str | None = None
    """Unique building identifier column. Required only when buildings come from a file."""
    building_layer: str | None = None
    """Layer name to read from a multi-layer buildings file."""
    building_height_col: str | None = None
    """Building height in metres (file sources) — read by the "native" height source."""
    building_use_col: str | None = None
    """Keep only buildings whose value here matches `building_use_value`. File-based
    sources only; OSM uses `osm.building_types` instead."""
    building_use_value: str | list[str] | None = None
    """Value, or list of values, of `building_use_col` to keep."""

    road_node_id: str = "id"
    """Unique road-node identifier column."""
    road_edge_start: str = "start_node"
    """Road-edge column holding the id of the node the edge starts at."""
    road_edge_end: str = "end_node"
    """Road-edge column holding the id of the node the edge ends at."""
    road_edge_length: str = "length"
    """Road-edge column holding the edge length in metres."""
    road_edge_layer: str = "road_link"
    """Layer name holding the road edges."""
    road_node_layer: str = "road_node"
    """Layer name holding the road nodes."""

    park_id: str = "id"
    """Unique park identifier column."""
    park_function_col: str | None = None
    """Park column naming the site's function, used to keep only public green space."""
    park_function_value: str | None = None
    """Value of `park_function_col` to keep."""
    park_access_ref_col: str | None = None
    """Access-point column referencing the park it belongs to (joins to `park_id`)."""

    tree_height_col: str = "height"
    """Tree column holding crown height in metres."""
    tree_area_col: str = "area"
    """Tree column holding crown area in square metres."""
    tree_id_col: str = "treeID"
    """Unique tree identifier column."""
    tree_layer: str = "trees"
    """Layer name holding the tree crowns."""

    geo_levels: list[str] = field(default_factory=list)
    """Census geography columns, ordered coarsest to finest,
    e.g. `["RGN22CD", "LAD22CD", "LSOA21CD", "OA21CD"]`."""
    geo_level_labels: dict[str, str] = field(default_factory=dict)
    """Display names for the levels, e.g. `{ADM3_code: Ward}` — used by the viz."""
    geo_level_names: dict[str, str] = field(default_factory=dict)
    """Per level, a `census_boundaries` column holding each unit's name,
    e.g. `{ADM3_code: ADM3_name}` — used by the viz."""


@dataclass
class DataPaths:
    """Where each input layer is read from: a file path, or a remote source name."""

    buildings: str
    """Building footprints: a file path, or one of `osm`, `overture`, `open_buildings`."""
    parks_sites: str
    """Park polygons: a file path, or `osm` / `overture`."""
    parks_access: str
    """Park access points: a file path, or `osm`."""
    roads: str
    """Road edges: a file path, or `osm`."""
    census_boundaries: str
    """Census unit boundaries, carrying every column named in `columns.geo_levels`."""
    road_nodes: str | None = None
    """Road nodes, when the road network is split across two files."""
    trees_dir: str | None = None
    """Directory of segmented tree crowns — written by `Trees`, read by T3 and Tree_count."""
    chm_tiles_dir: str | None = None
    """Directory of canopy height model tiles. Suits survey tiles; globally-tiled
    models belong in `meta_chm`, which reads only the boundary window."""
    chm_pattern: str = "*.tif"
    """Glob for CHM tiles under `chm_tiles_dir` (searched recursively), used by T30,
    T30_buildings and Trees. Defra VOM hillshades (`VOM_HS_*`) are always skipped."""
    chm_overlap: str = "latest"
    """How overlapping CHM tiles (e.g. survey years) combine, for T30, T30_buildings
    and Trees: `latest` takes the last path in sorted order (the latest year for
    `<dir>/<year>/` layouts); `max` takes the per-pixel maximum across them, so a
    tree seen in any survey counts."""
    chm_cache_dir: str | None = None
    """Where downloaded CHM tiles, raster indexes, VRTs and overlap composites go.
    None uses `$VERDANCE_CACHE_DIR`, else `<output.base_dir>/database/chm_cache`."""
    canopy_height_ee_path: str | None = None
    """Google Earth Engine canopy-height asset, e.g.
    `projects/sat-io/open-datasets/facebook/meta-canopy-height`."""
    meta_chm: str | None = None
    """Meta/WRI global 1 m CHM release from the public AWS bucket, `v1` or `v2`.
    When set it is the canopy source of T30 and T30_buildings (after
    `chm_tiles_dir`, before `canopy_height_ee_path`), and the release used wherever
    the `meta` CHM source is read (Trees, raster Visibility); None there means v1."""


@dataclass
class OSMConfig:
    """Options for layers sourced from OSM (data paths set to "osm")."""

    network_type: str = "walk"
    """osmnx network type for roads (walkable by default)."""
    building_types: list[str] | None = None
    """`building=*` tag values to fetch. None uses residential defaults;
    `["all"]` takes every building."""
    park_tags: dict[str, list[str]] | None = None
    """OSM tags identifying parks, e.g. `{leisure: [park], landuse: [village_green]}`.
    None uses public-park defaults."""
    exclude_private: bool = True
    """Drop parks tagged `access=private`, `no` or `customers`."""
    fetch_buffer: int = 2000
    """Buffer in metres around the census boundary when fetching roads, parks and
    access points, so the network can route to parks just outside the study area."""


@dataclass
class OpenBuildingsConfig:
    """Options for buildings sourced from Google Open Buildings v3 (data.buildings: open_buildings)."""

    confidence_threshold: float = 0.7
    """Minimum detection confidence to keep (dataset values lie roughly in [0.5, 1))."""


@dataclass
class OvertureConfig:
    """Options for layers sourced from Overture Maps (buildings or parks_sites set to "overture")."""

    park_land_use: list[str] = field(default_factory=lambda: ["park", "recreation_ground"])
    """`land_use` subtypes or classes kept as parks (an entry matches either).
    Protected areas such as national parks and reserves are left out by default:
    they are usually fenced or ticketed rather than open neighbourhood green space."""


@dataclass
class OutputPaths:
    """Where verdance writes its caches, intermediate CSVs and result tables."""

    base_dir: str
    """Root output directory. `database/` beneath it holds the cached inputs and
    the merged result tables."""


@dataclass
class TileSystemConfig:
    """Legacy UK VOM tile settings, parsed so older configs still load.

    Tree and CHM tile directories are always searched by file extent, so these
    no longer change which tiles are read.
    """

    enabled: bool = False
    """Ignored; retained so older configs still load."""
    tile_name_pattern: str | None = None
    """Ignored; retained so older configs still load."""


@dataclass
class TreeSegmentationConfig:
    """Options for the Trees process, which segments tree crowns from a CHM into data.trees_dir."""

    source: str | None = None
    """`chm_tiles` (from `data.chm_tiles_dir`) or `meta` (Meta/WRI global 1 m CHM
    from AWS). None uses `chm_tiles` when `data.chm_tiles_dir` is set, else `meta`."""
    preset: str = "legacy_vom"
    """`SegmentationParams` preset; `legacy_vom` reproduces the lidR
    `chm_processing.R` settings."""
    params: dict = field(default_factory=dict)
    """Per-field overrides applied on top of `preset`."""
    block_size: int = 2048
    """Block side in pixels. Each block is processed with a halo, in parallel when
    `--parallel --n_workers` is given."""
    geometry: str = "polygon"
    """`polygon` crowns, or `point` crown centroids — faster, and T3 and Tree_count
    use centroids only."""


@dataclass
class HeightSourceSpec:
    """One entry of heights.sources: a source name (see verdance.heights.SOURCE_NAMES) and its options."""

    source: str
    """Source name; see `verdance.heights.SOURCE_NAMES`."""
    options: dict = field(default_factory=dict)
    """Source-specific options."""
    name: str | None = None
    """Label written to `height_source`, e.g. `lidar` for a local nDSM.
    Defaults to the source name."""

    @property
    def label(self) -> str:
        return self.name or self.source


@dataclass
class HeightsConfig:
    """Options for the Heights process, which attaches a height to every building footprint."""

    sources: list[HeightSourceSpec] = field(default_factory=lambda: [HeightSourceSpec("native")])
    """Ordered sources; for each building the first valid height wins."""
    default_height: float = 6.0
    """Height given to buildings no source covers (`height_source` becomes `default`)."""
    storey_height: float = 3.0
    """Metres per storey: converts floor counts to heights and spaces Visibility's
    observer floors."""
    min_overlap: float = 0.3
    """Vector sources only: the minimum share of a footprint's area a source polygon
    must cover before it lends the footprint its height."""
    min_height: float = 2.0
    """Heights below this are treated as missing and fall through to the next source."""
    max_height: float = 300.0
    """Heights above this are treated as missing and fall through to the next source."""


@dataclass
class VisibilityConfig:
    """Options for the Visibility process (line of sight from building windows to trees)."""

    engine: str = "raster"
    """`raster` casts rays over a DSM (the default, and what scales); `vector` uses
    exact Sedona geometry (a reference implementation, for small areas)."""
    facade_spacing: float = 5.0
    """Metres between observer windows around each footprint."""
    facade_offset: float = 0.5
    """Metres outside the wall at which observer windows sit."""
    eye_height: float = 1.5
    """Metres above each floor at which observer windows sit; floors are spaced by
    `heights.storey_height`."""
    crown_points: int = 4
    """Points placed on each crown, in addition to the treetop, as visibility targets."""
    crown_point_height: float = 2 / 3
    """Fraction of tree height at which those crown points sit."""
    resolution: float = 1.0
    """Raster engine: DSM pixel size in metres."""
    vegetation: str = "auto"
    """Raster engine vegetation surface: `auto` uses the CHM when one is configured
    and rasterised crowns otherwise; `chm` and `crowns` force the choice."""
    mask_chm_buildings: bool = True
    """Raster engine: drop CHM pixels that fall on roofs."""
    end_skip: float | None = None
    """Metres ignored at both ends of each sightline. None uses `resolution`."""
    tile_size: float = 2000.0
    """Raster engine: buildings are processed in square tiles of this side, in metres."""


@dataclass
class TerrainConfig:
    """Ground elevation under buildings and trees for Visibility (raster engine)."""

    source: str | None = "fabdem"
    """`fabdem` (bare-earth Copernicus with buildings and forests removed;
    CC BY-NC-SA 4.0, non-commercial), `copernicus` (GLO-30) or `nasadem` — the latter
    two are surface models, so in cities they include rooftops and canopy — or a local
    DTM raster file or directory, or null for flat ground."""
    resolution: float = 30.0
    """Download resolution in metres for the GEE sources (native is about 30 m)."""


@dataclass
class VerdanceConfig:
    """A complete verdance study-area configuration, loaded from YAML by
    `verdance.load_config`.

    `examples/generic.yaml` is a fully commented template of every key below.
    """

    study_area_name: str
    """Name of the study area, used in output filenames and the viz title."""
    crs: str
    """Projected CRS in metres that every layer is reprojected to, e.g. `EPSG:32632`.
    A geographic CRS is rejected: the buffers and areas verdance computes are metric."""
    data: DataPaths
    """Input layers: where each one is read from."""
    columns: ColumnMapping
    """Which column of each input layer holds each value verdance needs."""
    output: OutputPaths
    """Where results and caches are written."""
    gee_project: str | None = None
    """Google Earth Engine project, required by the GEE-backed sources (Spectral,
    GEE canopy and building heights, and terrain for Visibility). Authenticate once
    with `earthengine authenticate`."""
    gee_boundaries_asset: str | None = None
    """GEE table asset of the census boundaries — Spectral only."""
    park_min_area_ha: float | None = None
    """Drop parks smaller than this many hectares before T300; None keeps all. The WHO
    guideline behind the 300 rule uses green spaces of at least 0.5-1 ha."""
    dggs: str | None = None
    """Aggregate to discrete global grid cells instead of the finest geo level:
    `h3`, `s2`, `geohash`, `a5` or `rhealpix`."""
    dggs_resolution: int | None = None
    """Resolution of the `dggs` grid; its meaning depends on the system chosen."""
    h3_resolution: int | None = None
    """Deprecated: use `dggs: h3` with `dggs_resolution`. The loader normalizes it there."""
    tile_system: TileSystemConfig = field(default_factory=TileSystemConfig)
    """Legacy UK VOM tile settings, parsed so older configs still load."""
    osm: OSMConfig = field(default_factory=OSMConfig)
    """Options for layers with their data path set to `osm`."""
    open_buildings: OpenBuildingsConfig = field(default_factory=OpenBuildingsConfig)
    """Options for buildings set to `open_buildings`."""
    overture: OvertureConfig = field(default_factory=OvertureConfig)
    """Options for layers set to `overture`."""
    tree_segmentation: TreeSegmentationConfig = field(default_factory=TreeSegmentationConfig)
    """Options for the Trees process."""
    heights: HeightsConfig = field(default_factory=HeightsConfig)
    """Options for the Heights process, and the building heights Visibility uses."""
    visibility: VisibilityConfig = field(default_factory=VisibilityConfig)
    """Options for the Visibility process."""
    terrain: TerrainConfig = field(default_factory=TerrainConfig)
    """Ground elevation under buildings and trees, for raster Visibility."""
    context_buffer: float = 100.0
    """Metres around the study area from which context is gathered: buildings that
    block views (Visibility) and trees that count for edge buildings (Trees, so T3
    and Visibility)."""
