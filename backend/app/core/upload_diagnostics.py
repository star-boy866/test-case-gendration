"""
Safe diagnostic logging helper for tracking document upload lifecycle.
Logs worker PID, RSS memory, subprocess count, and elapsed time across:
- UPLOAD_RECEIVED
- DOCX_PARSE
- PDF_CONVERT (LibreOffice start/end/exit code)
- SEMANTIC_RESOLUTION
- SNAPSHOT_RENDER (pypdfium2 start/end/dimensions)
- GOVERNANCE_PERSIST
- RESPONSE
Never logs secrets or sensitive payloads.
"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger("upload_lifecycle")


def get_worker_pid() -> int:
    """Returns current worker process PID."""
    return os.getpid()


def get_rss_mb() -> float:
    """
    Returns current process Resident Set Size (RSS) in MB across Windows and Linux.
    Never throws an exception.
    """
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
        else:
            # Linux (/proc/self/status)
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            return round(int(parts[1]) / 1024, 2)
            except Exception:
                import resource
                return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)
    except Exception:
        pass
    return 0.0


def get_active_subprocess_count() -> int:
    """Estimates active child tasks / threads / subprocesses where practical."""
    try:
        if os.name != "nt":
            task_dir = Path(f"/proc/{os.getpid()}/task")
            if task_dir.exists():
                return len(list(task_dir.iterdir()))
    except Exception:
        pass
    return 0


def log_upload_lifecycle(
    stage: str,
    request_id: str,
    run_id: Optional[Any] = None,
    document_size_bytes: Optional[int] = None,
    start_time: Optional[float] = None,
    extra_details: Optional[dict] = None,
):
    """
    Format and emit structured diagnostic log for UPLOAD_LIFECYCLE.
    Never throws.
    """
    try:
        pid = get_worker_pid()
        rss = get_rss_mb()
        children = get_active_subprocess_count()
        now_iso = datetime.now(timezone.utc).isoformat()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2) if start_time else 0.0

        parts = [
            f"[UPLOAD_LIFECYCLE] stage={stage}",
            f"request_id={request_id}",
            f"run_id={run_id or 'N/A'}",
            f"document_size_bytes={document_size_bytes or 'N/A'}",
            f"worker_pid={pid}",
            f"rss_memory_mb={rss}",
            f"active_subprocesses={children}",
            f"elapsed_ms={elapsed_ms}",
            f"timestamp={now_iso}",
        ]
        if extra_details:
            for k, v in extra_details.items():
                parts.append(f"{k}={v}")

        log_str = " | ".join(parts)
        print(log_str, flush=True)
        logger.info(log_str)
    except Exception as ex:
        logger.warning(f"Error emitting upload lifecycle log: {ex}")
