# Local-first beta release work

1. Expanded API/UI integration: added map/change/target/proposal/workspace endpoints and input form; existing indexing uses the expanded extractor. Tested API validation and frontend submission/build.
2. Guided workflow, evidence presentation and cancellation: added before/after views, graph/evidence/gap summaries, explicit proposal confirmation, resource/workspace inputs and stale-response protection. Cancel stops the browser request; bounded server work may finish. Blocking API work runs in worker threads.
3. End-to-end verification: pending.
4. Reproducible local distribution and dependency validation: pending.
5. CI, cleanup, configuration and release documentation: pending.

The release target is a local-first beta. Public multi-user hosting still requires authentication, authorization and isolated repository processing.
