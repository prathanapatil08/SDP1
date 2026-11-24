
import csv
import time
import psutil
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

# Find the main SDP project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# CSV file location
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CSV_FILE = DATA_DIR / "metrics.csv"

# Check whether our Flask application is running
def check_application():

    try:
        with urlopen("http://127.0.0.1:5000/health", timeout=2) as response:
            if response.status == 200:
                return "Healthy"

    except (URLError, TimeoutError, OSError):
        return "Unreachable"

    return "Unreachable"


# Create CSV file with column headings
if not CSV_FILE.exists():
    with open(CSV_FILE, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "timestamp",
            "cpu_usage",
            "memory_usage",
            "available_memory_mb",
            "application_status"
        ])


print("SDP System Monitoring Started")
print("Collecting metrics every 5 seconds...")
print("Press CTRL + C to stop monitoring.\n")


try:

    while True:
        cycle_started = time.monotonic()

        # Collect CPU usage
        cpu = psutil.cpu_percent(interval=1)

        # Collect memory information
        memory = psutil.virtual_memory()

        memory_usage = memory.percent
        available_memory = round(memory.available / (1024 * 1024), 2)

        # Check application health
        app_status = check_application()

        # Current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save metrics in CSV
        with open(CSV_FILE, "a", newline="") as file:

            writer = csv.writer(file)

            writer.writerow([
                timestamp,
                cpu,
                memory_usage,
                available_memory,
                app_status
            ])

        # Display collected information
        print("--------------------------------")
        print("Time:", timestamp)
        print("CPU Usage:", cpu, "%")
        print("Memory Usage:", memory_usage, "%")
        print("Available Memory:", available_memory, "MB")
        print("Application:", app_status)

        time.sleep(max(0, 5 - (time.monotonic() - cycle_started)))


except KeyboardInterrupt:

    print("\nMonitoring stopped.")
    print("Metrics saved at:", CSV_FILE)
