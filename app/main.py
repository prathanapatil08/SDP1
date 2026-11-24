
from flask import Flask, jsonify
import psutil
from datetime import datetime

# Create Flask application
app = Flask(__name__)


# Home route
@app.route("/")
def home():
    return jsonify({
        "project": "Intelligent AIOps Platform",
        "status": "Running",
        "message": "Welcome to SDP"
    })


# Health monitoring route
@app.route("/health")
def health():

    cpu = psutil.cpu_percent(interval=1)

    memory = psutil.virtual_memory().percent

    return jsonify({
        "application_status": "Healthy",
        "cpu_usage": cpu,
        "memory_usage": memory,
        "timestamp": datetime.now().isoformat()
    })


# Start application
if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
