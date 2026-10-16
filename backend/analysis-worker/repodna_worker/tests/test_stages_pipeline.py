"""The whole analysis, from source folder to the result posted to the API.

Uses the real stages and the real contract/result.schema.json; only the source
acquisition and the HTTP callback are replaced.
"""

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from repodna_worker.consumer import config
from repodna_worker.consumer.pipeline import ApiClient, Pipeline
from repodna_worker.consumer.stages import (
    AnalysisStages,
    clean_cycles,
    flatten_evidence,
    graph_to_contract,
)

JOB_ID = "3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c"

LAYERED_REPO = {
    "requirements.txt": "flask==3.0\n",
    "app.py": "from controllers.user_controller import list_users\n\ndef main():\n    return list_users()\n",
    "controllers/__init__.py": "",
    "controllers/user_controller.py": "from services.user_service import get_users\n\ndef list_users():\n    return get_users()\n",
    "controllers/order_controller.py": (
        "from services.order_service import create_order\n"
        "from repositories.order_repository import raw_query\n\n"
        "def place():\n    raw_query()\n    return create_order()\n"
    ),
    "services/__init__.py": "",
    "services/user_service.py": (
        "from repositories.user_repository import all_users\n"
        "from services.order_service import create_order\n\n"
        "def get_users():\n    return all_users()\n"
    ),
    "services/order_service.py": (
        "from repositories.order_repository import save\n"
        "from services.user_service import get_users\n\n"
        "def create_order(items=None):\n"
        "    total = 0\n"
        "    for i in items or []:\n"
        "        if i > 0:\n"
        "            for j in range(i):\n"
        "                if j % 2:\n"
        "                    while total < 10:\n"
        "                        total += 1\n"
        "                elif j % 3:\n"
        "                    total -= 1\n"
        "                else:\n"
        "                    total += 2\n"
        "    get_users()\n"
        "    return save(total)\n"
    ),
    "repositories/__init__.py": "",
    "repositories/user_repository.py": "def all_users():\n    return []\n",
    "repositories/order_repository.py": "def save(x):\n    return x\n\ndef raw_query():\n    return 1\n",
    "web/index.js": "import { helper } from './util.js';\nexport function run(a){ if(a){ for(let i=0;i<3;i++){ if(i){ helper(i);} } } return a; }\n",
    "web/util.js": "export function helper(x){ return x*2; }\n",
}


class FakeApi:
    def __init__(self):
        self.statuses = []
        self.result = None

    def post_status(self, job_id, status, message=None):
        self.statuses.append((status, message))

    def post_result(self, job_id, result):
        self.result = result


def write_repo(root: Path, files: dict) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return root


