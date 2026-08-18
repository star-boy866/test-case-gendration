import os
import sys
import psutil
import platform
import json
from pathlib import Path
from datetime import datetime, timezone

def capture_environment():
    env = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "os": platform.system(),
        "os_release": platform.release(),
        "python_version": platform.python_version(),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
        "sqlite_version": "Unknown",
        "backend_version": "1.0.0",
        "configuration": {
            "WAL_enabled": False, # baseline
            "LLM": "Ollama / local",
        }
    }
    
    try:
        import sqlite3
        env["sqlite_version"] = sqlite3.sqlite_version
    except Exception:
        pass
        
    out_file = Path("poc/load_benchmark/reports/load_benchmark_environment.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(env, f, indent=2)
        
    return env

if __name__ == "__main__":
    env = capture_environment()
    print(json.dumps(env, indent=2))
