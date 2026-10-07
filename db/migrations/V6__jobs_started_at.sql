-- Time the worker reported RUNNING; used to detect stuck jobs.
ALTER TABLE jobs ADD COLUMN started_at TIMESTAMPTZ;

-- Jobs already RUNNING before this migration: count from creation time.
UPDATE jobs SET started_at = created_at WHERE status = 'RUNNING';
