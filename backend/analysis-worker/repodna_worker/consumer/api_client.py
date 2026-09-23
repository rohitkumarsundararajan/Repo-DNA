"""HTTP client for worker callbacks to the API service."""

from typing import Any

import requests

from repodna_worker.consumer import config


def _post(path: str, payload: dict[str, Any]) -> requests.Response:
    headers = {"X-Internal-Key": config.INTERNAL_API_KEY}
    url = f"{config.API_URL}/internal/jobs/{path}"

    last_error: requests.RequestException | None = None
    for _ in range(config.RETRY_COUNT):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=config.REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError("Callback retry count must be greater than zero")


def post_status(job_id: str, status: str, error: str | None = None) -> requests.Response:
    """Post a worker status update for a job."""
    return _post(f"{job_id}/status", {"status": status, "error": error})


def post_result(job_id: str, result: dict[str, Any]) -> requests.Response:
    """Post the completed analysis result for a job."""
    return _post(f"{job_id}/result", result)