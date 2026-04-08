import subprocess

def sync(message="AURUM cycle update"):
    try:
        r1 = subprocess.run(["git", "add", "-A"], capture_output=True, text=True)
        r2 = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        if "nothing to commit" in r2.stdout + r2.stderr:
            print("[SYNC] Nothing to commit")
            return
        r3 = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if r3.returncode == 0:
            print("[SYNC] GitHub push OK")
        else:
            print("[SYNC] Push failed:", r3.stderr[:200])
            print("[SYNC] Trying force push...")
            r4 = subprocess.run(["git", "push", "origin", "main", "--force"], capture_output=True, text=True)
            if r4.returncode == 0:
                print("[SYNC] Force push OK")
            else:
                print("[SYNC] Force push also failed:", r4.stderr[:100])
    except Exception as e:
        print("[SYNC] Error:", e)
