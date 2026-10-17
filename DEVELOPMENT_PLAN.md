# GraphScope Development Plan & Incremental Verification Guide

GraphScope is an AI-assisted codebase investigation and dependency blast-radius assistant powered by **FalkorDB**, a **FastAPI backend**, an **agentic investigation engine**, and a **React frontend**.

This document outlines the architecture, data models, agent loop, and an **incremental stage-by-stage implementation roadmap**. Each stage defines specific deliverables and concrete verification checks to ensure correctness before proceeding.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |         React Frontend (Vite)         |
                      |  - Live Agent Reasoning Stream (SSE)  |
                      |  - Interactive Blast Radius Graph     |
                      |  - Source Code & Line Evidence Viewer |
                      |  - Analysis Gaps & Blind-Spots Drawer |
                      |  - Exportable Impact Report (MD/JSON) |
                      +-------------------+-------------------+
                                          | HTTP / SSE
                      +-------------------v-------------------+
                      |         FastAPI Backend (/api)        |
                      |  - /api/index (AST Ingestion)         |
                      |  - /api/investigate (Agent SSE Stream)|
                      |  - /api/evidence & /api/snapshots     |
                      +-------------------+-------------------+
                                          |
                      +-------------------v-------------------+
                      |      Agentic Investigation Core       |
                      |  - Bounded Multi-Step Tool Loop       |
                      |  - Strict Separation of Evidence      |
                      |    (Graph Facts vs Model Suggestions) |
                      +---------+-------------------+---------+
                                |                   |
             7 Bounded Tools    |                   | Exact Source Lines
     +--------------------------v---+         +-----v-----------------+
     | resolve_symbol               |         |  Target Repository    |
     | trace_callers (Reverse)      |         |  (e.g., Python AST,   |
     | trace_dependencies (Forward) |         |   FastAPI App, Tests) |
     | find_endpoints               |         +-----------------------+
     | find_related_tests           |
     | get_source_evidence          |
     | get_analysis_gaps            |
     +--------------+---------------+
                    | Cypher Queries
     +--------------v---------------+
     |        FalkorDB Engine       |
     |  - RepositorySnapshot        |
     |  - Function / Endpoint Nodes |
     |  - CALLS / HANDLED_BY Edges  |
     |  - USES_RESOURCE / EXERCISES |
     +------------------------------+
