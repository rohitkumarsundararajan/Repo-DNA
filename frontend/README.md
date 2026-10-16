# RepoDNA UI (Vite + React + TypeScript)

Converted from the HTML/CSS/JS demo. Same look, same four views (sign in, submit, job status, results).

## Run
```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

## Structure
```
src/
  App.tsx                  view switching (auth -> submit -> status -> results)
  types.ts                 shared TypeScript types
  data/demo.ts             made-up demo data (replace with API responses)
  lib/utils.ts             helpers, URL validation, result JSON builder
  hooks/useJobSimulation   fake job timeline (replace with polling GET /jobs/{id})
  components/              Header, Helix, Auth/Submit/Status/Results views
  components/results/      Scores, Architecture map, Issues, Raw JSON panels
  styles/style.css         original stylesheet, unchanged
```

## Backend connection
- `vite.config.ts` proxies `/api`, `/auth`, and `/jobs` to `http://localhost:8080` (Spring Boot API).
- Authentication: `POST /auth/register` and `POST /auth/login` manage session tokens with automatic header injection.
- Jobs: `POST /jobs` for repository links and multipart ZIP submissions, `GET /jobs` for past history.
- Live Status: Polls `GET /jobs/{id}` for real-time progress through queued, running, and completed stages.
- Results: `GET /jobs/{id}/result` dynamically loads architecture graph, complexity hotspots, cycles, violations, and scores.
- Offline / Demo fallback: Seamlessly continues in demo mode if the backend service is offline.
