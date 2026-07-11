"""
FastAPI server: REST endpoints + WebSocket for live route pushes.
Run with: python -m uvicorn main:app --reload
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from graph_engine import FloodRoutingEngine
import json

app = FastAPI(title="Flood-Aware Evacuation Routing")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = FloodRoutingEngine()

print("Loading OSM road network (10km radius) — this can take 15-40 seconds...")
engine.load_from_osm("Mangaluru, Karnataka, India", dist_meters=10000)
print(f"Loaded {engine.graph.number_of_nodes()} junctions and {engine.graph.number_of_edges()} roads.")

active_connections: list[WebSocket] = []


class FloodUpdate(BaseModel):
    node_a: str
    node_b: str
    severity: str  # 'impassable' | 'slow' | 'clear'


@app.get("/nodes")
def get_nodes():
    return engine.get_all_nodes()


@app.get("/edges")
def get_edges():
    return engine.get_all_edges()


@app.get("/neighbors/{node_id}")
def get_neighbors(node_id: str):
    return engine.get_neighbors(node_id)


@app.get("/locations/search")
def search_locations(q: str = ""):
    """Search named junctions/places for the start/end pickers."""
    return engine.search_locations(q)


@app.get("/roads/search")
def search_roads(q: str = ""):
    """Search named roads for flood reporting."""
    return engine.search_roads(q)


@app.get("/route")
def get_route(start: str, end: str):
    return engine.get_route(start, end)


@app.post("/flood-update")
async def flood_update(update: FloodUpdate):
    try:
        result = engine.mark_flooded(update.node_a, update.node_b, update.severity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    payload = json.dumps({"type": "flood_update", "data": result})
    for conn in active_connections:
        await conn.send_text(payload)

    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            req = json.loads(msg)
            if req.get("type") == "request_route":
                route = engine.get_route(req["start"], req["end"])
                await websocket.send_text(json.dumps({"type": "route_result", "data": route}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)


app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")