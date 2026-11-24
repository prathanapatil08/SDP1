
import streamlit as st
import pandas as pd
import psutil
import time
from pathlib import Path
from streamlit_autorefresh import st_autorefresh

# --------------------------------------------------
# 1. PROJECT FILE PATHS
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

METRICS_FILE = BASE_DIR / "data" / "metrics.csv"
ANOMALY_FILE = BASE_DIR / "data" / "anomaly_results.csv"
INCIDENT_FILE = BASE_DIR / "data" / "incident_reports.csv"

SELF_HEALING_LOG = BASE_DIR / "logs" / "self_healing_log.csv"
CPU_ALERT_THRESHOLD = 85
MEMORY_ALERT_THRESHOLD = 90


def active_test_workloads():
    now = time.monotonic()
    previous_samples = st.session_state.get("test_workload_cpu_samples", {})
    current_samples = {}
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

            cpu_times = process.cpu_times()
            cpu_seconds = cpu_times.user + cpu_times.system
            previous = previous_samples.get(process.pid)
            cpu_percent = None
            if previous is not None and now > previous[1]:
                cpu_percent = max(
                    0.0,
                    (cpu_seconds - previous[0]) / (now - previous[1]) * 100,
                )
            current_samples[process.pid] = (cpu_seconds, now)
            workloads.append(
                {
                    "kind": kind,
                    "pid": process.pid,
                    "cpu_percent": cpu_percent,
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

    st.session_state.test_workload_cpu_samples = current_samples
    return workloads


# --------------------------------------------------
# 2. PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="SDP - Intelligent AIOps Platform",
    page_icon="🤖",
    layout="wide"
)


# --------------------------------------------------
# 3. AUTOMATIC REFRESH
# --------------------------------------------------

st_autorefresh(
    interval=5000,
    key="dashboard_refresh"
)


# --------------------------------------------------
# 4. DASHBOARD TITLE
# --------------------------------------------------

st.title("🤖 Intelligent AIOps Platform")

st.markdown(
    "### Automated Cloud Incident Detection, "
    "Root Cause Analysis and Self-Healing"
)

st.caption("System Monitoring | Machine Learning | Anomaly Detection")

st.divider()


# --------------------------------------------------
# 5. CHECK METRICS FILE
# --------------------------------------------------

if not METRICS_FILE.exists():

    st.error("Metrics file not found!")

    st.info(
        "Please start the monitoring program using: "
        "python app/monitor.py"
    )

    st.stop()


# --------------------------------------------------
# 6. LOAD EXISTING AI AND INCIDENT RESULTS
# --------------------------------------------------

st.subheader("🧠 AI Anomaly Detection")
st.caption(
    "This dashboard reads existing AI/RCA results without rerunning scripts or "
    "modifying their history. Run detection and RCA from the separate testing control panel."
)


# --------------------------------------------------
# 9. LOAD MONITORING DATA
# --------------------------------------------------

try:

    metrics = pd.read_csv(METRICS_FILE)

    if metrics.empty:
        st.warning("No monitoring data available.")
        st.stop()

except Exception as e:
    st.error(f"Unable to read metrics file: {e}")
    st.stop()


# --------------------------------------------------
# 10. LOAD AI RESULTS
# --------------------------------------------------

try:

    if ANOMALY_FILE.exists():
        anomalies = pd.read_csv(ANOMALY_FILE)
    else:
        anomalies = pd.DataFrame()

except Exception as e:
    st.error(f"Unable to read anomaly results: {e}")
    anomalies = pd.DataFrame()


# --------------------------------------------------
# 11. DATA PREPROCESSING
# --------------------------------------------------

required_columns = [
    "timestamp",
    "cpu_usage",
    "memory_usage",
    "application_status"
]

missing_columns = [
    column for column in required_columns
    if column not in metrics.columns
]

if missing_columns:
    st.error(
        "Missing columns in metrics.csv: "
        + ", ".join(missing_columns)
    )
    st.stop()


metrics["cpu_usage"] = pd.to_numeric(
    metrics["cpu_usage"],
    errors="coerce"
)

metrics["memory_usage"] = pd.to_numeric(
    metrics["memory_usage"],
    errors="coerce"
)

metrics = metrics.dropna(
    subset=["cpu_usage", "memory_usage"]
)

if metrics.empty:
    st.warning("No valid monitoring readings found.")
    st.stop()


# --------------------------------------------------
# 12. LATEST SYSTEM READINGS
# --------------------------------------------------

latest = metrics.iloc[-1]

cpu = latest["cpu_usage"]
memory = latest["memory_usage"]
app_status = latest["application_status"]


# --------------------------------------------------
# 13. SYSTEM OVERVIEW
# --------------------------------------------------

st.subheader("📊 System Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("CPU Usage", f"{cpu:.1f}%")
c2.metric("Memory Usage", f"{memory:.1f}%")
c3.metric("Application Status", str(app_status))
c4.metric("Total Readings", len(metrics))
latest_timestamp = str(latest["timestamp"])
st.caption(f"Latest monitoring reading: {latest_timestamp}")
parsed_timestamp = pd.to_datetime(latest_timestamp, errors="coerce")
if pd.isna(parsed_timestamp):
    st.warning("The timestamp on the latest monitoring reading is invalid.")
else:
    reading_age_seconds = max(
        0,
        (pd.Timestamp.now() - parsed_timestamp).total_seconds(),
    )
    if reading_age_seconds > 15:
        st.warning(
            f"Monitoring data is stale: latest reading is "
            f"{reading_age_seconds:.0f} seconds old."
        )

st.markdown("**Rule-based resource alerts** (separate from Isolation Forest predictions)")
threshold_alerts = []
if cpu > CPU_ALERT_THRESHOLD:
    threshold_alerts.append(
        f"CPU threshold exceeded: {cpu:.1f}% > {CPU_ALERT_THRESHOLD}%."
    )
if memory > MEMORY_ALERT_THRESHOLD:
    threshold_alerts.append(
        f"Memory threshold exceeded: {memory:.1f}% > {MEMORY_ALERT_THRESHOLD}%."
    )
if threshold_alerts:
    for alert in threshold_alerts:
        st.warning(alert)
else:
    st.success(
        f"No resource threshold alert (CPU > {CPU_ALERT_THRESHOLD}%, "
        f"memory > {MEMORY_ALERT_THRESHOLD}%)."
    )

st.markdown("**Live workload detection** (actual worker processes; separate from threshold alerts)")
active_workloads = active_test_workloads()
if active_workloads:
    for workload in active_workloads:
        if workload["kind"] == "CPU":
            process_cpu = workload["cpu_percent"]
            cpu_detail = (
                f"{process_cpu:.1f}% of one CPU core"
                if process_cpu is not None
                else "sampling process CPU"
            )
            st.warning(
                f"CPU test process detected (PID {workload['pid']}): {cpu_detail}; "
                f"system CPU from metrics.csv is {cpu:.1f}%."
            )
        else:
            st.warning(
                f"Memory test process detected (PID {workload['pid']}): "
                f"{workload['memory_mib']:.1f} MiB resident memory; "
                f"system memory from metrics.csv is {memory:.1f}%."
            )
else:
    st.caption("No active CPU or memory test worker process detected.")


# --------------------------------------------------
# 14. PERFORMANCE CHARTS
# --------------------------------------------------

st.divider()
st.subheader("📈 System Performance")

left, right = st.columns(2)
chart_metrics = metrics.tail(120).set_index("timestamp")

with left:
    st.write("CPU Usage Over Time")
    st.line_chart(
        chart_metrics["cpu_usage"]
    )

with right:
    st.write("Memory Usage Over Time")
    st.line_chart(
        chart_metrics["memory_usage"]
    )


# --------------------------------------------------
# 15. AI ANOMALY SUMMARY
# --------------------------------------------------

st.divider()
st.subheader("🚨 Anomaly Detection Results")

if not anomalies.empty and "status" in anomalies.columns:

    anomaly_count = (
        anomalies["status"] == "Anomaly"
    ).sum()

    normal_count = (
        anomalies["status"] == "Normal"
    ).sum()

    a1, a2, a3 = st.columns(3)

    a1.metric("Total Analysed", len(anomalies))
    a2.metric("Normal Readings", int(normal_count))
    a3.metric("Anomalies Detected", int(anomaly_count))

    st.write("Latest AI Detection Results")

    st.dataframe(
        anomalies.tail(20).iloc[::-1],
        use_container_width=True
    )

else:
    st.warning(
        "AI results are not available. "
        "Check the AI detection script."
    )


# --------------------------------------------------
# 16. ROOT CAUSE ANALYSIS
# --------------------------------------------------

st.divider()
st.subheader("🔍 Root Cause Analysis")

st.caption(
    "Live analysis uses the latest monitoring reading and active CPU/memory "
    "test workers; this section refreshes every 5 seconds."
)
st.caption(f"Incident source reading: {latest_timestamp}")

live_causes = []
live_recommendations = []
if str(app_status).lower() == "unreachable":
    live_causes.append("Flask application is unreachable")
    live_recommendations.append(
        "Check the Flask application and its recovery status."
    )
if cpu > CPU_ALERT_THRESHOLD:
    live_causes.append(
        f"High system CPU utilization ({cpu:.1f}% > {CPU_ALERT_THRESHOLD}%)"
    )
    live_recommendations.append(
        "Inspect active CPU processes and reduce load if needed."
    )
if memory > MEMORY_ALERT_THRESHOLD:
    live_causes.append(
        f"High system memory utilization ({memory:.1f}% > {MEMORY_ALERT_THRESHOLD}%)"
    )
    live_recommendations.append(
        "Inspect memory-consuming processes and available system memory."
    )
for workload in active_workloads:
    if workload["kind"] == "CPU":
        process_cpu = workload["cpu_percent"]
        cpu_detail = (
            f"{process_cpu:.1f}% of one CPU core"
            if process_cpu is not None
            else "CPU usage is being sampled"
        )
        live_causes.append(
            f"Active CPU test load detected (PID {workload['pid']}; {cpu_detail})"
        )
        live_recommendations.append(
            "Stop the CPU test load when the demonstration is complete."
        )
    else:
        live_causes.append(
            "Active memory test load detected "
            f"(PID {workload['pid']}; {workload['memory_mib']:.1f} MiB resident)"
        )
        live_recommendations.append(
            "Stop the memory test load when the demonstration is complete."
        )

if str(app_status).lower() == "unreachable" or cpu > 95 or memory > 95:
    live_severity = "Critical"
elif live_causes:
    live_severity = "Warning"
else:
    live_severity = "Normal"

if live_severity == "Critical":
    st.error("🚨 Critical Incident")
elif live_severity == "Warning":
    st.warning("⚠️ Warning Detected")
else:
    st.success("✅ System Normal")

r1, r2, r3 = st.columns(3)
r1.metric("CPU Usage", f"{cpu:.1f}%")
r2.metric("Memory Usage", f"{memory:.1f}%")
r3.metric("Severity", live_severity)

st.markdown("### Possible Root Cause")
if live_causes:
    for cause in live_causes:
        st.write(f"- {cause}")
else:
    st.write("No major issue identified")

st.markdown("### Recommended Action")
if live_recommendations:
    for recommendation in live_recommendations:
        st.info(recommendation)
else:
    st.info("Continue monitoring system performance.")

if INCIDENT_FILE.exists():
    try:
        incidents = pd.read_csv(INCIDENT_FILE)
        if not incidents.empty:
            with st.expander("Saved incident history"):
                st.dataframe(
                    incidents.tail(20).iloc[::-1],
                    use_container_width=True,
                )
    except (OSError, UnicodeError, pd.errors.ParserError) as error:
        st.error(f"Unable to load saved incident history: {error}")


# --------------------------------------------------
# 17. SELF-HEALING ACTIVITY HISTORY
# --------------------------------------------------

st.divider()
st.subheader("🛠️ Self-Healing Activity History")

if SELF_HEALING_LOG.exists():

    try:

        healing_logs = pd.read_csv(SELF_HEALING_LOG)

        if not healing_logs.empty:

            total_attempts = len(
                healing_logs[
                    healing_logs["action"].str.contains(
                        "Start Flask application|Recovery attempted",
                        case=False,
                        na=False
                    )
                ]
            )

            successful_recoveries = len(
                healing_logs[
                    healing_logs["result"].str.contains(
                        "Recovery successful",
                        case=False,
                        na=False
                    )
                ]
            )

            h1, h2, h3 = st.columns(3)

            h1.metric(
                "Logged Recovery Attempts",
                total_attempts
            )

            h2.metric(
                "Successful Recoveries",
                successful_recoveries
            )

            h3.metric(
                "Total Activity Records",
                len(healing_logs)
            )

            st.markdown("### Recent Self-Healing Activities")

            st.dataframe(
                healing_logs.tail(20).iloc[::-1],
                use_container_width=True
            )

        else:
            st.info("No self-healing activities recorded yet.")

    except Exception as e:
        st.error(f"Unable to load self-healing log: {e}")

else:
    st.info(
        "Self-healing log is not available yet. "
        "Run the self-healing script to create it."
    )


# --------------------------------------------------
# 18. RECENT MONITORING RECORDS
# --------------------------------------------------

st.divider()
st.subheader("📋 Recent Monitoring Records")

st.dataframe(
    metrics.tail(20).iloc[::-1],
    use_container_width=True
)


# --------------------------------------------------
# 19. SYSTEM INFORMATION
# --------------------------------------------------

st.divider()
st.subheader("⚙️ Dashboard Information")

st.write("Monitoring interval: 5 seconds")
st.write("Dashboard refresh interval: 5 seconds")
st.write("AI algorithm: Isolation Forest")
st.write("Data source: metrics.csv")
st.write("AI output: anomaly_results.csv")
st.write("AI detection and Root Cause Analysis: Run from the Testing Control Panel")
st.write("Self-healing: Runs automatically after the Flask stop test")

st.caption(
    "SDP | Intelligent AIOps Platform | Final Year Project"
)
