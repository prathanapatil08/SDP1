
import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_FILE = BASE_DIR / "data" / "metrics.csv"
OUTPUT_FILE = BASE_DIR / "data" / "anomaly_results.csv"

# Load monitoring data
data = pd.read_csv(DATA_FILE)
if "timestamp" not in data.columns:
    raise ValueError("Metrics file must contain a timestamp column.")

# Features used by the AI model
features = [
    "cpu_usage",
    "memory_usage",
    "available_memory_mb"
]

# Check available data
if len(data) < 100:
    raise ValueError(
        "Collect at least 100 readings before training the model."
    )

# Convert features into numeric values
data[features] = data[features].apply(
    pd.to_numeric, errors="coerce"
)

# Remove incomplete records
data = data.dropna(subset=features).copy()

if len(data) < 100:
    raise ValueError(
        "Not enough valid metric readings. Collect more data."
    )

existing_results = None
if OUTPUT_FILE.exists():
    existing_results = pd.read_csv(OUTPUT_FILE)
    if not existing_results.empty and "timestamp" not in existing_results.columns:
        raise ValueError(
            "Existing anomaly results have no timestamp column; refusing to overwrite them."
        )

if existing_results is None or existing_results.empty:
    new_data = data.copy()
else:
    processed_timestamps = set(existing_results["timestamp"].astype(str))
    new_data = data[
        ~data["timestamp"].astype(str).isin(processed_timestamps)
    ].copy()

if new_data.empty:
    print("No newly collected metric timestamps to analyze.")
    print("Existing anomaly results were preserved.")
    raise SystemExit(0)

# Train using readings from the normal collection period
model = IsolationForest(
    n_estimators=100,
    contamination=0.05,
    random_state=42
)

model.fit(data[features])

# Predict newly collected readings. Isolation Forest is an outlier detector,
# so a higher resource reading is not automatically an anomaly.
# 1 = Normal
# -1 = Anomaly
new_data["prediction"] = model.predict(new_data[features])

# Calculate anomaly score
new_data["anomaly_score"] = model.decision_function(
    new_data[features]
)

# Convert prediction into readable labels
new_data["status"] = new_data["prediction"].map({
    1: "Normal",
    -1: "Anomaly"
})

# Append only new timestamps so historical results remain intact.
if OUTPUT_FILE.exists():
    existing_columns = list(pd.read_csv(OUTPUT_FILE, nrows=0).columns)
    if existing_columns != list(new_data.columns):
        raise ValueError(
            "Existing anomaly result columns do not match the current output schema; "
            "refusing to alter historical results."
        )
    new_data.to_csv(OUTPUT_FILE, mode="a", header=False, index=False)
else:
    new_data.to_csv(OUTPUT_FILE, index=False)

# Display summary
normal_count = (new_data["status"] == "Normal").sum()
anomaly_count = (new_data["status"] == "Anomaly").sum()

print("\n========== SDP AI ANOMALY DETECTION ==========")

print("New readings analyzed:", len(new_data))
print("New readings classified normal:", normal_count)
print("New anomalies detected:", anomaly_count)

print("\nLatest readings:")

print(
    new_data[
        ["cpu_usage", "memory_usage", "status"]
    ].tail(10).to_string(index=False)
)

print("\nResults saved to:", OUTPUT_FILE)
