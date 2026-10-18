# GraphScope

A Python dependency blast-radius assistant backed by FalkorDB.
Given a function, GraphScope will find potential callers and affected FastAPI
endpoints, with source evidence and explicit analysis gaps.

The synthetic commerce fixture (Stage 1) and static ingestion pipeline (Stage 2)
are implemented. Stage 3 adds cloud graph persistence and deterministic dependency
queries. Stage 4 adds bounded investigation tools, structured reports, Ollama Cloud, Gemini and OpenAI
adapter, and a local tool-loop test mode. The API and UI remain pending.

## Repository changes and cross-service impact

The expanded analysis CLI supports Git worktree/staged/revision comparisons,
before/after multi-target blast radius, confirmed proposed changes, literal resources,
static test links, and manifest-driven Python/TypeScript service workspaces.
See [ANALYSIS_GUIDE.md](ANALYSIS_GUIDE.md) for commands, supported subsets and limits.
Backend/frontend implementation remains deferred.

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis changes . --base HEAD --head worktree --output reports/change-impact.json
```

For JavaScript/TypeScript parsing only: `npm ci --prefix tools/javascript --ignore-scripts`.
No model calls or FalkorDB writes occur unless explicitly selected.

## Layout

```text
src/graphscope/
  config.py          # Application configuration
  models.py          # Shared snapshot, evidence, and report contracts
  ingestion/         # File discovery, AST extraction, symbol resolution
  graph/             # FalkorDB persistence and bounded queries
  investigation/     # Deterministic impact analysis and bounded agent tools
  api/               # FastAPI backend
  ui/                # Streamlit interface
examples/commerce/   # Synthetic FastAPI demo and independent behavior tests
tests/
  unit/              # Extractor and resolver behavior
  integration/       # FalkorDB and end-to-end behavior
  fixtures/          # Small source samples and expected relationships
scripts/             # Database connection verification
compose.yaml         # Local FalkorDB server and browser
```

## Development setup

Use Python 3.11 or newer. From PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Dependencies are declared in `pyproject.toml`. `requirements.lock.txt` records
the installed dependency versions verified on Windows with Python 3.15.0.
To reuse these versions in a fresh environment, replace the install command above
with `python -m pip install -r requirements.lock.txt -e ".[dev]"`.
This version snapshot is not a cross-platform lockfile with artifact hashes.
The graph client loads `.env`; FalkorDB must be provisioned separately. Local
Compose and FalkorDB Cloud are supported through the same connection settings.

The local `.venv` and `.env` have been created and are ignored by Git. In VS Code,
select `.venv\Scripts\python.exe` using **Python: Select Interpreter**.
You can use `.\.venv\Scripts\python.exe` directly if environment activation is blocked.

## Local FalkorDB

Install Docker Desktop with its WSL 2 backend and start it in Linux container mode.
Then run:

```powershell
docker compose up -d --wait
.\.venv\Scripts\python.exe scripts/check_falkordb.py
```

The database is available at `localhost:6379`; its browser is at
<http://localhost:3000>. Ports are bound to this computer only. Data is retained
in a Docker volume. The verification script writes, reads, and removes a temporary
graph; it does not modify application graphs. It loads `.env`, so it checks your
cloud instance when cloud credentials are configured there. For a local check,
set shell variables to localhost and its port, clearing cloud username/password.

Stop the service with `docker compose down`. The current image uses `latest`;
pin a tested image digest after the first successful startup.

Reference: [FalkorDB Docker setup](https://falkordb.github.io/docs-staging/operations/docker/).

## First milestone

Stage 0: FalkorDB Cloud connectivity was verified with a disposable graph write/read.
Stage 1: the commerce fixture is implemented; see [its README](examples/commerce/README.md)
for the dependency ground truth, run commands, and deliberate dynamic call.
Stage 2: AST extraction and scoped resolution work without database access.

## Test Stage 2

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m graphscope.ingestion examples/commerce --output reports/commerce-snapshot.json
.\.venv\Scripts\python.exe -m pytest tests/unit -q
```

Expected fixture extraction: **8 files, 8 functions, 5 resolved calls**, and these endpoints:

- `POST /orders`
- `POST /reservations`
- `GET /products`

Inspect the output:

```powershell
$snapshot = Get-Content reports/commerce-snapshot.json -Raw | ConvertFrom-Json
$snapshot.endpoints | Format-Table method, path
$snapshot.callsites | Where-Object file_path -eq 'dispatch.py' | Format-Table target_text, resolution_status, reason
```

Both call sites in `getattr(handlers, event_name)()` remain unresolved: the `getattr`
call itself and the call of its returned object. Other external/attribute calls
remain unresolved too: the current fixture has 5 unresolved sites in total.
Two gaps explain unsupported Pydantic class bodies. Counts are measured against
the current fixture, excluding tests by default. Add `--include-tests` to include
test functions as ordinary functions; static test-to-target classification is deferred.

