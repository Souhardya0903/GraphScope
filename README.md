# GraphScope

Understand the potential blast radius of a code change before making it.

GraphScope maps source dependencies, traces callers and affected API endpoints,
compares Git revisions, and inspects dependencies across declared service workspaces.
Findings include source locations, resolution rules, and explicit analysis limitations.

**Status:** local-first hackathon beta. Python and a subset of JavaScript/TypeScript
are supported. Results describe potential static impact, not guaranteed runtime behavior.

## What you can do

| Analysis mode | Purpose |
|---|---|
| Repository mapping | Explore functions, resolved calls, endpoints, and resource accesses. |
| Selected targets | Trace potential impact from one or more exact function names or a literal resource identity. |
| Proposed change | Describe an intended change, review candidate functions, and confirm targets before calculating impact. |
| Git changes | Map worktree, staged, or committed edits to symbols and inspect before/after impact. |
| Service workspace | Map declared services and infer HTTP/message dependencies, with service filtering and contract evidence. |

The React dashboard includes graph fitting, zoom/pan, node selection, dependency
evidence, grouped coverage reporting, and JSON export. Static test links identify
resolved caller relationships to tests; they do not execute tests or measure runtime coverage.

## Quick start

Requires Git, Python **3.11+**, and Node.js **22.12+**. Release verification uses Node 24.
Run from a source checkout so the dashboard and parser assets remain available.

```sh
git clone https://github.com/Souhardya0903/GraphScope.git
cd GraphScope
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe -m graphscope serve --port 8080
```

### Linux / macOS

```sh
sh scripts/setup.sh
.venv/bin/python -m graphscope serve --port 8080
```

Open **http://127.0.0.1:8080** and choose **Repository analysis**. Setup creates the
virtual environment, installs dependencies and the JavaScript parser, and builds the dashboard.

All five repository-analysis modes work without Docker, FalkorDB, or an LLM key.
The separate stored-snapshot investigation workflow requires FalkorDB.

For an external repository, allow its directory when launching:

```powershell
.\.venv\Scripts\python.exe -m graphscope serve --allow-root "D:\YourRepository"
```

Use `.venv/bin/python` on Linux/macOS. Repeat `--allow-root` for additional roots.
Bundled project examples are allowed by default. Keep the server terminal running;
use a hard browser refresh after rebuilding the frontend.

## Analyze your repository

Start the server with your repository directory allowed, then open the dashboard:

1. Choose an analysis mode and enter your repository's absolute path.
2. For target impact, enter an exact qualified function name from its map, or a
   literal resource identity. Use one selector at a time.
3. For a proposed change, describe the change, review candidate functions, and
   confirm the targets before calculating impact.
4. For Git changes, choose the base revision and compare against the worktree,
   staging index, or another revision.
5. For multiple services, provide a workspace JSON manifest. Inspect its map or
   select a service and target; alternatively select one changed service.

Workspace manifests have version `1` and a `services` array. Each service declares
an `id`, local `root`, and HTTP `base_url`. Optional `revision` pins source to a Git
ref or index; optional `message_broker` identifies a shared messaging namespace.
Service paths resolve relative to the manifest and must be under allowed roots.

Select graph nodes for dependency evidence, review coverage limitations, and export
JSON when you need the full report. Cross-service links are inferred contracts,
not observations of runtime traffic.

## Optional LLM suggestions

**Proposed change** supports offline lexical matching, Gemini, Ollama Cloud, and OpenAI.
Click **Describe a change**, choose a provider, and leave targets empty to request suggestions.
The UI asks permission to share the description and symbol catalog. Review the candidate,
select it, and explicitly confirm before calculating static impact. Confirmation does
not make another model request. Provider failures offer an offline fallback.

