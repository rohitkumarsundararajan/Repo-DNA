import time
from contextlib import contextmanager

from repodna_worker.consumer import config
from repodna_worker.consumer import pipeline as pipeline_module
from repodna_worker.consumer.pipeline import Pipeline, Stages
from repodna_worker.sandbox.resource_limits import RepositoryLimitError


class _Api:
    def __init__(self):
        self.statuses = []

    def post_status(self, job_id, status, message=None):
        self.statuses.append((job_id, status, message))

    def post_result(self, _job_id, _result):
        pass


def _stages(acquire, detect):
    return Stages(
        acquire=acquire,
        detect=detect,
        parse=lambda _repo, _detection: [],
        compute_metrics=lambda _parsed: {},
        build_graph=lambda _parsed: {},
        find_cycles=lambda _graph: [],
        detect_architecture=lambda _graph, _parsed: {},
        compute_scores=lambda *_args: {},
        assemble=lambda *_args: {},
    )


def test_repository_limit_fails_job_before_detection(tmp_path, monkeypatch):
    api = _Api()
    detected = []

    @contextmanager
    def acquire(_job):
        yield tmp_path

    def reject(_repo):
        raise RepositoryLimitError("repository file count exceeds limit")

    monkeypatch.setattr(pipeline_module, "validate_repository", reject)
    pipeline = Pipeline(_stages(acquire, lambda *_args: detected.append(True)), api)

    pipeline({"job_id": "limit-test"})

    assert detected == []
    assert api.statuses[-1][1] == "FAILED"
    assert "repository file count exceeds limit" in api.statuses[-1][2]


def test_job_timeout_reports_failure_and_cleans_up(tmp_path, monkeypatch):
    api = _Api()
    state = {"cleaned": False}

    @contextmanager
    def acquire(_job):
        try:
            yield tmp_path
        finally:
            state["cleaned"] = True

    def slow_detect(_repo):
        time.sleep(1.1)
        return {}

    monkeypatch.setattr(config, "JOB_TIMEOUT_SECONDS", 1)
    pipeline = Pipeline(_stages(acquire, slow_detect), api)

    pipeline({"job_id": "timeout-test"})

    assert state["cleaned"] is True
    assert api.statuses[-1][1] == "FAILED"
    assert "timeout" in api.statuses[-1][2]