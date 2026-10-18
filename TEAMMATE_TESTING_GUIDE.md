# GraphScope teammate testing guide

This guide uses examples included in Git, so it works on a fresh checkout without the author's local repositories, reports, database credentials, or API keys.

## 1. Get the latest version

Prerequisites: Git, Python 3.11+, and Node.js 22.12+ (Node 24 is used for release verification).

For a first checkout:

```sh
git clone https://github.com/Souhardya0903/GraphScope.git
cd GraphScope
git switch main
```

For an existing checkout, save or commit your own work before updating:

```sh
git switch main
git pull --ff-only origin main
```

Record the version you test:

```sh
git rev-parse --short HEAD
git status --short
```

The frontend redesign is included in commit `64e130a` and later main commits. The guide may be sent separately from the repository.

## 2. Install and launch

Run commands from the GraphScope checkout root. Setup installs Python dependencies, the JavaScript source parser, and the frontend, then builds the dashboard.

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\.venv\Scripts\python.exe -m graphscope doctor
.\.venv\Scripts\python.exe -m graphscope serve --port 8080
```

### Linux / macOS

```sh
sh scripts/setup.sh
.venv/bin/python -m graphscope doctor
.venv/bin/python -m graphscope serve --port 8080
```

Leave the server terminal running. Open **http://127.0.0.1:8080** and choose **Repository analysis**. Hard-refresh if an older dashboard is cached.

All five analysis modes below work without FalkorDB, Docker, or an LLM key. The separate **Stored snapshot investigation** workflow needs a configured FalkorDB instance and is outside this offline acceptance test.

Paths below are relative to the GraphScope checkout, because the server was launched there. You may instead enter absolute paths on your own computer. Do not copy another developer's `D:\GraphScope` path.

## 3. Repository mapping

| Field | Value |
|---|---|
| Analysis mode | Repository mapping |
| Repository path | `examples/commerce` |

Click **Analyze repository**.

Pass criteria:

- A report appears for the selected repository with a nonzero function count.
- The dependency graph contains function relationships.
- Expand **Affected functions and endpoints**: `inventory.validate_stock` is listed.
- Expand **Analysis coverage & limitations**: repository-wide totals, grouped reasons, and source examples can be inspected rather than silently hidden.
- **Export analysis JSON** downloads a readable JSON file.
- **Full analysis JSON** includes files, functions, call relationships, and repository metadata.

The map preview displays at most 200 paths; the export retains all report relationships. Do not compare its counts against the older ingestion-only examples in README: expanded analysis includes tests by default.

## 4. Selected targets

### A. Function impact

| Field | Value |
|---|---|
| Analysis mode | Selected targets |
| Repository path | `examples/commerce` |
| Qualified targets | `inventory.validate_stock` |
| Or resource identity | Empty |

Click **Analyze repository**.

Pass criteria:

- The graph identifies `inventory.validate_stock` as the change target.
- Affected endpoints include **POST `/orders`** and **POST `/reservations`**.
- **GET `/products`** is not reported as affected by this target.
- Expand the function list and select `orders.place_order`.
- **Dependency evidence** shows a source location and resolution rule, such as `explicit-python-binding-v1`.
- The export includes paths, analysis gaps, and traversal limits.
- In **Analysis coverage & limitations**, compare **Found affected functions / files** with **Whole repository**. Builtin calls are listed separately; repository-wide limitations are not presented as defects caused by the target.

### B. Resource impact

Keep **Selected targets**, then use:

| Field | Value |
|---|---|
| Repository path | `examples/workspace/stock` |
| Qualified targets | Empty |
| Or resource identity | `redis:inventory` |

Pass criteria: the result identifies the resource-owning `app.read_stock` function and potential impact on **GET `/stock/{item}`**. Resource identification is inferred from source conventions; it is not a live Redis connection check.

## 5. Proposed change

| Field | Value |
|---|---|
| Analysis mode | Proposed change |
| Repository path | `examples/commerce` |
| Qualified targets | Empty initially |
| Describe the proposed change | `Change validate_stock to reject zero quantity` |
| Confirmation checkbox | Unchecked |

Steps:

1. Click **Analyze repository**.
2. Review the suggested candidates.
3. Click **Use inventory.validate_stock**.
4. Confirm that the target field contains `inventory.validate_stock`.
5. Check **I confirm the explicit targets above**.
6. Click **Analyze repository** again.

Pass criteria:

- The first response requests target confirmation rather than silently choosing a blast radius.
- The confirmed report includes the same affected endpoints as the selected-target test.
- Editing the description or target clears the confirmation checkbox.

Candidate discovery in this workflow uses lexical matching. Naming the function makes this test reproducible; arbitrary natural-language intent is not guaranteed to resolve exhaustively.

### Optional model-assisted proposal test

The default proposal test above remains offline. To test an LLM, configure one provider in an ignored `.env` file at the checkout root, then restart the server:

```dotenv
# Set only the provider you intend to test. Use your own key and a supported model.
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-model
# Alternatives: OLLAMA_API_KEY / OLLAMA_MODEL, or OPENAI_API_KEY / OPENAI_MODEL.
```

1. Choose **Proposed change** (or click **Describe a change** in the page header).
2. Use `examples/commerce` and select your **Suggestion provider**.
3. Leave Qualified targets empty and describe a change, such as `Reject orders when inventory is insufficient`.
4. Read and check the catalog-sharing consent checkbox. Only the description, symbol names/IDs and relative file paths are sent; source contents and credentials are excluded.
5. Click **Analyze repository**. Expect a suggested repository target or a request for clarification, not a calculated blast radius.
6. Select a candidate, check target confirmation, and run again. This second request calculates static impact without another model call.
7. If the provider fails or lacks configuration, verify that the visible error offers **Use offline suggestions**. Switch to it, name `validate_stock` in the description, and rerun.

Provider calls may consume quota. Model-assisted suggestions have a 300-symbol / 45,000-character catalog limit and a 30-second request timeout. Use the small commerce example for this test. Large repositories can still use offline suggestions or explicit targets.

## 6. Git changes

This test requires a checkout with an existing Git commit. Start without unrelated edits to the example files.

Open `examples/commerce/inventory.py`. Insert this comment **inside** `validate_stock`, directly above its return statement, and save:

```python
def validate_stock(product_id: str, quantity: int) -> bool:
    # Temporary GraphScope verification change
    return quantity > 0 and read_inventory(product_id) >= quantity
