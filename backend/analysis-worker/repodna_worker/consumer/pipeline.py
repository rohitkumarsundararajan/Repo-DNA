"""Pipeline orchestrator: runs every analysis stage, in order, for one job.

Flow: RUNNING -> sandbox -> detect -> parse -> metrics
      -> build_graph -> find_cycles -> detect_architecture -> compute_scores -> assemble
      -> validate -> POST result.
Any exception posts FAILED with a short message. Sandbox cleanup always runs.

Every stage is injected through `Stages`, so the real implementations (and Venky's
functions) can be swapped in without touching the orchestration logic.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterator

import requests
from jsonschema import Draft202012Validator

log = logging.getLogger("repodna.pipeline")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_RESULT_SCHEMA_PATH = _REPO_ROOT / "contract" / "result.schema.json"

MAX_FAILURE_MESSAGE_CHARS = 500


# --------------------------------------------------------------------------- #
# Stage signatures (AGREE THE VENKY ONES WITH HIM BEFORE MERGING)
# --------------------------------------------------------------------------- #
@dataclass
class Stages:
    # Ours
    acquire: Callable[[dict], ContextManager[Path]]  # job -> ctx yielding repo path; cleans up on exit
    detect: Callable[[Path], Any]  # repo_path -> detection (languages, files)
    parse: Callable[[Path, Any], list]  # repo_path, detection -> parsed_files
    compute_metrics: Callable[[list], Any]  # parsed_files -> metrics
    # Venky's
    build_graph: Callable[[list], Any]  # parsed_files -> graph
    find_cycles: Callable[[Any], Any]  # graph -> cycles
    detect_architecture: Callable[[Any, list], Any]  # graph, parsed_files -> architecture
    compute_scores: Callable[[Any, Any, Any, Any], Any]  # graph, cycles, architecture, metrics -> scores
    assemble: Callable[[dict, Any, Any, Any, Any, Any], dict]  # job, graph, cycles, architecture, metrics, scores -> result

    @classmethod
    def stubs(cls) -> "Stages":
        return cls(
            acquire=_stub_acquire,
            detect=lambda repo: _stub("detect", {}),
            parse=lambda repo, detection: _stub("parse", []),
            compute_metrics=lambda parsed: _stub("metrics", {}),
            build_graph=lambda parsed: _stub("build_graph", {"nodes": [], "edges": []}),
            find_cycles=lambda graph: _stub("find_cycles", []),
            detect_architecture=lambda graph, parsed: _stub("detect_architecture", {}),
            compute_scores=lambda graph, cycles, arch, metrics: _stub("compute_scores", {}),
            assemble=_stub_assemble,
        )


def _stub(name: str, value: Any) -> Any:
    log.warning("stage %r is a stub", name)
    return value


@contextmanager
def _stub_acquire(job: dict) -> Iterator[Path]:
    log.warning("stage 'sandbox' is a stub (no clone/extract)")
    path = Path(tempfile.mkdtemp(prefix="repodna-stub-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _stub_assemble(job: dict, graph: Any, cycles: Any, architecture: Any, metrics: Any, scores: Any) -> dict:
    log.warning("stage 'assemble' is a stub; result will not satisfy result.schema.json")
    return {"job_id": job.get("job_id"), "stub": True}


# --------------------------------------------------------------------------- #
# API client (internal callbacks)
# --------------------------------------------------------------------------- #
class ApiClient:
    """Posts status and results to the API service, secured by INTERNAL_API_KEY.

    ASSUMPTIONS to confirm with the API owner: endpoint paths, HTTP methods,
    header name, and that posting the result marks the job as completed.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0, attempts: int = 3) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._attempts = attempts
        self._session = requests.Session()
        self._session.headers.update({"X-Internal-Api-Key": api_key})

    @classmethod
    def from_env(cls) -> "ApiClient":
        return cls(
            base_url=os.getenv("API_BASE_URL", "http://api-service:8080"),
            api_key=os.environ["INTERNAL_API_KEY"],
        )

    def post_status(self, job_id: str, status: str, message: str | None = None) -> None:
        body: dict[str, Any] = {"status": status}
        if message:
            body["message"] = message
        self._post(f"/internal/jobs/{job_id}/status", body)

    def post_result(self, job_id: str, result: dict) -> None:
        self._post(f"/internal/jobs/{job_id}/result", result)

    def _post(self, path: str, body: dict) -> None:
        url = self._base_url + path
        last_exc: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                resp = self._session.post(url, json=body, timeout=self._timeout)
                if resp.status_code < 500:
                    resp.raise_for_status()  # 4xx is not retried
                    return
                last_exc = requests.HTTPError(f"{resp.status_code} from {path}")
            except requests.HTTPError:
                raise
            except requests.RequestException as exc:
                last_exc = exc
            if attempt < self._attempts:
                time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"POST {path} failed after {self._attempts} attempts: {last_exc}")


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class Pipeline:
    def __init__(
        self,
        stages: Stages,
        api: ApiClient,
        result_validator: Draft202012Validator | None = None,
    ) -> None:
        self._stages = stages
        self._api = api
        self._validator = result_validator

    @classmethod
    def from_env(cls, stages: Stages | None = None) -> "Pipeline":
        schema_path = Path(os.getenv("RESULT_SCHEMA_PATH") or _DEFAULT_RESULT_SCHEMA_PATH)
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return cls(stages or Stages.stubs(), ApiClient.from_env(), Draft202012Validator(schema))

    def __call__(self, job: dict) -> None:
        """Run one job. Never raises for stage failures; they are reported as FAILED."""
        job_id = job.get("job_id")
        stage = "start"

        def step(name: str, fn: Callable[..., Any], *args: Any) -> Any:
            nonlocal stage
            stage = name
            started = time.monotonic()
            out = fn(*args)
            log.info("job_id=%s stage=%s done in %.2fs", job_id, name, time.monotonic() - started)
            return out

        try:
            if not job_id:
                raise ValueError("job has no job_id")

            step("status:running", self._api.post_status, job_id, "RUNNING")

            # ExitStack guarantees sandbox cleanup, even when a later stage raises.
            with ExitStack() as stack:
                repo = stack.enter_context(step("sandbox", self._stages.acquire, job))
                detection = step("detect", self._stages.detect, repo)
                parsed = step("parse", self._stages.parse, repo, detection)
                metrics = step("metrics", self._stages.compute_metrics, parsed)

                graph = step("build_graph", self._stages.build_graph, parsed)
                cycles = step("find_cycles", self._stages.find_cycles, graph)
                architecture = step("detect_architecture", self._stages.detect_architecture, graph, parsed)
                scores = step("compute_scores", self._stages.compute_scores, graph, cycles, architecture, metrics)
                result = step("assemble", self._stages.assemble, job, graph, cycles, architecture, metrics, scores)

                step("validate", self._validate_result, result)
                step("post_result", self._api.post_result, job_id, result)

            log.info("job_id=%s completed", job_id)
        except Exception as exc:
            log.exception("job_id=%s failed at stage=%s", job_id, stage)
            self._report_failure(job_id, stage, exc)

    # -- helpers -----------------------------------------------------------

    def _validate_result(self, result: dict) -> None:
        if self._validator is None:
            return
        errors = sorted(self._validator.iter_errors(result), key=lambda e: list(e.path))
        if errors:
            shown = "; ".join(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:5])
            more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
            raise ValueError(f"result failed schema validation: {shown}{more}")

    def _report_failure(self, job_id: str | None, stage: str, exc: Exception) -> None:
        if not job_id:
            return
        message = f"{stage}: {type(exc).__name__}: {exc}"[:MAX_FAILURE_MESSAGE_CHARS]
        try:
            self._api.post_status(job_id, "FAILED", message)
        except Exception:
            log.exception("job_id=%s could not post FAILED status", job_id)