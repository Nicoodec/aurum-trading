import subprocess, sys, os, time
from datetime import datetime

LOG = r"C:\Users\nicod\aurum-trading\logs\daemon_service.log"
os.makedirs(os.path.dirname(LOG), exist_ok=True)

def log(msg):
    line = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

log("AURUM service_runner starting...")

while True:
    log("Starting daemon.py...")
    try:
        proc = subprocess.Popen(
            [sys.executable, r"C:\Users\nicod\aurum-trading\daemon.py"],
            cwd=r"C:\Users\nicod\aurum-trading",
            stdout=open(r"C:\Users\nicod\aurum-trading\logs\daemon_stdout.log", "a", encoding="utf-8"),
            stderr=open(r"C:\Users\nicod\aurum-trading\logs\daemon_stderr.log", "a", encoding="utf-8"),
        )
        log("daemon.py PID=" + str(proc.pid))
        proc.wait()
        log("daemon.py exited with code " + str(proc.returncode))
    except Exception as e:
        log("Error: " + str(e))
    log("Restarting in 30 seconds...")
    time.sleep(30)