```

---

## FalkorDB Graph Schema

### Nodes
| Label | Properties | Description |
| :--- | :--- | :--- |
| `RepositorySnapshot` | `id, repository_id, revision, indexed_at, parser_version` | Point-in-time isolation for the graph |
| `File` | `id, relative_path, content_hash, parse_status` | Source code file representation |
| `Function` | `id, qualified_name, name, module, start_line, end_line, signature, is_async` | Functions & async handlers |
| `Endpoint` | `id, method, path, framework` | HTTP route entry point (e.g., `POST`, `/orders`) |
| `Resource` | `id, name, resource_type, declaration_source` | External dependencies (e.g., `Redis`, `PostgreSQL`) |
| `Test` | `id, qualified_name, file_path, discovery_method` | Unit & integration test functions |
| `CallSite` | `id, file_path, line, target_text, resolution_status` | Call locations (flagged as `resolved` or `unresolved`) |

### Edges
| Edge Type | From $\to$ To | Key Properties | Description |
| :--- | :--- | :--- | :--- |
| `CONTAINS` | `RepositorySnapshot` $\to$ `File` | - | Snapshot boundary |
| `DEFINES` | `File` $\to$ `Function` \| `Test` | - | Module symbol definition |
| `HANDLED_BY` | `Endpoint` $\to$ `Function` | - | Route handler mapping |
| `CALLS` | `Function` $\to$ `Function` | `file_path, line, snapshot_id, resolution_type` | Static call relationship |
| `USES_RESOURCE` | `Function` $\to$ `Resource` | `declaration_source, line` | Adapter or resource access |
| `EXERCISES` | `Test` $\to$ `Function` | `discovery_method` | Statically linked test target |
| `HAS_CALLSITE` | `Function` $\to$ `CallSite` | - | Call occurrence (tracks gaps) |

---

## Incremental Stages & Verification Roadmap

Current progress (18 October 2026): Stage 0 cloud connectivity verified. Stage 1
commerce fixture implemented and verified with 12 passing tests. Stage 2 contracts,
discovery, two-pass call resolution, router extraction, JSON CLI, and 11 unit tests
are implemented. Its Redis adapter
is an explicitly documented in-memory stand-in; no live Redis or resource graph
declaration is implemented. Stage 3 core storage, indexes, bounded forward/reverse
queries, endpoint lookup, unresolved-gap lookup, evidence/hash checks, and snapshot
isolation are implemented and verified against FalkorDB Cloud. Full suite: 34 passing
tests with integration enabled. Resource/test queries explicitly report unsupported
until those entity types are ingested. Stage 4 tools, deterministic structured
reports, bounded orchestration, local test planner, and Ollama Cloud/Gemini/OpenAI adapters
are implemented. Provider transport is mocked in automated tests; live model access
requires OLLAMA_API_KEY/OLLAMA_MODEL, GEMINI_API_KEY/GEMINI_MODEL, or OPENAI_API_KEY/OPENAI_MODEL. Stage 5 and subsequent stages remain pending.
Stage 4 local verification: 71 tests passed (Stage 4 test files retained locally, excluded from this commit) with cloud integration enabled, and the CLI
local tool-loop mode returned the expected two commerce endpoints. Live Ollama Cloud access completed with source sharing disabled. Live Gemini/OpenAI access remains unverified.

### Stage 0: Environment & FalkorDB Verification
**Goal:** Ensure local Python virtual environment, dependencies, Docker container, and FalkorDB connectivity are verified.

- **Deliverables:**
  - Provision FalkorDB container via `compose.yaml`.
  - Validate environment variables (`FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_PASSWORD`).
  - Run verification script `scripts/check_falkordb.py`.
- **Verification Check:**
  ```powershell
  docker compose up -d --wait
  .\.venv\Scripts\python.exe scripts/check_falkordb.py
  ```
  *Expected Output:* `FalkorDB graph write/read passed.`

---

### Stage 1: Ground-Truth Synthetic Target (`examples/commerce`)
**Goal:** Create a clean, self-contained synthetic FastAPI commerce service with known topology, ground truth relationships, and deliberate blind-spots.

- **Deliverables:**
  - `examples/commerce/app.py`: FastAPI entry point with router includes.
  - `examples/commerce/orders.py`: `POST /orders` $\to$ `create_order` $\to$ `place_order` $\to$ `validate_stock`.
  - `examples/commerce/reservations.py`: `POST /reservations` $\to$ `reserve_stock` $\to$ `validate_stock`.
  - `examples/commerce/inventory.py`: `validate_stock` $\to$ `read_inventory` $\to$ `Redis` adapter.
  - `examples/commerce/products.py`: `GET /products` $\to$ `list_products` (unconnected to `validate_stock`).
  - `examples/commerce/dispatch.py`: Dynamic call site (`getattr(handlers, event_name)()`) as intentional unresolved gap.
  - `examples/commerce/tests/test_commerce.py`: Pytest tests exercising order and inventory logic.
- **Verification Check:**
  ```powershell
  .\.venv\Scripts\pytest examples/commerce/tests
  ```
  *Expected Output:* All tests in `examples/commerce` pass independently.

---

### Stage 2: Pydantic Data Contracts & AST Ingestion Engine
**Goal:** Statically discover Python files, parse AST, extract FastAPI routes and symbols, resolve local & imported calls, and capture unresolved dynamic calls.

- **Deliverables:**
  - `src/graphscope/models.py`: Data contracts (`Snapshot`, `FunctionNode`, `EndpointNode`, `CallSiteNode`, `EvidenceEdge`, `ImpactReport`).
  - `src/graphscope/ingestion/discovery.py`: Scans directories ignoring virtualenvs, cache, and hidden folders.
  - `src/graphscope/ingestion/extractor.py`: AST visitor capturing function signatures, line spans, calls, imports, and `@app`/`@router` route decorators.
  - `src/graphscope/ingestion/resolver.py`: Resolves same-module calls, imported functions, and simple aliases; flags dynamic calls (`getattr`, `eval`) as `unresolved`.
  - `src/graphscope/ingestion/pipeline.py`: Orchestrates discovery + extraction + resolution into an in-memory graph representation.
- **Verification Check:**
  - Create `tests/unit/test_extractor.py` and `tests/unit/test_resolver.py`.
  ```powershell
  .\.venv\Scripts\pytest tests/unit
  ```
  *Expected Output:*
  - Extracted routes match `POST /orders`, `POST /reservations`, `GET /products`.
  - Resolved call edge `place_order -> validate_stock` with exact line numbers.
  - Flagged 1 unresolved `CallSite` from `dispatch.py`.

---

### Stage 3: FalkorDB Graph Layer & Parameterized Cypher Queries
**Goal:** Persist the ingested graph snapshot into FalkorDB and execute reverse/forward traversals using Cypher.

- **Deliverables:**
  - `src/graphscope/graph/client.py`: Thread-safe FalkorDB client with timeout controls.
  - `src/graphscope/graph/repository.py`: Bulk ingestion of nodes, edges, snapshot isolation, and indices (`INDEX ON :Function(id)`).
  - `src/graphscope/graph/queries.py`: Parameterized Cypher queries:
    1. Reverse caller traversal: `MATCH p=(c:Function)-[:CALLS*1..8]->(t:Function {id: $id}) RETURN p LIMIT 100`
    2. Endpoint reverse lookup: `MATCH (e:Endpoint)-[:HANDLED_BY]->(h:Function) ...`
    3. Forward callee traversal: `MATCH p=(f:Function {id: $id})-[:CALLS*1..8]->(callee:Function) ...`
    4. Resource caller lookup: `MATCH (f:Function)-[:USES_RESOURCE]->(r:Resource {name: $res}) ...`
    5. Test exercise lookup: `MATCH (t:Test)-[:EXERCISES]->(target:Function) ...`
    6. Analysis gaps lookup: `MATCH (f:Function)-[:HAS_CALLSITE]->(cs:CallSite {resolution_status: 'unresolved'}) ...`
- **Verification Check:**
  - Create `tests/integration/test_falkordb_graph.py`.
  ```powershell
  .\.venv\Scripts\pytest tests/integration/test_falkordb_graph.py
  ```
  *Expected Output:*
  - Ingestion into temporary FalkorDB test graph succeeds.
  - Reverse traversal from `validate_stock` retrieves `place_order`, `create_order`, `reserve_stock`.
  - Reverse endpoint lookup identifies `POST /orders` and `POST /reservations`.
  - Verifies `GET /products` has 0 paths to `validate_stock`.

---

### Stage 4: Bounded Investigation Tools & Agent Engine
**Goal:** Build the agentic investigation loop over FalkorDB using bounded tools, natural language target resolution, and structured impact reporting.

- **Deliverables:**
  - `src/graphscope/investigation/tools.py`:
    - `resolve_symbol(query, snapshot_id)`
    - `trace_callers(target_id, max_depth)`
    - `trace_dependencies(source_id, max_depth)`
    - `find_endpoints(function_ids)`
    - `find_related_tests(function_ids)`
    - `get_source_evidence(file_path, start_line, end_line)`
    - `get_analysis_gaps(function_ids)`
  - `src/graphscope/investigation/agent.py`:
    - Agentic tool loop with bounded steps (max iterations).
    - Multi-provider support (Gemini, OpenAI, Anthropic, or local LLM via env config).
    - Deterministic fallback mock agent (ensuring CI/test execution without requiring paid API keys).
  - `src/graphscope/investigation/service.py`: Generates the structured `ImpactReport` with clear separation:
    1. *Graph Evidence* (FalkorDB verified paths and line citations).
    2. *Agent Recommendations* (boundary tests to run, review priorities).
    3. *Analysis Gaps* (unresolved dynamic calls and caveats).
- **Verification Check:**
  - Local-only verification: `tests/integration/test_agent_investigation.py` was created and run but excluded from the Stage 4 implementation commit.
  ```powershell
  .\.venv\Scripts\pytest tests/integration/test_agent_investigation.py
  ```
  *Expected Output:*
  - Test 1: Change impact on `validate_stock` returns both endpoints, test suggestions, and source lines.
  - Test 2: Dependency incident on `Redis` finds reachable routes and advises timeout/fallback checks.
  - Test 3: Unresolved dynamic call is prominently surfaced in `analysis_gaps`.

---

### Stage 5: FastAPI Backend & SSE Streaming API
**Goal:** Expose repository indexing and real-time agent investigations over HTTP and Server-Sent Events (SSE).

- **Deliverables:**
  - `src/graphscope/api/main.py`:
    - `POST /api/snapshots/index`: Triggers AST extraction and FalkorDB storage.
    - `POST /api/investigate`: Runs agentic investigation, streaming thought steps and tool calls via SSE.
    - `GET /api/snapshots`: Lists available indexed snapshots.
    - `GET /api/evidence`: Serves source snippets with syntax metadata.
- **Verification Check:**
  - Create `tests/integration/test_api.py`.
  ```powershell
  .\.venv\Scripts\pytest tests/integration/test_api.py
  ```
  *Expected Output:*
  - Endpoint returns HTTP 200 and streaming events `event: agent_thought`, `event: tool_call`, `event: report_complete`.

---

### Stage 6: Modern React UI (`frontend/`)
**Goal:** Build a dark-mode, responsive web application for interacting with the agent, visualizing the FalkorDB blast radius graph, and inspecting source evidence.

- **Deliverables:**
  - React + Vite + TypeScript application in `frontend/`.
  - **Live Agent Reasoning Stream**: Real-time display of agent thoughts, tool invocations, and FalkorDB query results.
  - **Interactive Blast Radius Canvas**: SVG/Canvas dependency graph (Endpoints $\to$ Callers $\to$ Target $\to$ Resource $\to$ Tests).
  - **Source Evidence Drawer**: Syntax-highlighted code inspector with exact line highlights.
  - **Analysis Gaps Warning Panel**: Highlights dynamic calls and blind spots.
  - **Report Exporter**: Markdown and JSON export for PR reviews.
- **Verification Check:**
  - Run frontend development server:
  ```powershell
  cd frontend
  npm run build
  ```
  *Expected Output:* Production bundle builds cleanly with zero TypeScript errors.

---

### Stage 7: End-to-End Verification & Documentation
**Goal:** Complete system verification across the whole stack and comprehensive README update.

- **Deliverables:**
  - End-to-end demo script and documentation.
  - Update `README.md` with instructions for running Docker, backend, and React UI.
  - Recorded verification test suite covering unit, integration, and agent workflows.
- **Verification Check:**
  ```powershell
  .\.venv\Scripts\pytest
  ```
  *Expected Output:* Complete test suite passes with 100% green status.