Create an ignored `.env` file at the checkout root if you need model or database
configuration. Preserve existing settings. Set the selected provider's key and a tool-capable model ID
available to your account:

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-model
# Alternatives:
# OLLAMA_API_KEY / OLLAMA_MODEL
# OPENAI_API_KEY / OPENAI_MODEL
```

Restart the server after changing configuration. Credentials stay on the server.
Proposal requests send a description, symbol names/IDs, and relative file paths;
they exclude source contents. Catalogs are limited to **300 functions / 45,000
characters**, with a 30-second model-request timeout. Larger repositories can use
offline matching or explicit targets. Provider access and quota are account-dependent.

LLMs suggest targets and manual checks. Source analysis and graph traversal establish
the reported dependencies; model text cannot supply dependency edges.

## CLI

Use the virtual environment's Python executable. The following syntax uses
placeholders: replace `REPOSITORY_PATH`, `QUALIFIED_FUNCTION`, and `MANIFEST_PATH`
with your own values.

```text
python -m graphscope.analysis map REPOSITORY_PATH --output reports/map.json
python -m graphscope.analysis impact REPOSITORY_PATH --target QUALIFIED_FUNCTION
python -m graphscope.analysis changes REPOSITORY_PATH --base HEAD --head worktree
python -m graphscope.analysis propose REPOSITORY_PATH "CHANGE DESCRIPTION"
python -m graphscope.analysis workspace MANIFEST_PATH
```

Run `python -m graphscope.analysis MODE --help` for command options. A confirmed
proposal requires explicit `--target` and `--confirm`. Git comparisons accept
`--head index` for staged edits or a commit/ref for another revision.

## Optional FalkorDB snapshots and investigations

FalkorDB stores snapshots for the separate **Stored snapshot investigation** workflow.
For a local Docker installation:

```sh
docker compose up -d --wait
```

For a local instance, add these settings to `.env`. For FalkorDB Cloud, use its
host, port, credentials, and TLS setting instead.

```dotenv
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_SSL=false
FALKORDB_GRAPH=graphscope
# FALKORDB_USERNAME=
# FALKORDB_PASSWORD=
```

Then verify connectivity:

```powershell
.\.venv\Scripts\python.exe scripts/check_falkordb.py
```

The check uses a disposable graph. To persist a repository map, add `--store` to
the analysis CLI map command. The stored map includes a snapshot `id` that can
be selected in the dashboard or passed to `python -m graphscope.investigation`.
Stored investigation supports direct deterministic analysis and optional model providers.
Source excerpts in that workflow are opt-in and checked against indexed hashes.

## Coverage and limits

- Python resolution supports explicit imports, unambiguous re-exports, package/submodule
  calls, and a bounded subset of class-method lookup and FastAPI routes.
- Dynamic dispatch, arbitrary decorators, nested functions, runtime-generated routing,
  and other unsupported patterns can leave dependencies unresolved.
- JavaScript/TypeScript analysis supports a subset of functions/imports and literal
  HTTP calls. Java and universal framework/language support are not implemented.
- Resource identities and cross-service contracts can be inferred and require review.
- Analysis coverage separates repository-wide limitations, unresolved calls inside
  found affected functions, and builtin calls. The scoped view does not prove other
  code is unrelated; unresolved incoming calls may hide additional dependents.
- Graph previews are bounded; exports preserve full report relationships. Traversal
  truncation and depth limits are explicitly reported.

An empty impact result does not establish safety. Analysis never imports or executes
repository source. This beta binds to loopback and assumes a trusted local operator;
public multi-user hosting, tenant isolation, and authentication are not implemented.

## Verification

Dependencies are declared in `pyproject.toml`. Setup installs known runtime and
development versions from `requirements.lock.txt`, then installs GraphScope without
re-resolving dependencies. This version snapshot is not an artifact-hashed,
cross-platform lockfile. Run tests
from the checkout root; pytest uses the ignored `reports/pytest` temporary directory.

After setup:

```powershell
.\.venv\Scripts\python.exe -m graphscope doctor
.\.venv\Scripts\python.exe -m ruff check src tests examples
.\.venv\Scripts\python.exe -m pytest tests/unit -q
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=1
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

Use `.venv/bin/python` on Linux/macOS. Browser tests launch their own server on
port 8765; keep it free. Tests using optional local third-party clones may be skipped
on a fresh checkout. FalkorDB integration tests require `GRAPHSCOPE_INTEGRATION=1`
and a configured reachable instance. Normal automated checks do not call paid models.

## Project layout

```text
frontend/                 React + TypeScript dashboard and browser tests
src/graphscope/
  ingestion/              Python AST extraction and dependency resolution
  analysis/               Maps, changes, proposals, impact, and service workspaces
  api/                    Local FastAPI endpoints and filesystem boundaries
  graph/                  FalkorDB snapshot persistence and queries
  investigation/          Bounded optional model/tool investigation
  models.py               Shared report and snapshot contracts
examples/commerce/        Bundled function/endpoint demonstration
examples/workspace/       Bundled Python/TypeScript service contracts
scripts/                  Setup and database verification
tools/javascript/         JavaScript/TypeScript source parser
tests/                    Unit, fixture, and integration checks
```

## How the pieces connect

```mermaid
flowchart LR
    UI[React dashboard] --> API[Local FastAPI API]
    CLI[Python CLI] --> Engine[Analysis engine]
    API --> Engine
    Engine --> Parser[Python AST / JS-TS parser]
    Parser --> Graph[Snapshot and dependency graph]
    Graph --> Impact[Impact traversal and evidence]
    Impact --> UI
    API --> LLM[Optional target suggestions]
    Graph --> DB[Optional FalkorDB persistence]
```

The dashboard lives in `frontend/`; API routes in `src/graphscope/api/` delegate to
`analysis/`. Python extraction uses `ingestion/`; JavaScript/TypeScript extraction
uses `tools/javascript/`. Offline reports use the extracted graph directly.
`graph/` and `investigation/` support stored-snapshot investigations. Setup scripts
install these components; tests validate their contracts and browser workflows.

## Troubleshooting

| Symptom | Action |
|---|---|
| Cannot reach API | Keep the server running and open its exact URL. |
| Old frontend | Rebuild with `npm --prefix frontend run build`, then hard-refresh. |
| Port 8080 busy | Launch with `--port 8081` and open that port. |
| External root rejected | Restart with `--allow-root` for the repository/workspace directories. |
| JS/TS parser unavailable | Run `npm ci --prefix tools/javascript --ignore-scripts`. |
| No Git changes found | Save the edit, use `worktree`, and inspect `git diff`. |
| Model catalog too large | Use a smaller source root, offline matching, or exact targets. |
| Model credentials changed | Restart the server; credentials are loaded on startup. |

## License

[MIT](LICENSE).
