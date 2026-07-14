# FloodRoute System

FloodRoute is a dynamic, ultra-low latency flood routing and disaster response system designed to help emergency responders navigate safely through flood-prone areas, specifically configured for Mangaluru and Udupi. The system leverages real-time weather data, machine learning for localized flood risk assessment, and an optimized A* search algorithm to dynamically route users around submerged and high-risk roads.

## Key Features

- **Real-Time Weather Integration**: Fetches live weather data via the Open-Meteo API to determine the severity and extent of potential flooding.
- **Machine Learning Risk Assessment**: Utilizes a pre-trained ML regressor (`flood_risk_regressor.joblib`) to estimate road-level flood risks based on baseline features and real-time precipitation/wind conditions.
- **Ultra-Low Latency Routing Engine**: Employs vectorized operations via NumPy and pre-warmed memory caching of `osmnx` maps to calculate dynamic edge weights and risks with near-zero delay.
- **Advanced A* Search Pathfinding**: Custom routing algorithm that correctly identifies and traverses the safest paths, handling parallel edges efficiently and avoiding highly submerged zones.
- **React Native Web Frontend**: Interactive mapping UI allowing users to visualize routes, danger zones, and safe detours.
- **Graceful Startup & Shutdown**: A unified `run.sh` script to launch both the backend and frontend simultaneously and manage their lifecycle.

## Project Structure

- `flood/app.py`: The Python Flask backend. Houses the core routing engine (`UltraLowLatencyRouter`), ML integration, and API endpoints (`/api/route`).
- `flood-routing/ui/`: The React Native (Expo) web frontend. Provides the interactive map interface and user dashboard.
- `run.sh`: The main entry script to boot up the entire system.

## Getting Started

### Prerequisites

- **Python 3**: With required packages: `Flask`, `flask-cors`, `requests`, `joblib`, `networkx`, `osmnx`, `pandas`, `numpy`.
- **Node.js & npm**: For running the React Native web frontend.

### Installation & Execution

You can start the complete system (both frontend and backend) using the provided bash script:

```bash
chmod +x run.sh
./run.sh
```

Upon execution, the script will:
1. Terminate any stale processes on ports `5000` and `8081`.
2. Boot up the **Python Backend** on `http://localhost:5000`.
3. Boot up the **React Native Web Frontend** on `http://localhost:8081/explore`.



## How It Works

1. **Map Loading**: The system pre-loads driving networks for Mangaluru and Udupi directly into memory.
2. **Hazard Mapping**: The distance from every node to critical coastal hazard rivers (Netravati Basin, Gurupura Basin, Udyavara River Outlet, Swarna River Channel) is computed to assign baseline topological risks.
3. **Route Request**: When the frontend requests a route, the backend fetches live weather.
4. **Dynamic Weighting**: Edge weights (travel times) are dynamically increased based on the current flood risk score. Submerged edges are assigned infinite weight.
5. **Path Calculation**: The A* algorithm finds the optimal path, providing a detailed breakdown of the travel time (walking, biking, driving), the distance, and the safety reasoning.
