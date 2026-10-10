# Repository Analysis Timing

Measured 2026-10-09 on Windows with Python 3.12.10 and four parser workers. Each
directory was run once with `validation/real_repo_validation.py`; total time
covers parsing, graph construction, cycle detection, architecture detection,
violation detection, and scoring.

| Local code tree | Parsed files | Parse | Graph | Total |
| --- | ---: | ---: | ---: | ---: |
| `temp-madge-test` (small) | 2 | 0.650 s | 0.004 s | 0.657 s |
| `backend/analysis-worker` (medium) | 56 | 0.966 s | 0.097 s | 1.071 s |
| workspace root (largest) | 58 | 0.898 s | 0.098 s | 1.008 s |

Run from the workspace root:

```powershell
$py = Join-Path $env:TEMP 'repodna-worker-test312\Scripts\python.exe'
& $py backend\analysis-worker\validation\real_repo_validation.py `
  temp-madge-test backend\analysis-worker .
```

These are single-run local smoke timings, not a statistically stable benchmark.
The samples are workspace directories rather than independent remote clones,
and the medium and largest trees expose a similar number of supported source
files to the parser. Repeat on representative team repositories before using
these numbers for capacity planning.