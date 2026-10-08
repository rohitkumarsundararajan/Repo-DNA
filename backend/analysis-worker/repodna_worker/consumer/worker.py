"""Redis queue consumer for the Repo-DNA analysis worker.

MVP semantics: BRPOP pops the message *before* processing, so a job is lost if the
worker dies mid-run (at-most-once delivery). Move to BRPOPLPUSH / a reliable queue
or RabbitMQ if that matters later.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Callable

import redis
from jsonschema import Draft202012Validator

# Must match the key the API pushes to (Rohit's task 12). Change in ONE place only.
QUEUE_KEY = "repodna:jobs"

# Seconds BRPOP blocks before returning so the loop can notice a shutdown request.
POLL_TIMEOUT_SECONDS = 5
RECONNECT_DELAY_SECONDS = 3

# worker.py -> consumer -> repodna_worker -> analysis-worker -> backend -> <repo root>
_DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[4] / "contract" / "job_message.schema.json"

log = logging.getLogger("repodna.consumer")

Pipeline = Callable[[dict], None]


def run_pipeline(job: dict) -> None:
    """Placeholder for the real analysis pipeline.

    TODO: acquire source (Git/ZIP) -> parse -> graph -> metrics -> score ->
    assemble -> validate against result.schema.json -> POST to the API.
    """
    log.warning("job_id=%s pipeline not implemented yet; skipping", job.get("job_id"))


class Worker:
    def __init__(
        self,
        client: redis.Redis,
        validator: Draft202012Validator,
        pipeline: Pipeline = run_pipeline,
        queue_key: str = QUEUE_KEY,
    ) -> None:
        self._redis = client
        self._validator = validator
        self._pipeline = pipeline
        self._queue_key = queue_key
        self._stop = False

    # -- lifecycle ---------------------------------------------------------

    def request_stop(self, signum: int | None = None, _frame=None) -> None:
        """Signal handler: finish the current job, then exit the loop."""
        log.info("shutdown requested (signal=%s); finishing current job", signum)
        self._stop = True

    def run(self) -> None:
        log.info("consumer started, listening on %s", self._queue_key)
        while not self._stop:
            try:
                item = self._redis.brpop(self._queue_key, timeout=POLL_TIMEOUT_SECONDS)
            except redis.exceptions.RedisError as exc:
                log.error("redis error: %s; retrying in %ss", exc, RECONNECT_DELAY_SECONDS)
                time.sleep(RECONNECT_DELAY_SECONDS)
                continue

            if item is None:  # timeout, loop to re-check the stop flag
                continue

            _key, raw = item
            self.handle_message(raw)
        log.info("consumer stopped cleanly")

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
            return None
        return job


def load_validator(schema_path: Path | None = None) -> Draft202012Validator:
    path = Path(schema_path or os.getenv("JOB_SCHEMA_PATH") or _DEFAULT_SCHEMA_PATH)
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    worker = Worker(client, load_validator())

    signal.signal(signal.SIGINT, worker.request_stop)
    signal.signal(signal.SIGTERM, worker.request_stop)
    worker.run()


if __name__ == "__main__":
    main()