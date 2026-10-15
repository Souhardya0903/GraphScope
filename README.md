# GraphScope

A Python dependency blast-radius assistant backed by FalkorDB.
Given a function, GraphScope will find potential callers and affected FastAPI
endpoints, with source evidence and explicit analysis gaps.

This repository currently contains the project scaffold only. Extraction,
database queries, the investigator, API, and UI are not implemented yet.

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
examples/commerce/   # Synthetic demo application (to be implemented)
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
The configuration template is not loaded by application code yet. FalkorDB must
be provisioned separately; no database or model connection is made by this scaffold.

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
graph; it does not modify application graphs. It uses localhost defaults or shell
environment variables; it does not load `.env` automatically.

Stop the service with `docker compose down`. The current image uses `latest`;
pin a tested image digest after the first successful startup.

Reference: [FalkorDB Docker setup](https://falkordb.github.io/docs-staging/operations/docker/).

## First milestone

Parse two Python files, resolve one explicit imported call, persist the relationship
in FalkorDB, and retrieve it with its source location. Then add snapshot isolation,
route extraction, and deterministic reverse dependency traversal before an LLM.

Resources and static test links come later. PR review and automatic execution of
analyzed repositories are outside the current scope.
