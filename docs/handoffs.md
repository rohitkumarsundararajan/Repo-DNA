# RepoDNA Handoffs

Single reference for who hands what to whom, the queue key, callback URLs, environment variables, API endpoints and how to run everything. If something here changes, update this file in the same PR.

## 1. Finalised stack

Do not pick older versions from outdated tutorials or docs.

| Component | Version / choice |
|---|---|
| Java | 21 |
| Spring Boot | 4.1.1 (Spring Security 7, Jackson 3 `tools.jackson.*`) |
| Python (analysis worker) | 3.12 |
| Database | PostgreSQL 16, schema managed by Flyway |
| Queue | Redis 7 (list `repodna:jobs`) |
| Auth | JWT (HS256) for users, `X-Internal-Key` for the worker |

## 2. Overall flow

```
User -> API service -> Postgres (job row, QUEUED)
                    -> Redis LPUSH repodna:jobs
Analysis worker <- BRPOP repodna:jobs
  clone in sandbox -> detect -> parse -> metrics
  -> graph / cycles / architecture / scoring / assemble
  -> POST /internal/jobs/{id}/status and /result  (X-Internal-Key)
API service -> Postgres (job DONE + results)
Frontend -> GET /jobs/{id}, /result, /graph, /dashboard, /cycles, /violations
```

The JSON contract in `contract/` is the handshake between all three backend owners. Changes need sign-off from all three plus a `schema_version` bump.

## 3. Who gives what to whom

| From | To | What | Where |
|---|---|---|---|
| API service | Analysis worker | Job message on the queue | Redis list `repodna:jobs` |
| Analysis worker | API service | Status updates and final result | `POST /internal/jobs/{id}/status`, `POST /internal/jobs/{id}/result` |
| Analysis worker | Graph and scoring | `ParsedFile` objects and metrics | Python modules in `backend/analysis-worker/` |
| Graph and scoring | Analysis worker | Graph, cycles, architecture, scores, assembled result | Functions called by the pipeline orchestrator |
| All three | Everyone | JSON contract and sample fixture | `contract/result.schema.json`, `contract/job_message.schema.json`, `contract/fixtures/sample_result.json` |
| API service | Frontend | Public REST endpoints and base API URL | Section 6 |
| API service | Everyone | Database schema | `db/migrations/` (Flyway) |

## 4. Queue

- **Key:** `repodna:jobs` (configurable via `QUEUE_JOBS_KEY`, default `repodna:jobs`)
- **Producer:** API pushes with `LPUSH` after the job row is committed.
- **Consumer:** worker reads with `BRPOP`.
- **Message:** JSON matching `contract/job_message.schema.json`.

| Field | Meaning |
|---|---|
| `job_id` | UUID of the job (required) |
| `source_type` | `git` or `zip` (required) |
| `repo_url` | Set when `source_type` is `git`, otherwise null |
| `zip_path` | Set when `source_type` is `zip`, otherwise null |

Exactly one of `repo_url` and `zip_path` is set.

If Redis is unreachable when a job is created, the job is marked `FAILED` with error `queue_unavailable`.

## 5. Worker callbacks (internal)

Protected by the `X-Internal-Key` header, which must equal `INTERNAL_API_KEY`. User JWTs do not work on these endpoints.

| Method and path | Body | Result |
|---|---|---|
| `POST /internal/jobs/{id}/status` | `{"status": "RUNNING"}` or `{"status": "FAILED", "error": "..."}` | `204` |
| `POST /internal/jobs/{id}/result` | Full result JSON, validated against `contract/result.schema.json` | `204`, job becomes `DONE` |

Behaviour to know:

| Case | Response |
|---|---|
| Missing or wrong `X-Internal-Key` | `401` |
| Unknown job id | `404` |
| Result posted again for a finished job | `409` |
| Result fails schema validation | `400`, job becomes `FAILED` with error `invalid_result` |
| Job stays `RUNNING` longer than `JOB_RUNNING_TIMEOUT_MINUTES` (default 10) | Marked `FAILED` with error `worker_timeout` by a cleanup task running every 60 seconds |

Results are saved in a single transaction: `job_results` (jsonb), `file_metrics` and `dna_scores`.

## 6. Public API endpoints

Base URL: `http://localhost:8080` for local development (confirm the port in your run config). **Frontend: add the deployed base URL here when the Frontend work starts.**