The JSON includes file hashes, source lines, signatures, async flags, explicit
call evidence, route mount evidence, parse errors, and unresolved-site reasons.
Ingestion never imports or executes source and needs neither a running demo app
nor FalkorDB. Your demo's port (8080) does not affect extraction.

Supported: top-level functions, same-module calls, explicit absolute/relative
function imports and aliases, simple module aliases, literal FastAPI app/router
decorators, and module-level `include_router` calls with literal prefixes.
Unsupported: class/method dispatch, nested functions, arbitrary decorators,
re-exports, dynamic imports, computed prefixes, router mounts inside functions,
and full Python runtime name binding. Unsupported patterns remain gaps or unresolved
calls. The pipeline currently assumes no runtime monkey patching of namespace or
router objects. Stage 3 persists this extracted snapshot and queries its blast radius.

Resources and static test links come later. PR review and automatic execution of
analyzed repositories are outside the current scope.

## Stage 3: cloud graph storage and queries

The client reads connection settings from `.env` (shell environment values take
precedence). It supports username/password, TLS with certificate validation,
connection pooling, and timeouts. Credentials are never stored in snapshot data.

Index the synthetic fixture and inspect its blast radius:

```powershell
.\.venv\Scripts\python.exe -m graphscope.graph index examples/commerce --target inventory.validate_stock
```

Expected: `status: ready`, 8 files, 8 functions, 5 call edges, 3 endpoints.
The investigation returns `/orders` and `/reservations`, caller paths with evidence
IDs, unresolved calls, extraction gaps, and depth/path limits. `/products` is not
reachable from this target within the supported scope. Each index command creates
a new immutable snapshot; the output includes its `snapshot_id`.

Query an existing snapshot without reindexing:

```powershell
.\.venv\Scripts\python.exe -m graphscope.graph investigate YOUR_SNAPSHOT_ID inventory.validate_stock
.\.venv\Scripts\python.exe -m graphscope.graph investigate YOUR_SNAPSHOT_ID inventory.validate_stock --max-depth 1 --max-paths 1
```

Replace `YOUR_SNAPSHOT_ID` with the ID printed by indexing. Limits and truncation
are part of the result; a limited result does not establish safety. The target
itself is included when finding endpoints, including when it is a route handler.
Forward traversal and source retrieval are available through `GraphQueries.traverse`
and `GraphQueries.evidence(..., include_source=True)`. Source excerpts are checked
against indexed hashes, so changed or missing local source cannot silently appear
as evidence for an older snapshot. Source files are not uploaded to FalkorDB.

Bulk writes use batches of 200. Read queries require `ready` status and are scoped
to the chosen snapshot. A write claim prevents simultaneous builds of one ID;
repeating a successfully stored identical snapshot is idempotent. Failed/unfinished
builds remain hidden. Re-extract to get a fresh snapshot ID after a failed build.
Old snapshots are retained; no automatic cleanup or application-data deletion runs.

Cloud integration tests (create and delete their own uniquely named test graph):

```powershell
$env:GRAPHSCOPE_INTEGRATION = "1"
New-Item -ItemType Directory -Path reports -Force | Out-Null
$testPath = Join-Path (Get-Location) ('reports\stage3-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests/integration/test_falkordb_graph.py -q -p no:cacheprovider --basetemp $testPath
Remove-Item Env:GRAPHSCOPE_INTEGRATION
```

Expected: **4 passed** with the configured FalkorDB service reachable. Without the
opt-in flag these tests are skipped. Unit and fixture tests need no cloud connection.
The Stage 3 baseline passed **34 tests** with integration enabled. The existing
HTTP test client also emits a dependency deprecation warning.

Plain `python -m pytest -q` now allocates a fresh temporary directory under ignored
`reports/pytest-*` instead of the shared Windows temp folder. Pytest's optional cache
is disabled to avoid stale cache permissions. An explicitly supplied `--basetemp`
still takes precedence. Per-run temporary files remain under `reports/` for inspection.

Resources and static test links are not ingested yet; their lookup methods return
`supported: false` rather than claiming no impact. Snapshot revision/dirty metadata,
automatic recovery of abandoned builds remain future work.

## Stage 4: bounded investigation

Index once, then investigate that snapshot (PowerShell):

```powershell
$indexed = .\.venv\Scripts\python.exe -m graphscope.graph index examples/commerce | ConvertFrom-Json
.\.venv\Scripts\python.exe -m graphscope.investigation $indexed.snapshot_id "What should I check if validate_stock changes?" --target inventory.validate_stock --provider test --output reports/investigation.json
```

`test` runs a deterministic planner through real graph tools. It makes no LLM/API
requests and produces no model recommendations. Expected: both dependent POST routes,
two direct callers, one indirect caller, source references, five unresolved call
sites, and `agent.status: completed` with `agent.provider: test`. Completeness is
`partial`, because unresolved calls and unsupported class bodies remain visible.
Use `--provider none` (the default) to generate just the deterministic report.
Neither mode depends on the demo HTTP server or its port 8080.

