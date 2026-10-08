-- Allow ZIP uploads: a ZIP job has a zip_path instead of a repo_url.
-- source_type now uses the same values as the queue message: 'git' or 'zip'.

ALTER TABLE jobs ALTER COLUMN repo_url DROP NOT NULL;

ALTER TABLE jobs ADD COLUMN zip_path TEXT;

UPDATE jobs SET source_type = 'git' WHERE source_type = 'GITHUB_URL';

ALTER TABLE jobs ALTER COLUMN source_type SET DEFAULT 'git';

ALTER TABLE jobs
    ADD CONSTRAINT chk_jobs_source_type CHECK (source_type IN ('git', 'zip'));

ALTER TABLE jobs
    ADD CONSTRAINT chk_jobs_source_fields CHECK (
        (source_type = 'git' AND repo_url IS NOT NULL AND zip_path IS NULL)
     OR (source_type = 'zip' AND zip_path IS NOT NULL AND repo_url IS NULL)
    );