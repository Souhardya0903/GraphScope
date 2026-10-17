# GraphScope

A Python dependency blast-radius assistant backed by FalkorDB.
Given a function, GraphScope will find potential callers and affected FastAPI
endpoints, with source evidence and explicit analysis gaps.

The synthetic commerce fixture (Stage 1) and static ingestion pipeline (Stage 2)
are implemented. Stage 3 adds cloud graph persistence and deterministic dependency
queries. The LLM investigator, API, and UI remain pending.

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
The full verified suite is **34 tests** with integration enabled. The existing
HTTP test client also emits a dependency deprecation warning.

Plain `python -m pytest -q` now allocates a fresh temporary directory under ignored
`reports/pytest-*` instead of the shared Windows temp folder. Pytest's optional cache
is disabled to avoid stale cache permissions. An explicitly supplied `--basetemp`
still takes precedence. Per-run temporary files remain under `reports/` for inspection.

Resources and static test links are not ingested yet; their lookup methods return
`supported: false` rather than claiming no impact. Snapshot revision/dirty metadata,
automatic recovery of abandoned builds, and the bounded LLM agent remain future work.

Architecture choices and their current limits are recorded in [ARCHITECTURE.md](ARCHITECTURE.md).
