"""Configuration for the analysis worker.

Every setting comes from an environment variable with a safe default, so the same
image runs unchanged on a laptop, in docker compose and in production.
"""

import os
import tempfile


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _float_setting(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _list_setting(name: str, default: str) -> frozenset[str]:
    raw = os.getenv(name, default)
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


# --- Queue and API ---------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = _int_setting("REDIS_PORT", 6379)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
QUEUE_KEY = os.getenv("QUEUE_KEY", "repodna:jobs")
# Each worker replica needs its own stable id: it owns the "processing" list
# repodna:jobs:processing:<WORKER_ID> used to recover jobs after a crash.
WORKER_ID = os.getenv("WORKER_ID", "worker-1")
API_URL = os.getenv("API_URL", "http://api-service:8080").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

# --- Limits ----------------------------------------------------------------
MAX_FILES = _int_setting("MAX_FILES", 10_000)
MAX_FILE_SIZE_MB = _int_setting("MAX_FILE_SIZE_MB", 50)
MAX_REPO_SIZE_MB = _int_setting("MAX_REPO_SIZE_MB", 500)
# Must stay below the API's stuck-job timeout (JOB_RUNNING_TIMEOUT_MINUTES,
# default 10 minutes = 600 s), otherwise the API can fail a job that is still running.
JOB_TIMEOUT_SECONDS = _int_setting("JOB_TIMEOUT_SECONDS", 480)
REQUEST_TIMEOUT_SECONDS = _int_setting("REQUEST_TIMEOUT_SECONDS", 10)
RETRY_COUNT = _int_setting("RETRY_COUNT", 3)

# --- Sandbox (disposable container used to clone untrusted repositories) ----
SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "repodna-sandbox:latest")
SANDBOX_TIMEOUT_SECONDS = _int_setting("SANDBOX_TIMEOUT_SECONDS", 120)
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "1g")
SANDBOX_CPUS = _float_setting("SANDBOX_CPUS", 1.0)
SANDBOX_PIDS_LIMIT = _int_setting("SANDBOX_PIDS_LIMIT", 256)
# Only these hosts may be cloned (defence in depth; the API validates too).
ALLOWED_GIT_HOSTS = _list_setting("ALLOWED_GIT_HOSTS", "github.com,gitlab.com")

# --- Files -----------------------------------------------------------------
# Uploaded ZIPs live on a volume shared with the API (read-only for the worker).
ZIP_ROOT = os.getenv("ZIP_ROOT", "/data/uploads")
# Scratch space for one job; removed when the job ends.
WORK_DIR = os.getenv("WORK_DIR") or tempfile.gettempdir()
# 0 means "use every CPU core".
PARSE_WORKERS = _int_setting("PARSE_WORKERS", 0)
