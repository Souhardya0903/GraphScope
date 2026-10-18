# Local-first beta verification

Story: select a local repository/change in the dashboard, send a validated API request,
parse source without executing it, render potential impact/evidence/gaps and export the report.

| Boundary | Verified evidence |
|---|---|
| Browser form to API | Two Playwright tests against the single-origin local beta server serving production assets |
| API to source analysis | Local API tests plus Git, parser, change and workspace regression fixtures |
| Analysis to FalkorDB | Disposable graph persistence/traversal/API integration tests |
| Report to UI | 22 frontend tests and real-browser endpoint/evidence/proposal/export assertions |
| Python regression | 106 local tests passed with cloud integration enabled (includes retained local Stage 4/analysis tests not committed earlier) |

The first E2E run exposed cold development-bundle timing. E2E now builds the frontend
and uses the production preview, matching release assets. Both browser tests passed.
No live model calls are required. Model transport failure behavior is mocked.
One upstream Starlette/httpx deprecation warning and existing React test-act warnings
remain. Patched tooling reports zero npm audit vulnerabilities. Local API path/origin checks and single-origin launcher browser checks passed.

Reproduce from the checkout:

```powershell
$env:GRAPHSCOPE_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test -- --maxWorkers=1
.\frontend\node_modules\.bin\playwright.cmd install chromium
npm --prefix frontend run test:e2e
```

Browser checks use port 8765 and terminate their own servers. Traces on failure
are written under ignored reports/playwright. On Linux, install Chromium with
`npx playwright install --with-deps chromium` from frontend/. The Python path defaults
to the checkout's .venv, overridable with GRAPHSCOPE_PYTHON. Git/FalkorDB credentials
remain operator configuration; never add .env to source control.
