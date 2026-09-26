import os
import json

history_dir = os.path.expandvars(r"%APPDATA%\Code\User\History")

for root, dirs, files in os.walk(history_dir):
    if "entries.json" in files:
        entries_path = os.path.join(root, "entries.json")
        try:
            with open(entries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                resource = data.get("resource", "")
                if "5_Job_Aggregator.py" in resource or "app.py" in resource:
                    print(f"Found match: {resource} in {root}")
        except Exception:
            pass
