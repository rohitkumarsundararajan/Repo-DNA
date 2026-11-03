# RepoDNA

**Read the DNA of any code repository.**

RepoDNA takes a GitHub or GitLab link (or a ZIP of a project) and tells you how the code is built: how the files depend on each other, where the loops and layer breaks hide, and how healthy the project is, scored out of 100.

Submit a repo, get a job id straight back, and watch the analysis run in the background. When it finishes, the results are ready to explore.

## Features (Phase 1)

- **Submit a repo** by GitHub/GitLab link or ZIP upload, with live job status
- **Safe by design**: repos are copied into an isolated sandbox, and nothing from the repo is ever run
- **Language and framework detection** for the project
- **Code reading** for Python, JavaScript and TypeScript
- **Complexity measurement**, with the hardest files ranked as hotspots
- **Dependency map** showing which file depends on which
- **Cycle detection** for files that depend on each other in a loop
- **Architecture detection** (for example Layered) with the evidence behind it, plus layer-rule violations
- **Three DNA scores** out of 100: Architecture, Code and Quality
- **Private accounts**: sign up and sign in, and only you see your results

## How it works

```
Frontend  ->  API service  ->  Redis queue  ->  Analysis worker
                  |                                   |
              PostgreSQL  <---------------------------+
```

| Part | Folder | Built with |
|---|---|---|
| API service | `backend/api-service` | Java 21, Spring Boot, PostgreSQL, Flyway, Redis, JWT |
| Analysis worker | `backend/analysis-worker` | Python 3.12 |
| Frontend | `frontend` | React, TypeScript, Vite |
| Infrastructure | `infra` | Docker Compose |

## Run it

You need **Docker Desktop** (running) and **Git**. For the frontend you also need **Node.js**.

**1. Clone the repo**

```powershell
git clone <your-repo-url>
cd RepoDNA
```

**2. Create the environment file**

Copy `infra/.env.example` to `infra/.env` and fill in your own values (database password, JWT secret of 32+ characters, internal API key). Never commit the `.env` file.

**3. Start the backend** (database, queue, API and worker)

```powershell
cd infra
docker compose up --build
```

The API is now at `http://localhost:8080`.

**4. Start the frontend**

```powershell
cd frontend
npm install
npm run dev
```

Open the address Vite prints (usually `http://localhost:5173`), create an account, paste a repo link and press **Analyse repo**.

**Run the API tests** (Docker Desktop must be running)

```powershell
cd backend/api-service
./mvnw test
```

## Authors

- **Rohit** - Platform, API and Database
- **Sakthi** - Analysis pipeline
- **Venky** - Graph, architecture and scoring