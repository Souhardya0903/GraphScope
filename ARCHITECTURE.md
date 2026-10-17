# Architecture review: Stages 1–3

Reviewed 18 October 2026 against the code and fixture/cloud tests. This describes
the current CLI prototype, not a deployed multi-user application.

Release verification: installation from `requirements.lock.txt` in a fresh virtual
environment succeeded; `pip check`, Ruff for application/tests/fixtures, and all
34 tests passed, including cloud integration tests using a disposable graph.
One upstream HTTP test-client deprecation warning remains.

| Decision | Reason and verification | Limit |
| --- | --- | --- |
| Parse with Python AST without importing source | Avoids running analyzed application code. A fixture containing a top-level exception is parsed successfully without executing it. | Syntax cannot resolve all Python runtime bindings. Methods, callbacks, monkey patching, and unsupported constructs remain gaps/unresolved sites. |
| Collect definitions before resolving calls | Relative imports and aliases resolve independently of file ordering. Duplicate short names and shadowed bindings are tested. | Scope is module-level functions and a documented FastAPI subset. Unresolved sites are not proof of safety. |
| Pydantic contracts at the extraction boundary | Serialized snapshots round-trip through validation. Storage also checks IDs, ownership, and evidence references before writing. | These are internal contracts, not an untrusted public upload API. |
| FalkorDB is the authoritative query store | Reverse and forward traversals execute in FalkorDB, not a parallel in-memory graph. Cloud tests verify exact callers and affected endpoints. | Database unavailability prevents graph investigations; there is no fabricated fallback. |
| Caller → callee edges, reverse traversal for impact | Matches dependency semantics. Tests cover direct/indirect callers, unrelated products, and a target that is itself a handler. | Reachability means potential impact, not guaranteed failure. |
| Immutable, snapshot-scoped identities and publication gate | Nodes and traversed edges are isolated by snapshot. Bulk writes publish only after counts validate. Tests cover failed builds, identical retries, and competing writers. | Multi-query ingestion is not one database transaction. Failed builds remain stored but hidden; cleanup/recovery is manual. |
| Explicit per-query timeout, depth, and result limits | Queries use parameters; only a strictly validated integer enters a traversal range. Cycles, path caps, and cross-snapshot IDs are tested. | Path enumeration with sorting can still be expensive before truncation; the query timeout is the backstop. A timeout returns failure, not a complete report. |
| Store source references and hashes rather than whole files | Hash-checked snippets reject modified source. Both hash and snippet use the same read bytes. | Snippets require the original checkout at its indexed path. Sharing a cloud DB does not make source snippets available on another machine. |
| Separate synthetic application from GraphScope | Fixture HTTP tests run without FalkorDB or model credentials. The fake Redis boundary is explicit. | No real Redis resource graph or static test classification exists yet. |
| CLI before agent/API/frontend | Keeps deterministic correctness testable before model wording and web concerns are added. | No authentication, user/tenant isolation, uploads, or public API has been implemented. Snapshot isolation is not an authorization boundary. |

## Follow-up work

- Record repository identity, revision, and dirty state alongside the existing file hashes.
- Add source artifact storage or an explicit shared-checkout policy before hosted source viewing.
- Add a snapshot cleanup/recovery policy and schema migration/version handling before sustained use.
- Separate read-only query interfaces from writer interfaces before exposing agent tools.
- Add authentication, access control, quotas, and a total investigation budget before public hosting.
- Preserve deterministic graph results if a future model provider fails. Stream activity summaries,
  tool calls, and evidence, not hidden model reasoning.

TLS is supported with certificate validation when the database endpoint supports it.
An unencrypted connection must not be treated as production-ready for private source.
The Python dependency snapshot records versions verified on Windows/Python 3.15;
it is not a portable, artifact-hashed lockfile or a claim of testing every supported version.