```

Use:

| Field | Value |
|---|---|
| Analysis mode | Git changes |
| Repository path | `examples/commerce` |
| Base revision | `HEAD` |
| Compare with | `worktree` |

Pass criteria:

- The report identifies the edited file and `inventory.validate_stock` as a changed symbol.
- **Snapshot side** lets you inspect both **Before changes** and **After changes**.
- Both sides retain relevant caller and endpoint relationships.
- A comment changes the source file without changing behavior, so identical dependency relationships are expected.

Remove only the temporary comment and rerun. With no other eligible changes in the commerce example, the report should state that no eligible changes were found.

Optional staged test: reinsert the comment, stage only `examples/commerce/inventory.py`, select `index` in **Compare with**, and repeat. Unstage that file and remove the temporary comment afterward. Avoid undoing unrelated work.

## 7. Service workspace

The bundled manifest describes Python stock/worker services and a TypeScript client. Its service URLs are illustrative; those applications do not need to run.

### A. Map all services

| Field | Value |
|---|---|
| Analysis mode | Service workspace |
| Workspace manifest path | `examples/workspace/workspace.json` |
| Service ID | Empty |
| Qualified targets | Empty |
| Changed service ID | Empty |
| Base revision | `HEAD` |
| Compare with | `worktree` |

Click **Analyze repository**.

Pass criteria:

- The workspace overview shows stock, client, and worker, with nonzero aggregate function counts.
- The graph includes service-prefixed function names and inferred HTTP/message dependencies.
- Use **Service view** or a service card to inspect one service; counts and graph update to that service.
- Expand **Inferred service contracts** to inspect dependency direction, source locations, confidence, and matching rules.
- Export or inspect **Full analysis JSON** for the complete `snapshots`, `service_links`, and `service_gaps`.

### B. Cross-service target impact

Keep the same manifest and set:

| Field | Value |
|---|---|
| Service ID | `stock` |
| Qualified targets | `app.validate_stock` |
| Changed service ID | Empty |

Pass criteria: the result includes the selected stock target, the stock route, and the client's potential dependency through the declared HTTP contract. Cross-service links are inferred static contracts, not observed network traffic.

### C. Cross-service Git impact

Insert a temporary comment inside `validate_stock` in `examples/workspace/stock/app.py`, then save.

| Field | Value |
|---|---|
| Service ID | Empty |
| Qualified targets | Empty |
| Changed service ID | `stock` |
| Base revision | `HEAD` |
| Compare with | `worktree` |

Pass criteria: the report identifies stock as the changed service and provides before/after potential impact. Remove the temporary comment afterward.

Do not combine explicit Service ID/target input with Changed service ID in the same request.

## 8. UI and error checks

| Action | Expected result |
|---|---|
| Enter a nonexistent repository path | A visible error; no successful report |
| Use target `does.not.exist` in commerce | A target validation error |
| Edit repository or analysis inputs after success | Previous results clear |
| Inspect a long graph label | Text stays inside its card; hovering exposes the full name |
| Select a node | It is highlighted and relevant evidence is available |
| Tab to a graph node and press Enter | The node can be selected without a mouse |
| Zoom in, then click Fit graph | The graph returns to its fitted view |
| Drag the graph background | The graph pans |
| Narrow browser to about 390 pixels | Setup and results stack without horizontal page overflow |
| Cancel a running analysis, if long enough | Cancellation is visible and its late result is not displayed |
| Switch to Stored snapshot investigation | No prefilled commerce question or target appears |

Cancellation stops waiting in the browser; server work already running may finish.

## 9. Optional automated checks

Run in another terminal from the checkout root. Frontend checks do not need cloud credentials:

```sh
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=1
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

