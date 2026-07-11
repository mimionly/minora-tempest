"""
elevation_loader.py
-------------------
Loads Digital Elevation Model (DEM) raster data from GeoTIFF files
or SRTM/ASTER tile archives.

Exposes an ElevationLoader that returns elevation in metres for a
given (lat, lon) pair or for a batch of coordinates.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

class ElevationLoader:
    """
    Reads elevation raster tiles and supports point / batch queries.

    Supports:
    - Single GeoTIFF file
    - Directory of SRTM/ASTER tiles (auto-selected by coordinate)
    """

    def __init__(self, source: str):
        """
        Args:
            source: Path to a single GeoTIFF, or a directory of DEM tiles.
        """
        import numpy as np  # type: ignore
        import rasterio  # type: ignore
        from rasterio.transform import rowcol  # type: ignore
        
        self.rasterio = rasterio
        self.rowcol = rowcol

        self.source = source
        self._dataset = None  # rasterio dataset (single-file mode)
        self._tile_cache: dict[str, object] = {}  # tile-path → rasterio dataset

        if os.path.isfile(source):
            self._dataset = self.rasterio.open(source)
            logger.info(f"ElevationLoader: opened single GeoTIFF '{source}'.")
        elif os.path.isdir(source):
            logger.info(f"ElevationLoader: using tile directory '{source}'.")
        else:
            raise FileNotFoundError(f"Elevation source not found: {source}")

    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """
        Query elevation at a single geographic coordinate.

        Args:
            lat: Latitude in decimal degrees (WGS-84).
            lon: Longitude in decimal degrees (WGS-84).

        Returns:
            Elevation in metres, or None if outside raster bounds.
        """
        dataset = self._resolve_dataset(lat, lon)
        if dataset is None:
            return None

        try:
            row, col = self.rowcol(dataset.transform, lon, lat)
            data = dataset.read(1)
            if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                val = float(data[row, col])
                nodata = dataset.nodata
                return None if (nodata is not None and val == nodata) else val
        except Exception as exc:
            logger.warning(f"Elevation query failed for ({lat}, {lon}): {exc}")
        return None

    def get_elevation_batch(self, coords: list[tuple[float, float]]) -> list[Optional[float]]:
        """
        Batch query elevation for a list of (lat, lon) tuples.

        Args:
            coords: List of (lat, lon) pairs.

        Returns:
            List of elevations (metres) in the same order, None for missing values.
        """
        return [self.get_elevation(lat, lon) for lat, lon in coords]

    def close(self) -> None:
        """Release rasterio file handles."""
        if self._dataset:
            self._dataset.close()
        for ds in self._tile_cache.values():
            ds.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_dataset(self, lat: float, lon: float):
        """Return the appropriate rasterio dataset for the coordinate."""
        if self._dataset is not None:
            return self._dataset

        tile_path = self._find_tile(lat, lon)
        if tile_path is None:
            return None

        if tile_path not in self._tile_cache:
            self._tile_cache[tile_path] = self.rasterio.open(tile_path)
        return self._tile_cache[tile_path]

    def _find_tile(self, lat: float, lon: float) -> Optional[str]:
        """
        Locate the DEM tile file covering the given coordinate.
        Supports SRTM-style naming:
          - HGT format: N18E073.hgt / N18E073.tif
          - SRTM tile format: srtm_23_16.tif  (based on tile indices)
        """
        # Strategy 1: Standard SRTM HGT naming (N18E073)
        ns = "N" if lat >= 0 else "S"
        ew = "E" if lon >= 0 else "W"
        tile_name_base = f"{ns}{abs(int(lat)):02d}{ew}{abs(int(lon)):03d}"

        for ext in (".tif", ".tiff", ".hgt", ".img"):
            candidate = os.path.join(self.source, tile_name_base + ext)
            if os.path.exists(candidate):
                return candidate

        # Strategy 2: SRTM tile-grid naming (e.g. srtm_23_16.tif)
        # Tiles are 1°×1° indexed from 0 at the equator (or -60 for SRTM).
        # SRTM v3 tiles: latitude index from -60 to 60 (row from south)
        # longitude index from -180 to 180 (col from west)
        # Common naming: srtm_<lat idx>_<lon idx>.tif  where idx starts near equator
        # For simplicity, try converting lat/lon to common scheme:
        #    lat_idx = abs(int(lat))
        #    lon_idx = abs(int(lon))
        srtm_name = f"srtm_{abs(int(lat)):02d}_{abs(int(lon)):02d}.tif"
        candidate2 = os.path.join(self.source, srtm_name)
        if os.path.exists(candidate2):
            return candidate2

        logger.debug(f"No DEM tile found for ({lat}, {lon}) in '{self.source}'.")
        return None