def run_job(repo: Path, monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_KEY", "test-key")

    @contextmanager
    def local_source(job):
        yield repo

    pipeline = Pipeline.from_env(AnalysisStages(acquire=local_source, parse_workers=1).as_stages())
    api = FakeApi()
    pipeline._api = api
    pipeline({"job_id": JOB_ID, "source_type": "git", "repo_url": "https://github.com/a/b", "zip_path": None})
    return api


def test_full_pipeline_posts_a_schema_valid_result(tmp_path, monkeypatch):
    api = run_job(write_repo(tmp_path, LAYERED_REPO), monkeypatch)

    assert [status for status, _ in api.statuses] == ["RUNNING"]
    result = api.result
    assert result is not None, f"no result posted: {api.statuses}"
    assert result["job_id"] == JOB_ID
    assert result["schema_version"] == "1.0.0"
    assert result["repo_meta"]["source_type"] == "git"

    architecture = result["architecture"]
    assert architecture["pattern"] == "layered"
    assert {"from": "controllers/order_controller.py", "to": "repositories/order_repository.py",
            "rule": "controller_to_repository"} in architecture["violations"]
    assert ["services/order_service.py", "services/user_service.py"] in result["cycles"]

    # JS imports written with a file extension become graph edges.
    assert {"from": "web/index.js", "to": "web/util.js"} in result["graph"]["edges"]

    scores = result["scores"]
    assert set(scores) == {"architecture_dna", "code_dna", "quality_dna"}
    assert all(0 <= value <= 100 for value in scores.values())
    # Real numbers, not the "always 100" an unwired scorer returns.
    assert scores["architecture_dna"] < 100 and scores["code_dna"] < 100
    assert result["hotspots"][0]["path"] == "services/order_service.py"
    assert [item["name"] for item in result["frameworks"]] == ["Flask"]
    assert result["languages"][0]["name"] == "Python"


def test_result_is_json_serialisable(tmp_path, monkeypatch):
    api = run_job(write_repo(tmp_path, LAYERED_REPO), monkeypatch)
    json.dumps(api.result)


def test_repo_without_supported_files_fails_with_clear_message(tmp_path, monkeypatch):
    api = run_job(write_repo(tmp_path, {"Main.java": "class Main {}\n", "README.md": "hi\n"}), monkeypatch)
    assert api.result is None
    status, message = api.statuses[-1]
    assert status == "FAILED"
    assert "No Python, JavaScript or TypeScript" in message


def test_repo_over_limit_fails_before_analysis(tmp_path, monkeypatch):
    monkeypatch.setattr("repodna_worker.consumer.pipeline.validate_repository",
                        lambda repo: (_ for _ in ()).throw(ValueError("repository file count exceeds limit (3)")))
    api = run_job(write_repo(tmp_path, LAYERED_REPO), monkeypatch)
    assert api.result is None
    assert api.statuses[-1][0] == "FAILED" and "limit" in api.statuses[-1][1]


def test_acquire_failure_is_reported_as_failed(monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_KEY", "test-key")

    @contextmanager
    def broken(job):
        raise RuntimeError("clone exploded")
        yield  # pragma: no cover

    pipeline = Pipeline.from_env(AnalysisStages(acquire=broken).as_stages())
    api = FakeApi()
    pipeline._api = api
    pipeline({"job_id": JOB_ID, "source_type": "git", "repo_url": "https://github.com/a/b", "zip_path": None})
    assert api.statuses[-1][0] == "FAILED" and "clone exploded" in api.statuses[-1][1]


# --- shaping helpers ---------------------------------------------------------


def test_self_import_cycles_are_dropped():
    assert clean_cycles([["a.py"], ["a.py", "b.py"]]) == [["a.py", "b.py"]]


def test_unknown_pattern_has_no_evidence_files():
    assert flatten_evidence({"reason": "No supported architecture pattern was detected."}) == []


def test_layered_evidence_is_flat_sorted_file_list():
    evidence = {
        "layers": {"controller": ["c.py"], "service": ["s.py"], "repository": ["r.py"]},
        "edges": [{"from": "c.py", "to": "s.py"}],
    }
    assert flatten_evidence(evidence) == ["c.py", "r.py", "s.py"]


# --- API client matches the API contract --------------------------------------


def test_api_client_uses_the_header_and_field_names_the_api_expects(monkeypatch):
    calls = []

    class Response:
        status_code = 204

        def raise_for_status(self):
            pass

    client = ApiClient("http://api-service:8080", "secret")
    monkeypatch.setattr(client._session, "post", lambda url, json=None, timeout=None: calls.append((url, json)) or Response())
    client.post_status(JOB_ID, "FAILED", "boom")
    assert client._session.headers["X-Internal-Key"] == "secret"
    assert calls == [(f"http://api-service:8080/internal/jobs/{JOB_ID}/status", {"status": "FAILED", "error": "boom"})]


def test_api_client_refuses_to_start_without_a_key(monkeypatch):
    monkeypatch.setattr(config, "INTERNAL_API_KEY", "")
    with pytest.raises(RuntimeError, match="INTERNAL_API_KEY"):
        ApiClient.from_env()
