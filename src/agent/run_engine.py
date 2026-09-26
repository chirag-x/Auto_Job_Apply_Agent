import asyncio
import sys
import os
import sqlite3
import subprocess

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from src.core.db import get_db_connection

def main():
    print("Starting Background Execution Engine...", flush=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_applications WHERE status = 'approved' ORDER BY match_score DESC")
        approved_jobs = [dict(row) for row in cursor.fetchall()]
        
    if not approved_jobs:
        print("No approved jobs found in the queue. Exiting.", flush=True)
        return
        
    print(f"Found {len(approved_jobs)} approved jobs to process.", flush=True)
    
    RUNNER_MAP = {
        "linkedin":    "src/agent/hybrid_runner.py",
        "naukri":      "src/agent/naukri_runner.py",
        "internshala": "src/agent/internshala_runner.py",
        "wellfound":   "src/agent/wellfound_runner.py",
        "indeed":      "src/agent/indeed_runner.py",
    }
    
    for i, job in enumerate(approved_jobs):
        job_id   = job['id']
        job_url  = job['job_url']
        platform = job['platform']
        title    = job['job_title']
        company  = job['company']
        
        print(f"\n[{i+1}/{len(approved_jobs)}] Launching {platform} bot for: {title} at {company}", flush=True)
        
        runner = RUNNER_MAP.get(platform)
        if runner and os.path.exists(runner):
            cmd = [sys.executable, runner, "--url", job_url]
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"
                
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    env=env
                )
                
                full_output = []
                for line in iter(process.stdout.readline, ''):
                    print(line.strip(), flush=True)
                    full_output.append(line.strip())
                    
                process.wait()
                
                logs = "\n".join(full_output)
                if "Application submitted successfully!" in logs:
                    new_status = "applied"
                    print(f"\n--- Successfully marked job {job_id} as APPLIED in database ---", flush=True)
                else:
                    new_status = "failed"
                    print(f"\n--- Job {job_id} failed. Marked as FAILED in database ---", flush=True)
                    
                with get_db_connection() as conn:
                    conn.cursor().execute("UPDATE job_applications SET status=?, logs=? WHERE id=?", (new_status, logs, job_id))
                    conn.commit()
                    
            except Exception as e:
                print(f"Error running bot: {e}", flush=True)
                with get_db_connection() as conn:
                    conn.cursor().execute("UPDATE job_applications SET status='failed', logs=? WHERE id=?", (str(e), job_id))
                    conn.commit()
        else:
            print(f"Platform '{platform}' not yet supported. Skipping.", flush=True)
            with get_db_connection() as conn:
                conn.cursor().execute("UPDATE job_applications SET status='skipped', logs='Platform unsupported' WHERE id=?", (job_id,))
                conn.commit()

    print("\nALL DONE. Queue is empty.", flush=True)

if __name__ == "__main__":
    main()
