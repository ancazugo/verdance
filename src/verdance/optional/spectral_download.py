"""
Download GEE imagery to Google Drive (optional module).
"""

import time
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    import ee


def download_imagery(
    imagery_ic: "ee.Image", output_path: str, poll_s: int = 30, timeout_s: float = 7200,
) -> None:
    """Export imagery to Google Drive, polling until it finishes or `timeout_s` elapses."""
    import ee

    logger.debug(f"Downloading imagery to Google Drive: {output_path}")

    task = ee.batch.Export.image.toDrive(
        image=imagery_ic,
        description=f"Spectral_imagery_{int(time.time())}",
        folder="EarthEngine_Exports",
        fileNamePrefix=output_path,
        scale=10,
        region=imagery_ic.geometry(),
        fileFormat="GeoTIFF",
        maxPixels=1e13,
    )
    task.start()

    logger.info("Export task started. Waiting for completion...")
    deadline = time.time() + timeout_s
    while task.status()["state"] in ["READY", "RUNNING"]:
        if time.time() > deadline:
            task.cancel()
            raise TimeoutError(f"GEE export did not finish within {timeout_s:.0f}s (last state: {task.status()['state']})")
        logger.info(f"Task status: {task.status()['state']}")
        time.sleep(poll_s)

    if task.status()["state"] == "COMPLETED":
        logger.info("Download completed successfully!")
    else:
        raise RuntimeError(f"Download failed: {task.status()}")


def process_gee(
    imagery_ee_path: str,
    start_date: str,
    end_date: str,
    cloud_coverage: float,
    spectral_indexes: list[str],
    boundary_fc: "ee.FeatureCollection | None" = None,
    boundary_asset: str | None = None,
    adm0_name: str | None = None,
    project: str | None = None,
) -> None:
    """
    Download spectral imagery for a given boundary.

    Boundary can be provided as:
    - a pre-built ee.FeatureCollection (boundary_fc)
    - a GEE asset path (boundary_asset)
    - a country name from FAO/GAUL dataset (adm0_name)

    `project` sets the Earth Engine Cloud project (defaults to GEE_PROJECT_NAME).
    """
    import ee

    from .spectral import get_imagery, setup_gee

    setup_gee(project)

    if boundary_fc is None:
        if boundary_asset:
            boundary_fc = ee.FeatureCollection(boundary_asset)
        elif adm0_name:
            boundary_fc = (
                ee.FeatureCollection("FAO/GAUL/2015/level1")
                .filter(ee.Filter.eq("ADM0_NAME", adm0_name))
            )
        else:
            raise ValueError("Provide one of: boundary_fc, boundary_asset, or adm0_name")

    imagery_ic = get_imagery(boundary_fc, imagery_ee_path, start_date, end_date, cloud_coverage, spectral_indexes)
    spectral_index_path = f"spectral_{start_date}_{end_date}.tif"
    download_imagery(imagery_ic, spectral_index_path)
