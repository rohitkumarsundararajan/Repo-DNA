"""Redis queue consumer for the Repo-DNA analysis worker.

Delivery is "safe at-most-once":

  * A job is moved atomically (BLMOVE) from the shared queue to this worker's own
    "processing" list, and removed from it only after the job finished.
  * If the worker dies mid-job, the job is still in the processing list. On the next
    start the worker finds it and marks the job FAILED right away (the user can
    resubmit) instead of leaving it QUEUED or RUNNING until a timeout. A job that
    crashes the worker is never retried automatically, so it cannot crash-loop.

Each worker replica needs its own stable WORKER_ID.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable

import redis
from jsonschema import Draft202012Validator

from . import config

# Must match the key the API pushes to (QUEUE_JOBS_KEY on the API). One place only.
QUEUE_KEY = config.QUEUE_KEY

# Seconds the blocking pop waits before returning so the loop can notice a shutdown request.
POLL_TIMEOUT_SECONDS = 5
RECONNECT_DELAY_SECONDS = 3

# worker.py -> consumer -> repodna_worker -> analysis-worker -> backend -> <repo root>
# (the Docker image keeps the same layout, so this works on a laptop and in the container)
_DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "contract" / "job_message.schema.json"

log = logging.getLogger("repodna.consumer")

PipelineFn = Callable[[dict], None]
RejectFn = Callable[[str, str], None]


def run_pipeline(job: dict) -> None:
    """Placeholder pipeline kept for tests; the real one is built in main()."""
    log.warning("job_id=%s placeholder pipeline; skipping", job.get("job_id"))


class Worker:
    def __init__(
        self,
        client: redis.Redis,
        validator: Draft202012Validator,
        pipeline: PipelineFn = run_pipeline,
        queue_key: str = QUEUE_KEY,
        processing_key: str | None = None,
        on_reject: RejectFn | None = None,
    ) -> None:
        self._redis = client
        self._validator = validator
        self._pipeline = pipeline
        self._queue_key = queue_key
        self._processing_key = processing_key or f"{queue_key}:processing:{config.WORKER_ID}"
        self._on_reject = on_reject
        self._stop = False

    # -- lifecycle ---------------------------------------------------------

    def request_stop(self, signum: int | None = None, _frame=None) -> None:
        """Signal handler: finish the current job, then exit the loop."""
        log.info("shutdown requested (signal=%s); finishing current job", signum)
        self._stop = True

    def run(self) -> None:
        self.recover_orphans()
        log.info("consumer started, listening on %s", self._queue_key)
        while not self._stop:
            try:
                raw = self._redis.blmove(
                    self._queue_key, self._processing_key, POLL_TIMEOUT_SECONDS, "RIGHT", "LEFT"
                )
            except redis.exceptions.RedisError as exc:
                log.error("redis error: %s; retrying in %ss", exc, RECONNECT_DELAY_SECONDS)
                time.sleep(RECONNECT_DELAY_SECONDS)
                continue

            if raw is None:  # timeout, loop to re-check the stop flag
                continue

            try:
                self.handle_message(raw)
            finally:
                self._acknowledge(raw)
        log.info("consumer stopped cleanly")

    def recover_orphans(self) -> None:
        """Fail jobs a previous run of this worker was processing when it stopped."""
        try:
            leftovers = self._redis.lrange(self._processing_key, 0, -1)
        except redis.exceptions.RedisError as exc:
            log.error("could not check for interrupted jobs: %s", exc)
            return
        for raw in leftovers:
            job_id = self._job_id_of(raw)
            log.warning("job_id=%s was interrupted by a worker restart; marking FAILED", job_id)
            self._reject(
                job_id,
                "worker_restarted: the analysis worker stopped while processing this job; "
                "please submit it again",
            )
            self._acknowledge(raw)

    # -- message handling --------------------------------------------------

    def handle_message(self, raw: bytes | str) -> None:
        job = self._parse_and_validate(raw)
        if job is None:
            return

        job_id = job.get("job_id")
        log.info("job_id=%s picked up", job_id)
        started = time.monotonic()
        try:
            self._pipeline(job)
        except Exception:  # one bad job must not kill the worker
            log.exception("job_id=%s failed", job_id)
            self._reject(job_id, "internal_error: the analysis worker hit an unexpected error")
        else:
            log.info("job_id=%s finished in %.2fs", job_id, time.monotonic() - started)

    def _parse_and_validate(self, raw: bytes | str) -> dict | None:
        try:
            job = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            log.error("dropping unparseable message: %s", exc)
            return None

        errors = sorted(self._validator.iter_errors(job), key=lambda e: list(e.path))
        if errors:
            job_id = job.get("job_id") if isinstance(job, dict) else None
            details = "; ".join(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors)
            log.error("job_id=%s dropping invalid message: %s", job_id, details)
            self._reject(job_id, f"invalid_job_message: {details}"[:400])
            return None
        return job

    # -- helpers -----------------------------------------------------------

    def _acknowledge(self, raw: bytes | str) -> None:
        try:
            self._redis.lrem(self._processing_key, 1, raw)
        except redis.exceptions.RedisError as exc:
            log.error("could not remove a finished job from the processing list: %s", exc)

    @staticmethod
    def _job_id_of(raw: bytes | str) -> str | None:
        try:
            job = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        value = job.get("job_id") if isinstance(job, dict) else None
        return value if isinstance(value, str) else None

    def _reject(self, job_id: str | None, reason: str) -> None:
        if not (self._on_reject and isinstance(job_id, str) and job_id):
            return
        try:
            self._on_reject(job_id, reason)
        except Exception:
            log.exception("job_id=%s could not report failure to the API", job_id)


def load_validator(schema_path: Path | None = None) -> Draft202012Validator:
    path = Path(schema_path or os.getenv("JOB_SCHEMA_PATH") or _DEFAULT_SCHEMA_PATH)
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def build_redis_client() -> redis.Redis:
    options = {
        "socket_timeout": POLL_TIMEOUT_SECONDS + 10,  # must exceed the blocking pop
        "socket_connect_timeout": 5,
        "health_check_interval": 30,
    }
    url = os.getenv("REDIS_URL")
    if url:
        return redis.Redis.from_url(url, **options)
    return redis.Redis(
        host=config.REDIS_HOST, port=config.REDIS_PORT, password=config.REDIS_PASSWORD, **options
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Imported here so the queue logic above can be tested without Docker or the analysis stack.
    from ..sandbox.container import Sandbox, SandboxError
    from .pipeline import Pipeline
    from .stages import build_stages

    try:
        Sandbox().ensure_image()
        pipeline = Pipeline.from_env(build_stages())
        validator = load_validator()
    except (SandboxError, RuntimeError, OSError, ValueError) as exc:
        log.error("worker cannot start: %s", exc)
        sys.exit(1)

    worker = Worker(build_redis_client(), validator, pipeline=pipeline, on_reject=pipeline.fail_job)
    signal.signal(signal.SIGINT, worker.request_stop)
    signal.signal(signal.SIGTERM, worker.request_stop)
    log.info(
        "worker %s ready (queue=%s, api=%s, sandbox=%s, job timeout=%ss)",
        config.WORKER_ID,
        config.QUEUE_KEY,
        config.API_URL,
        config.SANDBOX_IMAGE,
        config.JOB_TIMEOUT_SECONDS,
    )
    worker.run()


if __name__ == "__main__":
    main()
