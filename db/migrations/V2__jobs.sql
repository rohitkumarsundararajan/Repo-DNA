CREATE TABLE jobs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     BIGINT      NOT NULL REFERENCES users (id),
    source_type TEXT        NOT NULL DEFAULT 'GITHUB_URL',
    repo_url    TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'QUEUED'
                CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED')),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX idx_jobs_user_id ON jobs (user_id);