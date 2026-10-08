-- =====================================================================
-- LOCAL DEVELOPMENT ONLY. NEVER RUN IN PRODUCTION.
--
-- Loads one fake user, one DONE job, and its result so the
-- result-serving endpoints can be tested without a real analysis.
--
-- Test login:  test@repodna.dev / password123   (fake, local only)
--
-- NOT a Flyway migration (Flyway only reads db/migrations), so it is
-- never applied automatically. Run it by hand, from the repo root:
--
--   Get-Content db\seed\seed.sql | docker compose -f infra/docker-compose.yml exec -T postgres psql -U repodna -d repodna
--
-- Safe to run more than once (ON CONFLICT DO NOTHING).
--
-- NOTE: the JSON below is a copy of contract/fixtures/sample_result.json.
-- If the fixture changes, update this file too. Requires V4 (schema_version
-- as TEXT), because the fixture uses "1.0.0".
-- =====================================================================

BEGIN;

-- 1. Test user (bcrypt hash of "password123", cost 10)
INSERT INTO users (email, password_hash)
VALUES ('test@repodna.dev',
        '$2a$10$.8zNdgC60tqOdQcPsLIqv.w4JyE1gVNrARzKaTZZOCuHUvMzvQ3TW')
ON CONFLICT (email) DO NOTHING;

-- 2. One finished job (id matches job_id in the fixture)
INSERT INTO jobs (id, user_id, source_type, repo_url, status, created_at, finished_at)
VALUES ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c',
        (SELECT id FROM users WHERE email = 'test@repodna.dev'),
        'git',
        'https://github.com/repodna-demo/mini-flask-shop.git',
        'DONE',
        '2026-09-20T14:31:57Z',
        '2026-09-20T14:32:07Z')
ON CONFLICT (id) DO NOTHING;

-- 3. Full result JSON (copy of contract/fixtures/sample_result.json)
INSERT INTO job_results (job_id, schema_version, result)
VALUES ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c',
        '1.0.0',
        $json$
{
  "schema_version": "1.0.0",
  "job_id": "3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c",

  "repo_meta": {
    "repo_url": "https://github.com/repodna-demo/mini-flask-shop.git",
    "source_type": "git",
    "total_files": 6,
    "total_loc": 540,
    "analyzed_at": "2026-09-20T14:32:07Z"
  },

  "languages": [
    { "name": "Python", "file_count": 6, "loc": 540, "percentage": 100.0 }
  ],

  "frameworks": [
    { "name": "Flask", "category": "web" }
  ],

  "files": [
    { "path": "src/app.py", "loc": 45, "cyclomatic": 6, "cognitive": 8, "max_nesting": 2 },
    { "path": "src/routes/users.py", "loc": 80, "cyclomatic": 12, "cognitive": 15, "max_nesting": 3 },
    { "path": "src/routes/orders.py", "loc": 95, "cyclomatic": 14, "cognitive": 18, "max_nesting": 4 },
    { "path": "src/services/user_service.py", "loc": 120, "cyclomatic": 20, "cognitive": 25, "max_nesting": 3 },
    { "path": "src/services/order_service.py", "loc": 140, "cyclomatic": 24, "cognitive": 30, "max_nesting": 4 },
    { "path": "src/db/models.py", "loc": 60, "cyclomatic": 5, "cognitive": 6, "max_nesting": 1 }
  ],

  "hotspots": [
    { "path": "src/services/order_service.py", "metric": "cyclomatic", "value": 24 },
    { "path": "src/services/user_service.py", "metric": "cognitive", "value": 25 },
    { "path": "src/routes/orders.py", "metric": "max_nesting", "value": 4 }
  ],

  "graph": {
    "nodes": [
      { "path": "src/app.py", "language": "python", "folder": "src", "fan_in": 0, "fan_out": 2 },
      { "path": "src/routes/users.py", "language": "python", "folder": "src/routes", "fan_in": 1, "fan_out": 1 },
      { "path": "src/routes/orders.py", "language": "python", "folder": "src/routes", "fan_in": 1, "fan_out": 2 },
      { "path": "src/services/user_service.py", "language": "python", "folder": "src/services", "fan_in": 2, "fan_out": 2 },
      { "path": "src/services/order_service.py", "language": "python", "folder": "src/services", "fan_in": 2, "fan_out": 2 },
      { "path": "src/db/models.py", "language": "python", "folder": "src/db", "fan_in": 3, "fan_out": 0 }
    ],
    "edges": [
      { "from": "src/app.py", "to": "src/routes/users.py" },
      { "from": "src/app.py", "to": "src/routes/orders.py" },
      { "from": "src/routes/users.py", "to": "src/services/user_service.py" },
      { "from": "src/routes/orders.py", "to": "src/services/order_service.py" },
      { "from": "src/services/user_service.py", "to": "src/db/models.py" },
      { "from": "src/services/order_service.py", "to": "src/db/models.py" },
      { "from": "src/services/order_service.py", "to": "src/services/user_service.py" },
      { "from": "src/services/user_service.py", "to": "src/services/order_service.py" },
      { "from": "src/routes/orders.py", "to": "src/db/models.py" }
    ]
  },

  "cycles": [
    ["src/services/order_service.py", "src/services/user_service.py"]
  ],

  "architecture": {
    "pattern": "layered",
    "evidence": [
      "src/app.py",
      "src/routes/users.py",
      "src/routes/orders.py",
      "src/services/user_service.py",
      "src/services/order_service.py",
      "src/db/models.py"
    ],
    "violations": [
      {
        "from": "src/routes/orders.py",
        "to": "src/db/models.py",
        "rule": "routes-must-not-access-db-directly"
      }
    ]
  },

  "scores": {
    "architecture_dna": 72.5,
    "code_dna": 64.0,
    "quality_dna": 78.3
  }
}
$json$::jsonb)
ON CONFLICT (job_id) DO NOTHING;

-- 4. Per-file metrics (same values as "files" in the fixture)
INSERT INTO file_metrics (job_id, path, loc, cyclomatic, cognitive, max_nesting) VALUES
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/app.py',                    45,  6,  8, 2),
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/routes/users.py',           80, 12, 15, 3),
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/routes/orders.py',          95, 14, 18, 4),
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/services/user_service.py', 120, 20, 25, 3),
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/services/order_service.py',140, 24, 30, 4),
  ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 'src/db/models.py',              60,  5,  6, 1)
ON CONFLICT (job_id, path) DO NOTHING;

-- 5. DNA scores (same values as "scores" in the fixture)
INSERT INTO dna_scores (job_id, architecture, code, quality)
VALUES ('3f9c1a2e-6b3d-4e7a-9c1a-2e6b3d4e7a9c', 72.5, 64.0, 78.3)
ON CONFLICT (job_id) DO NOTHING;

COMMIT;