All endpoints except `/auth/**` need the header `Authorization: Bearer <jwt>`. Users only see their own jobs; another user's job returns `404`.

### Auth

| Method and path | Purpose | Notes |
|---|---|---|
| `POST /auth/register` | Create account, returns a JWT (auto-login) | `201`; duplicate email `409`; password under 8 characters `400` |
| `POST /auth/login` | Log in, returns a JWT | `200`; wrong password `401` |

### Jobs

| Method and path | Purpose | Notes |
|---|---|---|
| `POST /jobs` | Submit a repo. JSON `{"repo_url": "https://github.com/..."}` or multipart ZIP upload | Returns `{"job_id": "..."}`; only https GitHub or GitLab URLs, otherwise `400` |
| `GET /jobs` | List your jobs | |
| `GET /jobs/{id}` | Job status (`QUEUED`, `RUNNING`, `DONE`, `FAILED`) and error if any | |

### Results (job must be `DONE`, otherwise `409`)

| Method and path | Returns |
|---|---|
| `GET /jobs/{id}/result` | Full result JSON |
| `GET /jobs/{id}/graph` | Dependency graph (nodes and edges) |
| `GET /jobs/{id}/dashboard` | Three DNA scores plus top 10 complexity hotspots |
| `GET /jobs/{id}/cycles` | Dependency cycles |
| `GET /jobs/{id}/violations` | Architecture boundary violations |

### Common error responses

Errors share one JSON shape (`ApiError`). Status codes used: `400`, `401`, `403`, `404`, `409`, `500`.

A Postman collection with all of the above is in `docs/postman_collection.json`.

## 7. Environment variables

Names only. Real values live in `infra/.env`, which is never committed. `infra/.env.example` is committed and lists the names.

| Variable | Used by | Purpose |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Postgres container | Database bootstrap |
| `DB_URL`, `DB_USER`, `DB_PASSWORD` | API | JDBC connection |
| `REDIS_HOST` | API, worker | Redis host |
| `QUEUE_JOBS_KEY` | API | Queue key, default `repodna:jobs` |
| `JWT_SECRET` | API | HS256 signing key, 32+ characters, no default |
| `JWT_EXPIRY_MINUTES` | API | Token lifetime, default 60 |
| `INTERNAL_API_KEY` | API, worker | Shared secret for `X-Internal-Key` |
| `ZIP_DIR` | API | Where uploaded ZIPs are saved, default `./uploads` |
| `JOB_RUNNING_TIMEOUT_MINUTES` | API | Stuck-job timeout, default 10 |

Never hardcode secrets in code or commit them.

## 8. How to run

### Everything with Docker Compose

Prerequisites: Docker Desktop running, `infra/.env` created from `infra/.env.example` with real values.

```
cd infra
docker compose up --build
```

Services:

| Service | Image / source | Purpose |
|---|---|---|
| `postgres` | `postgres:16` | Database (named volume, healthcheck) |
| `redis` | `redis:7` | Job queue |
| `api-service` | `backend/api-service/Dockerfile` (Java 21 base) | REST API |
| `analysis-worker` | `backend/analysis-worker/Dockerfile` (Python 3.12) | Analysis pipeline |

Flyway applies the migrations in `db/migrations/` when the API starts. Never edit an already applied migration; add a new `V` file.

### API only, for local development

1. Start Docker Desktop, then start Postgres and Redis (compose with only those two services, or the existing containers).
2. From `backend/api-service`, run the app with the database and secret variables set in the same command.
3. Windows note: a leftover system variable such as `DB_USER` overrides the app's value. Set `DB_USER` and `DB_PASSWORD` in the same PowerShell command that starts the app.

```
cd backend\api-service
mvn spring-boot:run
```

### Tests

Docker Desktop must be running (tests use Testcontainers Postgres).

```
cd backend\api-service
mvn test
```

Run `mvn test` before every push.

## 9. Open items

Decisions still to confirm with the team:

- Sandbox scope: whether the whole analysis or only the clone runs in the sandbox container.
- Where `madge` runs: worker image or `infra/sandbox.Dockerfile`.
- Docker socket access for the worker in compose (needed for sandboxing).
- `zip_path` is currently a local absolute path; compose needs a shared volume so the worker can read uploaded ZIPs.
- DNA score formulas and exact cognitive complexity rules.
