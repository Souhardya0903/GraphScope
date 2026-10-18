# Local-first beta release work

1. Expanded API/UI integration: added map/change/target/proposal/workspace endpoints and input form; existing indexing uses the expanded extractor. Tested API validation and frontend submission/build.
2. Guided workflow, evidence presentation and cancellation: added before/after views, graph/evidence/gap summaries, explicit proposal confirmation, resource/workspace inputs and stale-response protection. Cancel stops the browser request; bounded server work may finish. Blocking API work runs in worker threads.
3. End-to-end verification: passed 102 Python checks, 21 frontend tests, and 2 real-browser journeys against production assets. See VERIFICATION.md.
4. Reproducible local distribution and dependency validation: added Windows/POSIX setup scripts, loopback single-origin serve/doctor commands, explicit allowed repository roots, Host/Origin checks and patched frontend tooling. Verified a fresh locked Python install with pip check/doctor, 4 API boundary tests, 21 frontend tests, production build and 2 browser journeys. npm audit reports zero vulnerabilities.
5. CI, cleanup, configuration and release documentation: added GitHub checks with a pinned isolated FalkorDB image, browser tests and audit; fixed snapshot counts/deletion and evidence normalization; added request IDs/timing without logging payloads; versioned 0.1.0b1. Local verification: 106 Python tests and 22 frontend tests passed. GitHub CI passed on a clean Linux runner: https://github.com/Souhardya0903/GraphScope/actions/runs/39124566407

The release target is a local-first beta. Public multi-user hosting still requires authentication, authorization and isolated repository processing.
