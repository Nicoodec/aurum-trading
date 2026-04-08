import subprocess

def sync(message="AURUM cycle update"):
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        if "nothing to commit" in result.stdout + result.stderr:
            print("[SYNC] Nothing to commit")
            return
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        print("[SYNC] GitHub push OK")
    except subprocess.CalledProcessError as e:
        print("[SYNC] Git error:", e)
