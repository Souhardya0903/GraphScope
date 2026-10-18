# Run the local-first beta

Use a source checkout, Python 3.11+ and Node.js 22.12+ (Node 24 is used for release
verification). Git must be available. Keep the checkout for the parser and dashboard
assets; standalone wheel-only installation is not a supported beta distribution.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
./.venv/Scripts/python.exe -m graphscope serve --allow-root "D:\YourRepository"
```

Linux/macOS:

```sh
sh scripts/setup.sh
.venv/bin/python -m graphscope serve --allow-root /path/to/repository
```

Open http://127.0.0.1:8080. The built dashboard and API use one local origin.
Change the port with `--port`. The server binds only to loopback. Repeat
`--allow-root` for additional repository/workspace directories. Project examples
are allowed by default. Workspace manifests and their service roots must all be
under an allowed directory. Network share paths are rejected.

For Git changes choose a repository with an existing commit, then compare HEAD to
worktree, index, or another revision. For proposals, select candidates and explicitly
confirm targets. Review both before/after results, gaps, and limits; export JSON.
Analysis runs locally and does not require FalkorDB or a model. The older stored
snapshot/agent workflow needs FalkorDB settings in ignored .env. Models are opt-in;
the agent form defaults to no model calls. Never place provider keys in frontend
environment variables. `python -m graphscope doctor` checks installed components
and credential presence without printing values or making network requests.

For development use Vite on 5173 and Uvicorn on 8000. Host and Origin checks accept
loopback clients and those development origins, not arbitrary websites. Additional
repository paths can be configured with GRAPHSCOPE_ALLOWED_ROOTS as a JSON array.

This beta is for a trusted local operator. Do not bind it publicly or reverse-proxy
it to the internet. Multi-user authentication, authorization, isolated processing,
tenant storage/quotas and hosted retention policies are not implemented. Request
cancellation suppresses the browser result; bounded server work may finish.

No repository code is executed by analysis, but static coverage is partial. See
ANALYSIS_GUIDE.md for supported languages/frameworks and resource inference limits.


## Snapshots and diagnostics

The server logs request ID, route, status and elapsed time, never request bodies or
provider keys. X-Request-ID is returned for troubleshooting. Snapshot listing shows
only ready snapshots; metadata includes actual function/file/endpoint/resource counts.

Stored snapshots persist until explicitly deleted. To delete one, send DELETE to
`http://127.0.0.1:8080/api/snapshots/SNAPSHOT_ID` (add a graph query parameter only if
you used a non-default graph). This removes its entities, relationships and metadata.
There is no automatic retention policy in this local beta. Generated exports live
under ignored reports/ and can be removed when no longer needed.

CI runs on main/integration pushes and pull requests, using a pinned disposable
FalkorDB container rather than cloud credentials. It installs from locks, lints,
tests Python/frontend/browser flows and audits npm dependencies. CI does not invoke
paid models, publish a package, deploy a public site or alter your cloud graphs.
