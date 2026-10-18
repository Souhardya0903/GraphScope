# Repository and service analysis (phases 1–7)

The analysis CLI maps source, identifies changes, and reports potential impact.
It runs locally without FalkorDB or model calls by default. It does not import
repository Python modules, execute JavaScript, load tsconfig plugins, check out
Git branches, or contact discovered service URLs. Backend/frontend work is deferred.

## Setup

Python dependencies remain those in `pyproject.toml` / `requirements.lock.txt`.
For JavaScript/TypeScript source parsing, install Node and run from this checkout:

```powershell
npm ci --prefix tools/javascript --ignore-scripts
```

The pinned TypeScript 5.9 compiler API parses `.js`, `.jsx`, `.ts`, and `.tsx` files.
This Node dependency is a source-analysis tool, not a frontend application.
It is needed only when the analyzed source includes JavaScript/TypeScript.

## Map and investigate a repository

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis map examples/commerce --output reports/commerce-map.json
.\.venv\Scripts\python.exe -m graphscope.analysis impact examples/commerce --target inventory.validate_stock --output reports/commerce-impact.json
```

`--target` is repeatable. Reports merge overlapping affected symbols/endpoints and
retain bounded evidence paths to individual targets. Tests are included by default.
Map output includes file hashes, revision/dirty metadata, unresolved calls and gaps.
Python `src/` layout is normalized to importable package names.

To store the extended map in the configured FalkorDB graph:

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis map examples/commerce --store --output reports/commerce-map.json
```

This stores resource accesses, metadata and call relationships alongside the existing
snapshot contracts. Its snapshot ID can be used with `graphscope.investigation`.
Snapshots previously indexed without tests/resources retain their coverage limits;
reindex using the new command to obtain the expanded capabilities.

## Estimate impact from actual changes

```powershell
# HEAD versus current tracked files and non-ignored untracked files
.\.venv\Scripts\python.exe -m graphscope.analysis changes . --output reports/changes.json

# HEAD versus the staging index
.\.venv\Scripts\python.exe -m graphscope.analysis changes . --head index --output reports/staged-changes.json

# Compare two committed revisions; resolve refs without switching the checkout
.\.venv\Scripts\python.exe -m graphscope.analysis changes . --base HEAD~1 --head HEAD --output reports/commit-impact.json
```

`changes` lists additions, deletions and modifications with changed line ranges.
Renames are conservatively analyzed as deleted/added or modified files; rename
identity is not guessed. Changed symbols are selected on both sides. `before`
retains deleted functions and their former callers; `after` describes the new map.
Imports, class attributes and other edits outside function bodies conservatively
select all functions in that file and add a review gap. Simple SQL `ALTER/CREATE/DROP
TABLE` changes select functions with matching literal SQL table accesses; database
identity and migration semantics remain inferred/review-required.

Configuration/schema files without supported mappings remain visible in
`change_gaps`. They must not be interpreted as having zero impact.
Git trees are read through object IDs without filters or hooks. Line-ending-only
changes are ignored. Unmerged indexes are rejected. Temporary source trees are
created beneath ignored `reports/analysis-tmp` and cleaned up after parsing.

## Investigate a proposed change before editing

```powershell
# Offline lexical candidates; always asks for confirmation
.\.venv\Scripts\python.exe -m graphscope.analysis propose examples/commerce "Change validate_stock to reject zero quantity"

# Optional model-assisted suggestion; sends description and bounded symbol catalog
.\.venv\Scripts\python.exe -m graphscope.analysis propose examples/commerce "Reject zero quantity during ordering" --provider ollama

# Confirm one or more exact qualified targets to calculate hypothetical impact
.\.venv\Scripts\python.exe -m graphscope.analysis propose examples/commerce "Reject zero quantity during ordering" --target inventory.validate_stock --confirm --output reports/proposal.json
```

Model assistance is optional, bounded to one request (30 seconds, at most 300
symbols / 45,000 catalog characters), and validates the suggested ID against the
catalog. It cannot confirm a target or supply graph findings. A model suggestion is
one candidate, not proof that every symbol relevant to a description was identified.
The source snippets, `.env` contents and full source files are not sent by this flow.

