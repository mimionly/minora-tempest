from flask import Flask
from flask_cors import CORS
from graph.weights import initialize_edge_weights
from graph.graph_loader import load_graph
from environment.monitor import start_monitor

from api.routes import route_api


app = Flask(__name__)

CORS(app)

load_graph()
initialize_edge_weights()
start_monitor()

app.register_blueprint(route_api, url_prefix="/api")


@app.route("/")
def home():

    return "FloodRoute AI Backend Running"


if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )