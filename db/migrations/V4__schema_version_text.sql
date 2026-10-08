ALTER TABLE job_results
    ALTER COLUMN schema_version TYPE TEXT USING schema_version::text;