For Ollama Cloud, set these entries in your ignored `.env`:

```dotenv
OLLAMA_API_KEY=your-key
OLLAMA_MODEL=your-direct-api-model-id
```

Use the exact model name listed by `https://ollama.com/api/tags` and choose a model
with tool calling available to your account. No local Ollama installation is needed.
The adapter uses the fixed `https://ollama.com/api/chat` endpoint; keys are sent in
the authorization header. Cloud usage is subject to your account's credits/limits.

Index the example first and capture its output (the indexing CLI has no `--output` flag):

```powershell
New-Item -ItemType Directory -Force reports | Out-Null
.\.venv\Scripts\python.exe -m graphscope.graph index examples/commerce --target inventory.validate_stock | Out-File -Encoding utf8 reports/commerce-index.json
$indexed = Get-Content reports/commerce-index.json -Raw | ConvertFrom-Json
.\.venv\Scripts\python.exe -m graphscope.investigation $indexed.snapshot_id "What should I review before changing validate_stock?" --target inventory.validate_stock --provider ollama --output reports/ollama-investigation.json
```

Check `agent.provider` is `ollama` and `agent.status` is `completed`. Status `failed`
or `limited` means the model did not complete; deterministic findings are still
retained for an explicit target. Questions and selected graph metadata are sent to
Ollama Cloud; source snippets remain excluded unless `--share-source` is supplied.
A live Ollama Cloud investigation completed against the commerce snapshot, returning model recommendations with source sharing disabled. Automated tests mock the provider API.

For Gemini, save these entries in your ignored `.env` (keep your key out of Git and chat):

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-account-model-id
```

Choose a function-calling model available on your account's free tier, then run:

```powershell
.\.venv\Scripts\python.exe -m graphscope.investigation $indexed.snapshot_id "What should I review before changing validate_stock?" --target inventory.validate_stock --provider gemini --output reports/gemini-investigation.json
```

Check `agent.provider` is `gemini` and `agent.status` is `completed`. If access or
quota fails, the report retains deterministic findings and records the failure.
The adapter uses Google's generateContent API with function calling. Free-tier
limits and data handling depend on your account and Google's current terms.

For OpenAI, save these entries in your ignored `.env`:

```dotenv
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-account-model-id
```

Choose a model available to your API account that supports Responses function calls.
Then run:

```powershell
.\.venv\Scripts\python.exe -m graphscope.investigation $indexed.snapshot_id "What should I review before changing validate_stock?" --target inventory.validate_stock --provider openai
```

The adapter uses [OpenAI Responses function calling](https://developers.openai.com/api/docs/guides/function-calling)
with strict function schemas and `store: false`. Live provider access, quota,
model compatibility, and billing depend on your API account. Adapter behavior is
tested with mocked HTTP responses; no live OpenAI call was made during implementation.

The model sees your question and selected graph/evidence slices. Source snippets are
excluded from model tool results unless you explicitly pass `--share-source`.
When enabled, excerpts may be sent to your selected provider and must match indexed file hashes.
`store: false` disables response application-state storage; it is not a claim of
zero data retention across all provider logging/policies. No full repository is sent.

Reports separate `graph_evidence`, `recommended_checks` (labelled `deterministic`
or `model`), `analysis_gaps`, and short tool activity events. Model output cannot
replace graph findings or switch an explicitly selected target. If a model fails,
verified deterministic findings remain available when `--target` was provided.
Without a target, unresolved/ambiguous selection requires clarification. A database
failure never produces a normal-looking fabricated report. Redis/resource analysis
and static test linking still return explicitly unsupported results.

Defaults: 6 model turns, 12 tool calls, 100 database reads, a 90-second investigation
deadline checked between operations, a 30-second per-model-request timeout, 60,000
context characters, 12,000 characters per tool result, and a 250,000-character report
cap. Traversal uses depth 8 and at most 30 paths for this service. Network timeouts
remain per blocking operation; this is not a process-level hard wall-clock kill.
The agent has no shell, arbitrary Cypher, file-path, source-execution, or write tool.

Run all tests, including real graph/tool/service integration but no paid model calls:

```powershell
$env:GRAPHSCOPE_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
```

Local implementation verification: **71 passed**, including additional Stage 4 tests retained locally and excluded from this commit. A fresh checkout contains the existing Stage 1–3 tests, so its test count will differ. One upstream HTTP test-client deprecation warning remains. Automated verification used mocked model APIs; Ollama Cloud was also verified separately with a live investigation.

Next: Stage 5 exposes these operations through the backend; it should stream tool
activity and results, not hidden model reasoning.

Architecture choices and their current limits are recorded in [ARCHITECTURE.md](ARCHITECTURE.md).
