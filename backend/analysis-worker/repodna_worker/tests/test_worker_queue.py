"""Queue consumer: safe delivery, orphan recovery and invalid messages (fake Redis)."""

import json

import pytest

from repodna_worker.consumer.worker import Worker, load_validator

JOB_ID = "3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c"
QUEUE = "repodna:jobs"
PROCESSING = "repodna:jobs:processing:test"


class FakeRedis:
    """Just enough of Redis lists for the worker (BLMOVE, LRANGE, LREM)."""

    def __init__(self):
        self.lists = {}

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value if isinstance(value, bytes) else value.encode())

    def blmove(self, source, destination, timeout, src="LEFT", dest="RIGHT"):
        items = self.lists.get(source, [])
        if not items:
            return None
        value = items.pop() if src == "RIGHT" else items.pop(0)
        target = self.lists.setdefault(destination, [])
        target.insert(0, value) if dest == "LEFT" else target.append(value)
        return value

    def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    def lrem(self, key, count, value):
        items = self.lists.get(key, [])
        if value in items:
            items.remove(value)
        return 1


def message(**overrides):
    body = {"job_id": JOB_ID, "source_type": "git", "repo_url": "https://github.com/a/b", "zip_path": None}
    body.update(overrides)
    return json.dumps(body)


@pytest.fixture
def validator():
    return load_validator()


def make_worker(redis, validator, pipeline, rejected):
    worker = Worker(redis, validator, pipeline=pipeline, queue_key=QUEUE, processing_key=PROCESSING,
                    on_reject=lambda job_id, reason: rejected.append((job_id, reason)))
    return worker


def run_until_empty(worker, redis):
    """Run the loop until the queue is drained."""
    original = redis.blmove

    def stopping(*args, **kwargs):
        value = original(*args, **kwargs)
        if value is None:
            worker.request_stop()
        return value

    redis.blmove = stopping
    worker.run()


def test_job_is_processed_and_removed_from_processing_list(validator):
    redis, seen, rejected = FakeRedis(), [], []
    redis.lpush(QUEUE, message())
    run_until_empty(make_worker(redis, validator, seen.append, rejected), redis)
    assert [job["job_id"] for job in seen] == [JOB_ID]
    assert redis.lists[PROCESSING] == [] and redis.lists[QUEUE] == []
    assert rejected == []


def test_oldest_job_first(validator):
    redis, seen, rejected = FakeRedis(), [], []
    ids = ["11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"]
    for job_id in ids:  # the API LPUSHes, so the first one pushed is the oldest
        redis.lpush(QUEUE, message(job_id=job_id))
    run_until_empty(make_worker(redis, validator, seen.append, rejected), redis)
    assert [job["job_id"] for job in seen] == ids


def test_crashing_pipeline_fails_the_job_and_worker_keeps_going(validator):
    redis, rejected, seen = FakeRedis(), [], []

    def pipeline(job):
        seen.append(job["job_id"])
        if job["job_id"].startswith("1"):
            raise RuntimeError("boom")

    redis.lpush(QUEUE, message(job_id="11111111-1111-4111-8111-111111111111"))
    redis.lpush(QUEUE, message(job_id="22222222-2222-4222-8222-222222222222"))
    run_until_empty(make_worker(redis, validator, pipeline, rejected), redis)
    assert len(seen) == 2
    assert [job_id for job_id, _ in rejected] == ["11111111-1111-4111-8111-111111111111"]
    assert redis.lists[PROCESSING] == []


def test_interrupted_job_is_failed_on_restart_not_retried(validator):
    redis, seen, rejected = FakeRedis(), [], []
    redis.lists[PROCESSING] = [message().encode()]  # left behind by a crashed worker
    run_until_empty(make_worker(redis, validator, seen.append, rejected), redis)
    assert seen == []  # never run again (no crash loops)
    assert rejected and rejected[0][0] == JOB_ID and "worker_restarted" in rejected[0][1]
    assert redis.lists[PROCESSING] == []


def test_invalid_message_is_rejected_with_reason(validator):
    redis, seen, rejected = FakeRedis(), [], []
    redis.lpush(QUEUE, message(source_type="zip", zip_path=None))  # zip without zip_path
    run_until_empty(make_worker(redis, validator, seen.append, rejected), redis)
    assert seen == []
    assert rejected and rejected[0][0] == JOB_ID and "invalid_job_message" in rejected[0][1]


def test_garbage_message_is_dropped(validator):
    redis, seen, rejected = FakeRedis(), [], []
    redis.lpush(QUEUE, "not json at all")
    run_until_empty(make_worker(redis, validator, seen.append, rejected), redis)
    assert seen == [] and rejected == []
    assert redis.lists[PROCESSING] == []


def test_api_failure_while_rejecting_does_not_kill_the_worker(validator):
    redis, seen = FakeRedis(), []

    def failing_reject(job_id, reason):
        raise RuntimeError("api down")

    redis.lpush(QUEUE, message(source_type="zip", zip_path=None))
    redis.lpush(QUEUE, message(job_id="22222222-2222-4222-8222-222222222222"))
    worker = Worker(redis, validator, pipeline=seen.append, queue_key=QUEUE, processing_key=PROCESSING,
                    on_reject=failing_reject)
    run_until_empty(worker, redis)
    assert [job["job_id"] for job in seen] == ["22222222-2222-4222-8222-222222222222"]
