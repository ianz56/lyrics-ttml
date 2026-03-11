import subprocess
import platform
import sys
from datetime import datetime

def run_command(cmd, exit_on_error=True):
    try:
        # shell=True to run on Windows (CMD/Powershell) and Linux (Bash)
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error while running: {cmd}")
        if exit_on_error:
            print("🛑 Stopping process due to error...")
            sys.exit(1)
        return False

print(f"--- Starting Auto Sync on {platform.system()} ---")

run_command("git pull")
run_command("python lint_ttml.py --all --fix")
run_command("python ttml_to_json.py --all")

# Check if there are any changes to commit
status_check = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)

if not status_check.stdout.strip():
    print("✅ No changes to sync.")
else:
    run_command("git add .")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    run_command(f'git commit -m "ttml: auto sync {timestamp}"')
    run_command("git push origin main")
    print("✅ Push successful!")

print("--- Done! ---")