Browser tests start their own server on port **8765**. Keep that port free. Tests using optional ignored Click/algorithms clones may be skipped on a fresh checkout; the bundled commerce tests should run.

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| Failed to fetch / Cannot reach API | Keep the server terminal running; open its exact URL, normally `http://127.0.0.1:8080` |
| Old layout | Rebuild the frontend and hard-refresh the browser |
| Address already in use | Start with `--port 8081` and open `http://127.0.0.1:8081` |
| Repository path rejected | Bundled examples are permitted by default. For external repositories, restart with `--allow-root "/absolute/path/to/repository"` |
| JavaScript parser unavailable | Run `npm ci --prefix tools/javascript --ignore-scripts` |
| No Git changes detected | Save the edit inside the tested function, use `worktree`, and check `git diff` |
| FalkorDB errors | Use Repository analysis for these tests; stored snapshot investigation has separate database requirements |

## 11. Share your results

Copy and fill in:

```text
Commit:
Operating system:
Python version:
Node version:
Browser/version:

Repository mapping: PASS / FAIL
Selected function impact: PASS / FAIL
Resource impact: PASS / FAIL
Proposed change: PASS / FAIL
Git changes: PASS / FAIL
Workspace mapping: PASS / FAIL
Workspace target impact: PASS / FAIL
Workspace Git impact: PASS / FAIL
Desktop graph / keyboard controls: PASS / FAIL
Narrow layout: PASS / FAIL
Error handling: PASS / FAIL

Failure details:
- Mode and exact inputs:
- Steps to reproduce:
- Expected vs actual behavior:
- Error text / server log excerpt:
- Screenshot or exported JSON filename:
```

Do not include `.env` files, API keys, database passwords, or private source in shared diagnostics.

## Interpreting the findings

Results describe **potential static impact** and remain partial. Unresolved calls and coverage gaps are expected for unsupported patterns. An empty impact result does not establish safety. Static test links are source relationships, not executed tests or runtime coverage. Passing this guide verifies these supported workflows; it does not establish universal mapping of every repository or service.
