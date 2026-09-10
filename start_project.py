"""
Healthcare NL-to-Test-Case Generation Agent - Development Startup Launcher

Single-command startup for both Backend (FastAPI) and Frontend (Vite) servers.
Usage:
    python start_project.py
"""

import os
import sys
import time
import json
import socket
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"

# Virtualenv Python and Node Paths
BACKEND_PYTHON = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
DEFAULT_NODE_DIR = Path(r"D:\Tools\node-v26.5.0-win-x64\node-v26.5.0-win-x64")
DEFAULT_NPM_CMD = DEFAULT_NODE_DIR / "npm.cmd"
EXPECTED_APP_NAME = "Healthcare NL-to-Test-Case Generation Agent"


def validate_environment() -> tuple[Path, Path, Path]:
    """
    Validates required directories and executables before starting services.
    Returns (backend_python, node_dir, npm_cmd).
    """
    errors = []

    # 1. Validate Backend Directory
    if not BACKEND_DIR.is_dir():
        errors.append(f"ERROR: Backend directory not found: {BACKEND_DIR}")

    # 2. Validate Frontend Directory
    if not FRONTEND_DIR.is_dir():
        errors.append(f"ERROR: Frontend directory not found: {FRONTEND_DIR}")

    # 3. Validate Backend Python
    if not BACKEND_PYTHON.is_file():
        errors.append(
            f"ERROR: Backend virtual environment not found:\n"
            f"  Expected: {BACKEND_PYTHON}\n"
            f"  Please ensure backend\\venv is created and configured."
        )

    # 4. Validate Node and NPM
    node_dir = DEFAULT_NODE_DIR
    npm_cmd = DEFAULT_NPM_CMD

    if not npm_cmd.is_file():
        # Fallback check in PATH
        fallback_npm = shutil.which("npm.cmd") or shutil.which("npm")
        if fallback_npm:
            npm_cmd = Path(fallback_npm)
            node_dir = npm_cmd.parent
        else:
            errors.append(
                f"ERROR: Node/NPM executable not found:\n"
                f"  Expected: {DEFAULT_NPM_CMD}\n"
                f"  Please verify Node installation at {DEFAULT_NODE_DIR} or in system PATH."
            )

    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)

    return BACKEND_PYTHON, node_dir, npm_cmd


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a TCP port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def check_backend_health(url: str = "http://localhost:8000/health", timeout_sec: float = 6.0) -> tuple[bool, str]:
    """
    Polls backend health check endpoint and verifies it is the Healthcare agent backend.
    """
    start_time = time.time()
    last_detail = "Initializing"
    while time.time() - start_time < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    raw = resp.read().decode()
                    try:
                        data = json.loads(raw)
                        app_name = data.get("app")
                        if app_name == EXPECTED_APP_NAME:
                            return True, "OK"
                        else:
                            return False, f"Port 8000 is occupied by another application ({app_name or 'unknown'}). Please stop other servers on port 8000."
                    except Exception:
                        return False, "Port 8000 returned non-JSON response from a different server."
        except Exception as e:
            last_detail = str(e)
            time.sleep(0.5)
    return False, f"Initializing (check the Backend console for logs: {last_detail})"


def main():
    print("=" * 60)
    print("Healthcare NL-to-Test-Case Generation Agent")
    print("=" * 60)

    # Step 1: Validate environment
    backend_python, node_dir, npm_cmd = validate_environment()

    # Pre-check: Check if port 8000 is already in use by another app
    if is_port_in_use(8000):
        # Check who is listening
        is_healthy, msg = check_backend_health("http://localhost:8000/health", timeout_sec=1.0)
        if not is_healthy and "occupied by another application" in msg:
            print(f"[!] WARNING: {msg}\n", file=sys.stderr)

    # Step 2: Prepare environments
    backend_env = os.environ.copy()
    frontend_env = os.environ.copy()
    if node_dir.is_dir():
        backend_env["PATH"] = str(node_dir) + os.pathsep + backend_env.get("PATH", "")
        frontend_env["PATH"] = str(node_dir) + os.pathsep + frontend_env.get("PATH", "")

    # Step 3: Start Backend Process
    # Equivalent to: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 in backend dir
    backend_title = "Healthcare Agent - Backend (FastAPI :8000)"
    backend_cmd = (
        f'title {backend_title} && '
        f'"{backend_python}" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000'
    )

    try:
        subprocess.Popen(
            f'cmd.exe /k "{backend_cmd}"',
            cwd=str(BACKEND_DIR),
            env=backend_env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            shell=True if os.name != "nt" else False,
        )
        print("[+] Backend server launched in separate console window.")
    except Exception as e:
        print(f"ERROR: Backend startup failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 4: Start Frontend Process
    # Equivalent to: npm.cmd run dev in frontend dir
    frontend_title = "Healthcare Agent - Frontend (Vite :5173)"
    frontend_cmd = (
        f'title {frontend_title} && '
        f'"{npm_cmd}" run dev'
    )

    try:
        subprocess.Popen(
            f'cmd.exe /k "{frontend_cmd}"',
            cwd=str(FRONTEND_DIR),
            env=frontend_env,
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
            shell=True if os.name != "nt" else False,
        )
        print("[+] Frontend server launched in separate console window.")
    except Exception as e:
        print(f"ERROR: Frontend startup failed: {e}", file=sys.stderr)
        sys.exit(1)

    print()
    print("Backend : http://localhost:8000")
    print("Health  : http://localhost:8000/health")
    print("Swagger : http://localhost:8000/docs")
    print("Frontend: http://localhost:5173")
    print("=" * 60)

    # Step 5: Health check diagnostic
    is_ok, health_msg = check_backend_health("http://localhost:8000/health", timeout_sec=8.0)
    print(f"Backend health: {health_msg}")
    print("=" * 60)


if __name__ == "__main__":
    main()
