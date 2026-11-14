
import subprocess
import sys
import time
import csv
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

BASE_DIR = Path(__file__).resolve().parent.parent
MAIN_FILE = BASE_DIR / "app" / "main.py"
LOG_FILE = BASE_DIR / "logs" / "self_healing_log.csv"

APP_URL = "http://127.0.0.1:5000/health"

app_process = None


def check_application():
    """Check whether the Flask application is responding."""
    try:
        with urlopen(APP_URL, timeout=3) as response:
            return response.status == 200
    except (URLError, TimeoutError, OSError):
        return False


def write_log(action, result):
    """Save recovery activity to a CSV file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_exists = LOG_FILE.exists()

    with open(LOG_FILE, "a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(["timestamp", "action", "result"])

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action,
            result
        ])


def restart_application():
    """Start Flask only if it is not already responding."""
    global app_process

    print("\nSelf-healing process started.")

    if check_application():
        print("Application is already healthy.")
        write_log("No recovery needed", "Application healthy")
        return

    print("Application is unreachable.")
    print("Attempting to start Flask application...")

    if app_process is not None and app_process.poll() is None:
        print("A Flask process is already running but not responding.")
        write_log(
            "Recovery attempted",
            "Existing managed process is unresponsive; no duplicate started"
        )
        return

    try:
        app_process = subprocess.Popen(
            [sys.executable, str(MAIN_FILE)],
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )

        # Give Flask time to start.
        for attempt in range(10):
            time.sleep(2)

            if check_application():
                print("Application recovered successfully!")
                write_log("Start Flask application", "Recovery successful")
                return

        print("Application did not recover.")
        write_log("Start Flask application", "Recovery failed")

    except Exception as error:
        print("Self-healing error:", error)
        write_log("Start Flask application", f"Error: {error}")


if __name__ == "__main__":
    restart_application()
