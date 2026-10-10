"""Configuration for the analysis worker consumer."""

import os


def _int_setting(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


REDIS_HOST = os.getenv("REDIS_HOST", "redis")
QUEUE_KEY = os.getenv("QUEUE_KEY", "repodna:jobs")
API_URL = os.getenv("API_URL", "http://api-service:8080").rstrip("/")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

MAX_FILES = _int_setting("MAX_FILES", 10_000)
MAX_FILE_SIZE_MB = _int_setting("MAX_FILE_SIZE_MB", 50)
MAX_REPO_SIZE_MB = _int_setting("MAX_REPO_SIZE_MB", 500)
JOB_TIMEOUT_SECONDS = _int_setting("JOB_TIMEOUT_SECONDS", 600)
REQUEST_TIMEOUT_SECONDS = _int_setting("REQUEST_TIMEOUT_SECONDS", 10)
RETRY_COUNT = _int_setting("RETRY_COUNT", 3)