import os
import json
import glob

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")
target_files = [
    "1_Dashboard.py",
    "2_Profile.py",
    "4_Session_Manager.py",
    "5_Job_Aggregator.py",
    "6_Platforms.py",
    "app.py"
]

found_backups = {}

for root, dirs, files in os.walk(history_dir):
    if "entries.json" in files:
        entries_path = os.path.join(root, "entries.json")
        try:
            with open(entries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                resource = data.get("resource", "")
                
                # Check if this history folder belongs to one of our lost files
                for target in target_files:
                    if target in resource and "Aoto_Job_agent" in resource:
                        if target not in found_backups:
                            found_backups[target] = []
                        
                        # Add all backup entries in this folder
                        for entry in data.get("entries", []):
                            entry_id = entry.get("id")
                            timestamp = entry.get("timestamp")
                            if entry_id:
                                backup_file = os.path.join(root, entry_id)
                                found_backups[target].append({
                                    "backup_file": backup_file,
                                    "timestamp": timestamp,
                                    "original_path": resource
                                })
        except Exception as e:
            pass

# Print the results, sorted by timestamp (newest first)
if not found_backups:
    print("NO BACKUPS FOUND IN VS CODE HISTORY.")
else:
    for target, backups in found_backups.items():
        print(f"\n--- Backups for {target} ---")
        # Sort descending by timestamp
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        for b in backups[:5]: # Show top 5 newest
            print(f"File: {b['backup_file']} | Time: {b['timestamp']}")
