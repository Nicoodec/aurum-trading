# utils/github_sync.py
import subprocess, os

def sync(message='AURUM cycle update'):
    try:
        subprocess.run(['git', 'add', '-A'], check=True)
        subprocess.run(['git', 'commit', '-m', message], check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True)
        print('[SYNC] GitHub push OK')
    except subprocess.CalledProcessError as e:
        print(f'[SYNC] Git error: {e}')
