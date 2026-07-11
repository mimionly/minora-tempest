"""
emergency_feed.py
-----------------
Simulates receiving emergency incidents from an external feed (e.g. emergency calls, mobile app GPS, IoT sensors).
Generates coordinates dynamically near the active city center.
"""
import random
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class EmergencyFeed:
    """
    Connects to external feeds (emergency API, websockets, IoT sensors) to poll real-time emergency events.
    """
    def __init__(self):
        # Mock incident types
        self.incident_types = [
            {"type": "Flooding trapped citizen", "severity": "High"},
            {"type": "Waterlogging rescue request", "severity": "Medium"},
            {"type": "Emergency evacuation needed", "severity": "Critical"},
            {"type": "Roadblock assistance request", "severity": "Low"}
        ]
        
    def get_latest_incident(self, center_lat: float, center_lon: float) -> Dict[str, Any]:
        """
        Polls the latest incident from the feed.
        Generates a dynamic GPS coordinate within a 1.2km radius of the map center
        to simulate an incoming mobile app/GPS emergency signal.
        """
        logger.info("Polling emergency feed for new incidents (simulating mobile app / GPS sensor feed)...")
        
        # Pick a random incident type
        inc = random.choice(self.incident_types)
        
        # Offset coordinates slightly (within ~1.2km) to guarantee they lie inside the active bounding box
        lat_offset = random.uniform(-0.007, 0.007)
        lon_offset = random.uniform(-0.007, 0.007)
        
        incident_lat = center_lat + lat_offset
        incident_lon = center_lon + lon_offset
        
        incident = {
            "id": f"INC-{random.randint(1000, 9999)}",
            "type": inc["type"],
            "severity": inc["severity"],
            "lat": incident_lat,
            "lon": incident_lon,
            "timestamp": datetime.now().isoformat(),
            "source": random.choice(["Mobile App GPS", "Emergency Call (112)", "IoT Water Sensor"])
        }
        
        logger.info(f"🚨 New Live Incident Received:")
        logger.info(f"   ID:       {incident['id']}")
        logger.info(f"   Source:   {incident['source']}")
        logger.info(f"   Type:     {incident['type']} (Severity: {incident['severity']})")
        logger.info(f"   GPS Coords: ({incident['lat']:.5f}, {incident['lon']:.5f})")
        
        return incident
