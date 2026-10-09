"""Fictional worker for the Windows job cleanup test; no browser/network/data."""

import json
import subprocess
import sys


for line in sys.stdin:
    request = json.loads(line)
    if request["action"] == "open":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        print(json.dumps({"id":request["id"], "action":"open", "ok": True, "data": {"child_pid": child.pid}}), flush=True)
    # Deliberately ignore close to verify bounded process-tree cleanup.
