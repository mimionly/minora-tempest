"""
sentinel_loader.py
------------------
Simulates downloading and segmenting Sentinel-1 SAR imagery to identify flooded areas.
Produces a GeoJSON-compliant flood extent polygon dynamically based on geocoded coordinates.
"""

import logging
import numpy as np
from typing import List, Tuple, Dict
from scipy.spatial import ConvexHull

logger = logging.getLogger(__name__)


class SentinelFloodLoader:
    """
    Simulates a Sentinel-1 Synthetic Aperture Radar (SAR) imagery pipeline:
    1. Downloads SAR backscatter scene around map coordinates.
    2. Runs threshold-based water segmentation (standing water scatters radar specularly, appearing dark / low dB).
    3. Traces boundary contour using Convex Hull to produce a GeoJSON flood polygon.
    """

    def __init__(self, backscatter_threshold_db: float = -17.0):
        """
        Args:
            backscatter_threshold_db: SAR intensity threshold (dB). Values below this are flagged as water.
        """
        self.threshold = backscatter_threshold_db

    def download_sar_scene(self, center_lat: float, center_lon: float, grid_size: int = 20) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Simulate fetching a Sentinel-1 SAR intensity grid centered at coordinates.
        Creates a mock river corridor that has swollen into a flood plain.
        """
        logger.info(f"Simulating Sentinel-1 SAR download for scene centered at ({center_lat:.5f}, {center_lon:.5f})...")
        
        # Define geographic coordinate ranges for the grid
        # Spanning ~2.0km x 2.0km area
        lat_grid = np.linspace(center_lat - 0.010, center_lat + 0.010, grid_size)
        lon_grid = np.linspace(center_lon - 0.010, center_lon + 0.010, grid_size)
        
        # Grid of backscatter coefficients (dB values from -30dB to -5dB)
        sar_grid = np.zeros((grid_size, grid_size))
        
        # Simulate a low-lying river corridor running diagonally from NW to SE (with swelling flood waters)
        # Equation: lat = center_lat + (lon - center_lon) - 0.002
        for r in range(grid_size):
            cell_lat = lat_grid[r]
            for c in range(grid_size):
                cell_lon = lon_grid[c]
                
                # Distance of the cell to the simulated river corridor line
                dist_to_river = abs(cell_lat - (center_lat + (cell_lon - center_lon) - 0.002))
                
                # If close to the river corridor, simulate low backscatter (standing water ~ -20 dB)
                # swollen river flood zone: cells within ~0.004 degrees of river path
                if dist_to_river <= 0.004:
                    backscatter = -21.0 + np.random.uniform(-1.5, 1.5)
                else:
                    # Dry land backscatter (~ -12 dB)
                    backscatter = -12.0 + np.random.uniform(-2.5, 2.5)
                    
                sar_grid[r, c] = backscatter
                
        logger.info("✓ Sentinel-1 SAR scene successfully downloaded (simulated).")
        return sar_grid, lat_grid, lon_grid

    def segment_flood(self, sar_grid: np.ndarray) -> np.ndarray:
        """
        Run threshold-based segmentation on the SAR grid.
        Standing water has low backscatter intensity (specular reflection away from sensor).
        """
        logger.info(f"Running flood segmentation filter (SAR intensity threshold: {self.threshold} dB)...")
        # 1 = Flooded (water), 0 = Land
        classified = (sar_grid < self.threshold).astype(int)
        flooded_pixels = np.sum(classified)
        logger.info(f"✓ Flood segmentation complete: classified {flooded_pixels} grid cells as flooded.")
        return classified

    def get_latest_flood_polygon(self, center_lat: float, center_lon: float) -> List[Tuple[float, float]]:
        """
        Execute the full Sentinel-1 SAR pipeline and output the coordinate vertices
        of the segmented flood polygon.
        
        Returns:
            List of (lat, lon) vertices forming the closed outer boundary of the flood polygon.
        """
        sar_grid, lat_grid, lon_grid = self.download_sar_scene(center_lat, center_lon)
        classified = self.segment_flood(sar_grid)
        
        # Collect geographic coordinates of all classified flood cells
        flood_points = []
        grid_size = classified.shape[0]
        for r in range(grid_size):
            for c in range(grid_size):
                if classified[r, c] == 1:
                    flood_points.append((lat_grid[r], lon_grid[c]))
                    
        if len(flood_points) < 3:
            logger.warning("No significant flooded areas segmented. Returning empty polygon.")
            return []
            
        # Extract the outer boundary boundary using a Convex Hull over the classified points
        try:
            points_arr = np.array(flood_points)
            hull = ConvexHull(points_arr)
            
            # Form the list of vertices (ordered counter-clockwise)
            polygon_vertices = [tuple(points_arr[idx]) for idx in hull.vertices]
            # Close the polygon ring by repeating the first vertex
            polygon_vertices.append(polygon_vertices[0])
            
            logger.info(f"✓ Traced GeoJSON flood polygon consisting of {len(polygon_vertices)-1} boundary vertices.")
            return polygon_vertices
        except Exception as e:
            logger.error(f"Failed to compute flood polygon Convex Hull boundary: {e}")
            # Fallback: simple bounding box of points
            lats = [p[0] for p in flood_points]
            lons = [p[1] for p in flood_points]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            fallback_poly = [
                (min_lat, min_lon),
                (max_lat, min_lon),
                (max_lat, max_lon),
                (min_lat, max_lon),
                (min_lat, min_lon)
            ]
            logger.info("✓ Returning fallback bounding box flood polygon.")
            return fallback_poly


if __name__ == "__main__":
    # Quick self-test
    logging.basicConfig(level=logging.INFO)
    loader = SentinelFloodLoader()
    poly = loader.get_latest_flood_polygon(12.8698, 74.8430)
    print("Self-test output polygon vertices count:", len(poly))
