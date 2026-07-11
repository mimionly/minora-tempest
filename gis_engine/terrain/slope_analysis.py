"""
slope_analysis.py
-----------------
Computes slope (gradient) and aspect (direction) from a DEM raster
and assigns per-edge slope values to road graph edges.

Slope affects:
- Edge travel-time weights (via edge_weights.py)
- Flood water flow direction (via simulation/flood/water_propagation.py)
- Fire spread direction (via simulation/wildfire/fire_spread.py)
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


def compute_slope(
    elev_a: Optional[float],
    elev_b: Optional[float],
    distance_m: float,
) -> float:
    """
    Compute slope angle in degrees between two elevation points.

    Args:
        elev_a: Elevation at start point (metres).
        elev_b: Elevation at end point (metres).
        distance_m: Horizontal distance between points (metres).

    Returns:
        Slope in degrees [0, 90]. Returns 0 if elevations are unavailable.
    """
    if elev_a is None or elev_b is None or distance_m <= 0:
        return 0.0
    rise = abs(elev_b - elev_a)
    return math.degrees(math.atan(rise / distance_m))


def compute_aspect(
    lat_a: float, lon_a: float,
    lat_b: float, lon_b: float,
) -> float:
    """
    Compute bearing (aspect) from point A to point B in degrees [0, 360).

    Args:
        lat_a, lon_a: Start coordinate.
        lat_b, lon_b: End coordinate.

    Returns:
        Compass bearing in degrees (0 = North, 90 = East, …).
    """
    dlon = math.radians(lon_b - lon_a)
    lat1 = math.radians(lat_a)
    lat2 = math.radians(lat_b)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


class SlopeAnalyzer:
    """
    Assigns slope_degrees and aspect_degrees to every edge in the road graph.

    Requires:
    - A NodeMapper for coordinate lookup
    - An ElevationLoader for DEM queries
    """

    def __init__(self, node_mapper, elevation_loader):
        """
        Args:
            node_mapper: NodeMapper instance from gis-engine/graph/node_mapper.py.
            elevation_loader: ElevationLoader from terrain/elevation_loader.py.
        """
        self.mapper = node_mapper
        self.loader = elevation_loader

    def annotate_graph(self, G) -> dict[tuple, dict]:
        """
        Compute and attach slope/aspect data to each graph edge.

        Edge attributes added:
        - slope_degrees: float
        - aspect_degrees: float
        - elevation_start_m: Optional[float]
        - elevation_end_m: Optional[float]

        Args:
            G: NetworkX DiGraph.

        Returns:
            Dict mapping (u, v) → {slope_degrees, aspect_degrees}.
        """
        slope_map: dict[tuple, dict] = {}

        for u, v, data in G.edges(data=True):
            coords_u = self.mapper.get_node_coords(u)
            coords_v = self.mapper.get_node_coords(v)

            if coords_u is None or coords_v is None:
                data["slope_degrees"] = 0.0
                data["aspect_degrees"] = 0.0
                continue

            lat_a, lon_a = coords_u
            lat_b, lon_b = coords_v
            elev_a = self.loader.get_elevation(lat_a, lon_a)
            elev_b = self.loader.get_elevation(lat_b, lon_b)
            dist = data.get("length_m", 1.0)

            slope = compute_slope(elev_a, elev_b, dist)
            aspect = compute_aspect(lat_a, lon_a, lat_b, lon_b)

            data["slope_degrees"] = round(slope, 4)
            data["aspect_degrees"] = round(aspect, 2)
            data["elevation_start_m"] = elev_a
            data["elevation_end_m"] = elev_b

            slope_map[(u, v)] = {
                "slope_degrees": slope,
                "aspect_degrees": aspect,
            }

        logger.info(f"Slope analysis complete: annotated {len(slope_map)} edges.")
        return slope_map

    def get_slope_map(self, G) -> dict[tuple, float]:
        """
        Return a simple {(u,v): slope_degrees} dict from the graph.

        Useful as input to EdgeWeightCalculator.
        """
        return {
            (u, v): data.get("slope_degrees", 0.0)
            for u, v, data in G.edges(data=True)
        }
