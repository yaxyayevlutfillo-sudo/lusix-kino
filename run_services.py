import os
import subprocess
import signal
import sys
import time

web = subprocess.Popen([
    "gunicorn",
    "app:app",
    "--bind",
    f"0.0.0.0:{os.environ.get('PORT', '10000')}"
])

bot = subprocess.Popen([sys.executable, "bot.py"])

def stop_services(signum, frame):
    for process in (web, bot):
        if process.poll() is None:
            process.terminate()

    for process in (web, bot):
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

    sys.exit(0)

signal.signal(signal.SIGTERM, stop_services)
signal.signal(signal.SIGINT, stop_services)

while True:
    if web.poll() is not None or bot.poll() is not None:
        stop_services(signal.SIGTERM, None)

    time.sleep(1)
