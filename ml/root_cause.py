
import pandas as pd
import psutil
from pathlib import Path
from datetime import datetime


def active_test_workloads():
    workloads = []

    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command_line = " ".join(process.info["cmdline"] or [])
            if "AIOPS_CPU_SECONDS:" in command_line:
                kind = "CPU"
            elif "AIOPS_MEMORY_RSS_MIB:" in command_line:
                kind = "Memory"
            else:
                continue

            workloads.append(
                {
                    "kind": kind,
                    "pid": process.info["pid"],
                    "cpu_percent": process.cpu_percent(interval=0.1),
                    "memory_mib": process.memory_info().rss / (1024 * 1024),
                }
            )
        except (
            psutil.AccessDenied,
            psutil.NoSuchProcess,
            psutil.ZombieProcess,
            OSError,
        ):
            continue

    return workloads


# --------------------------------------------------
# 1. PROJECT PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

METRICS_FILE = BASE_DIR / "data" / "metrics.csv"
ANOMALY_FILE = BASE_DIR / "data" / "anomaly_results.csv"
INCIDENT_FILE = BASE_DIR / "data" / "incident_reports.csv"

# --------------------------------------------------
# 2. CHECK FILES
# --------------------------------------------------

if not METRICS_FILE.exists():
    raise FileNotFoundError("Metrics file not found.")

# --------------------------------------------------
# 3. LOAD DATA
# --------------------------------------------------

metrics = pd.read_csv(METRICS_FILE)
anomalies = pd.read_csv(ANOMALY_FILE) if ANOMALY_FILE.exists() else pd.DataFrame()

if metrics.empty:
    raise ValueError("No monitoring data available.")

required_metric_columns = {
    "timestamp",
    "cpu_usage",
    "memory_usage",
    "application_status",
}
missing_metric_columns = required_metric_columns.difference(metrics.columns)
if missing_metric_columns:
    raise ValueError(
        "Metrics file is missing required columns: "
        + ", ".join(sorted(missing_metric_columns))
    )

latest = metrics.iloc[-1]
source_timestamp = str(latest["timestamp"])

ai_status = "Unavailable"
if not anomalies.empty:
    if not {"timestamp", "status"}.issubset(anomalies.columns):
        raise ValueError(
            "Anomaly results must contain timestamp and status columns."
        )
    matching_ai = anomalies[
        anomalies["timestamp"].astype(str).eq(source_timestamp)
    ]
    if not matching_ai.empty:
        ai_status = str(matching_ai.iloc[-1]["status"])

active_workloads = active_test_workloads()
# --------------------------------------------------
# 4. AVOID DUPLICATE REPORTS
# --------------------------------------------------

if INCIDENT_FILE.exists():
    existing = pd.read_csv(INCIDENT_FILE)

    if not existing.empty and "source_timestamp" in existing.columns:
        same_source = existing["source_timestamp"].astype(str).eq(source_timestamp)
        already_reported_workloads = (
            not active_workloads
            or (
                "root_cause" in existing.columns
                and any(
                    all(
                        f"PID {workload['pid']}" in str(root_cause)
                        for workload in active_workloads
                    )
                    for root_cause in existing.loc[same_source, "root_cause"]
                )
            )
        )
        if same_source.any() and already_reported_workloads:
            print("RCA already completed for this reading and active workload.")
            raise SystemExit(0)

# --------------------------------------------------
# 5. GET MATCHED METRICS AND AI RESULT
# --------------------------------------------------

cpu = float(latest["cpu_usage"])
memory = float(latest["memory_usage"])
app_status = str(latest["application_status"])


# --------------------------------------------------
# 6. ROOT CAUSE ANALYSIS
# --------------------------------------------------

possible_causes = []
recommended_actions = []

if app_status.lower() == "unreachable":
    possible_causes.append("Application is unreachable")
    recommended_actions.append(
        "Check whether the Flask application is running."
    )

if cpu > 85:
    possible_causes.append("High CPU utilization")
    recommended_actions.append(
        "Identify CPU-intensive processes."
    )

if memory > 90:
    possible_causes.append("High memory utilization")
    recommended_actions.append(
        "Identify memory-intensive processes and check available RAM."
    )

for workload in active_workloads:
    if workload["kind"] == "CPU":
        possible_causes.append(
            "Active CPU test workload detected "
            f"(PID {workload['pid']}; {workload['cpu_percent']:.1f}% of one CPU core)"
        )
        recommended_actions.append(
            "Review the active CPU test workload and compare its process usage "
            "with the system CPU reading."
        )
    else:
        possible_causes.append(
            "Active memory test workload detected "
            f"(PID {workload['pid']}; {workload['memory_mib']:.1f} MiB resident memory)"
        )
        recommended_actions.append(
            "Review the active memory test workload and available system memory."
        )

if cpu > 85 and memory > 90:
    possible_causes.append("Possible system resource exhaustion")

if ai_status == "Anomaly" and not possible_causes:
    possible_causes.append(
        "Unusual system behaviour detected by AI"
    )
    recommended_actions.append(
        "Inspect recent CPU, memory and application health readings."
    )

if not possible_causes:
    possible_causes.append("No major issue identified")
    recommended_actions.append(
        "Continue monitoring system performance."
    )

# --------------------------------------------------
# 7. INCIDENT SEVERITY
# --------------------------------------------------

if (
    app_status.lower() == "unreachable"
    or cpu > 95
    or memory > 95
):
    severity = "Critical"

elif (
    cpu > 85
    or memory > 90
    or ai_status == "Anomaly"
    or active_workloads
):
    severity = "Warning"

else:
    severity = "Normal"

# --------------------------------------------------
# 8. CREATE INCIDENT REPORT
# --------------------------------------------------

report = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "source_timestamp": source_timestamp,
    "cpu_usage": cpu,
    "memory_usage": memory,
    "application_status": app_status,
    "ai_status": ai_status,
    "severity": severity,
    "root_cause": "; ".join(possible_causes),
    "recommended_action": "; ".join(recommended_actions)
}

report_df = pd.DataFrame([report])

# --------------------------------------------------
# 9. SAVE REPORT
# --------------------------------------------------

if INCIDENT_FILE.exists():
    report_df.to_csv(
        INCIDENT_FILE,
        mode="a",
        header=False,
        index=False
    )
else:
    report_df.to_csv(INCIDENT_FILE, index=False)

# --------------------------------------------------
# 10. DISPLAY RESULTS
# --------------------------------------------------

print("\n========== SDP ROOT CAUSE ANALYSIS ==========")
print("Source Timestamp:", source_timestamp)
print("CPU Usage:", cpu, "%")
print("Memory Usage:", memory, "%")
print("Application Status:", app_status)
print("Matched AI Detection:", ai_status)
print("Incident Severity:", severity)

print("\nPossible Root Cause:")
for cause in possible_causes:
    print("-", cause)

print("\nRecommended Actions:")
for action in recommended_actions:
    print("-", action)

print("\nIncident report saved to:")
print(INCIDENT_FILE)