## Resource and test analysis

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis impact examples/workspace/stock --resource redis:inventory --output reports/resource-impact.json
```

The resource selector seeds every matching owner in the selected repository and
traces its callers. Resource identities are repository-local, not globally unique.
Supported Python conventions include requests/httpx/aiohttp module HTTP calls,
Redis/cache access methods, literal SQL table names, environment reads, and common
message publishing/subscription methods/decorators. JavaScript supports literal
global `fetch` calls. URL credentials, query strings and fragments are stripped;
SQL statements are reduced to table names. Dynamic identities remain gaps.

Conventions are labelled `inferred`; a variable named `cache` is not proof of a Redis
connection. Test links are resolved static caller paths (including imported Python
tests), not runtime coverage, test discovery, execution or proof of correctness.
Pytest fixtures, mocking, JS framework callback tests and parametrization are not
fully modeled. SQLAlchemy/ORM schemas and arbitrary query builders are not supported.

## Multiple services, repositories and languages

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis workspace examples/workspace/workspace.json --output reports/workspace-map.json
.\.venv\Scripts\python.exe -m graphscope.analysis workspace examples/workspace/workspace.json --service stock --target app.validate_stock --output reports/workspace-impact.json
```

The fixture verifies Python route → function and TypeScript caller → literal HTTP
request links, plus explicit broker/topic message dependencies. See
`examples/workspace/README.md`. Each manifest service has:

- A unique `id` and local `root`, resolved relative to the manifest.
- An HTTP(S) `base_url` origin, without credentials, query or path prefix.
- Optional `message_broker`: an explicit shared broker/namespace identity.
- Optional `revision`: a Git commit/ref or `index`; default `worktree`.

Roots can be separate repositories or subdirectories in a monorepo. HTTP links
require one matching origin, method and supported FastAPI route. Messaging links
require an identical declared broker identity and literal topic; the consumer is
treated as potentially dependent on the producer. Both carry evidence from both
sides and are inferred contracts, not observations of runtime traffic.

For automatic cross-service impact from one service's changes:

```powershell
.\.venv\Scripts\python.exe -m graphscope.analysis workspace path/to/workspace.json --changed-service stock --base HEAD --head worktree --output reports/workspace-changes.json
```

The other services are captured once at their manifest versions for both sides.
Deployment/version compatibility across repositories is not proven. The combined
workspace report is local; only individual repository snapshots can be stored in
FalkorDB by this CLI. No implicit topic-name or short-symbol-name cross-repository
matching is performed.

## Supported scope and remaining coverage

| Phase | Implemented scope | Remaining coverage |
|---|---|---|
| 1 | Python functions/method definitions, explicit class method calls, simple single-base lookup, imports, FastAPI routes, src layout, hashes/revision metadata | Dynamic instance/self/super dispatch, multiple inheritance, arbitrary decorators, other web frameworks |
| 2 | Worktree, staged and revision comparisons; line-to-symbol mapping; additions/deletions/renames conservatively retained | Precise rename attribution, general config-to-symbol semantic analysis |
| 3 | Multi-target before/after impact, deduplicated affected symbols/endpoints, source evidence and traversal limits | Runtime certainty, incremental indexing |
| 4 | Lexical or optional model suggestions with separate explicit target confirmation | Exhaustive natural-language intent interpretation |
| 5 | Literal resource accesses, simple SQL schema impact, static test caller links | ORM/query-builder semantics, comprehensive framework test linking, dynamic resource identities |
| 6 | Manifest-driven HTTP origin/method/route and broker/topic dependencies with two-sided evidence | Automatic deployment discovery, OpenAPI-only external services, arbitrary runtime routing |
| 7 | Explicit versioned multi-repository workspaces; Python and JS/TS function/import adapters | Additional languages, JS classes, re-exports, tsconfig aliases, CommonJS require, cross-language type analysis |

All reports remain `partial`: these are meaningful static capabilities across phases
1–7, not universal repository/service mapping. An empty path is not proof of safety.

Limits: 10,000 eligible files / 50 MB, at most 500 change targets, traversal depth
1–30 (default 12), paths 1–2,000 (default 500), and 20,000 traversal expansions.
Truncation/depth boundaries appear in reports. Narrow the source root for larger
repositories. Hidden directories, environments, node_modules, build outputs and
reports are excluded. `.env` and unsupported extensions are not read for analysis.


## Verification

```powershell
$env:GRAPHSCOPE_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests examples
```

The expanded local suite includes Git repositories created in disposable test
folders, parser/alias/shadowing checks, deleted-symbol and schema-change impact,
cross-language HTTP and broker contracts, cross-service Git changes, proposal ID
validation, traversal limits and FalkorDB resource/metadata/test-link persistence.
Provider-assisted proposals are mocked in these checks; no live model request is
needed. Integration tests create and delete isolated graphs.

Verified locally: **88 tests passed** with cloud integration enabled; Ruff passed.
One upstream Starlette/httpx deprecation warning remains.
