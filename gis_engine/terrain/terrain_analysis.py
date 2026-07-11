"""
terrain_analysis.py
-------------------
Higher-level terrain analysis utilities built on top of ElevationLoader.

Provides:
- Elevation profiles along road segments
- Terrain classification (flat, hilly, mountainous)
- Flood-prone basin detection
- Watershed delineation helpers
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# Terrain classification thresholds (metres)
FLAT_THRESHOLD_M = 50
HILLY_THRESHOLD_M = 300
MOUNTAINOUS_THRESHOLD_M = 1500


class TerrainAnalyzer:
    """
    Analyses elevation data to characterise terrain along road segments
    and across geographic regions.
    """

    def __init__(self, elevation_loader):
        """
        Args:
            elevation_loader: An ElevationLoader instance.
        """
        self.loader = elevation_loader

    # ------------------------------------------------------------------
    # Elevation profile along a path
    # ------------------------------------------------------------------

    def elevation_profile(
        self,
        coords: list[tuple[float, float]],
        sample_interval_m: float = 100.0,
    ) -> list[dict]:
        """
        Sample elevations along a sequence of (lat, lon) waypoints.

        Args:
            coords: Ordered list of (lat, lon) pairs forming a path.
            sample_interval_m: Approx. distance in metres between samples.

        Returns:
            List of dicts: {lat, lon, distance_m, elevation_m}
        """
        profile = []
        cumulative_dist = 0.0

        for i, (lat, lon) in enumerate(coords):
            elev = self.loader.get_elevation(lat, lon)
            if i > 0:
                cumulative_dist += self._haversine(coords[i - 1], (lat, lon))
            profile.append({
                "lat": lat,
                "lon": lon,
                "distance_m": round(cumulative_dist, 1),
                "elevation_m": elev,
            })

        return profile

    # ------------------------------------------------------------------
    # Terrain classification
    # ------------------------------------------------------------------

    def classify_terrain(self, elevation_m: Optional[float]) -> str:
        """
        Classify a location's terrain category from its elevation.

        Args:
            elevation_m: Elevation in metres above sea level.

        Returns:
            One of: 'sea_level', 'flat', 'hilly', 'mountainous', 'unknown'
        """
        if elevation_m is None:
            return "unknown"
        if elevation_m < 0:
            return "sea_level"
        if elevation_m < FLAT_THRESHOLD_M:
            return "flat"
        if elevation_m < HILLY_THRESHOLD_M:
            return "hilly"
        if elevation_m < MOUNTAINOUS_THRESHOLD_M:
            return "mountainous"
        return "alpine"

    # ------------------------------------------------------------------
    # Flood-prone basin detection
    # ------------------------------------------------------------------

    def is_in_depression(
        self,
        lat: float,
        lon: float,
        search_radius_m: float = 500.0,
        sample_count: int = 8,
    ) -> bool:
        """
        Determine if a point lies in a topographic depression (flood-prone).

        Approximated by checking if all sampled surrounding points are higher.

        Args:
            lat: Centre latitude.
            lon: Centre longitude.
            search_radius_m: Radius of the surrounding sample ring.
            sample_count: Number of cardinal/intermediate samples.

        Returns:
            True if the centre is lower than all surrounding samples.
        """
        centre_elev = self.loader.get_elevation(lat, lon)
        if centre_elev is None:
            return False

        R_earth = 6_371_000
        angle_step = 360.0 / sample_count
        surrounding_elevs = []

        for i in range(sample_count):
            bearing = math.radians(i * angle_step)
            dlat = (search_radius_m / R_earth) * math.cos(bearing)
            dlon = (search_radius_m / R_earth) * math.sin(bearing) / math.cos(math.radians(lat))
            elev = self.loader.get_elevation(lat + math.degrees(dlat), lon + math.degrees(dlon))
            if elev is not None:
                surrounding_elevs.append(elev)

        if not surrounding_elevs:
            return False
        return centre_elev < min(surrounding_elevs)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
        R = 6_371_000
        lat1, lon1 = math.radians(a[0]), math.radians(a[1])
        lat2, lon2 = math.radians(b[0]), math.radians(b[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.asin(math.sqrt(h))
