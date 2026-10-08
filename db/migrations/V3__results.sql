CREATE TABLE job_results (
    job_id         UUID    PRIMARY KEY REFERENCES jobs (id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL,
    result         JSONB   NOT NULL
);

CREATE TABLE file_metrics (
    job_id      UUID    NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    path        TEXT    NOT NULL,
    loc         INTEGER NOT NULL,
    cyclomatic  INTEGER NOT NULL,
    cognitive   INTEGER NOT NULL,
    max_nesting INTEGER NOT NULL,
    PRIMARY KEY (job_id, path)
);

CREATE INDEX idx_file_metrics_job_id ON file_metrics (job_id);

CREATE TABLE dna_scores (
    job_id       UUID         PRIMARY KEY REFERENCES jobs (id) ON DELETE CASCADE,
    architecture NUMERIC(5,2) NOT NULL,
    code         NUMERIC(5,2) NOT NULL,
    quality      NUMERIC(5,2) NOT NULL
);