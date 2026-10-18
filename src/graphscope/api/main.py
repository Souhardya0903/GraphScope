"""FastAPI backend – indexing, SSE-streamed agent investigations, evidence retrieval."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from graphscope import __version__
from graphscope.analysis.repository import analyze as ingest
from graphscope.api.analysis import router as analysis_router
from graphscope.api.safety import allowed_origins, allowed_path
from graphscope.graph.client import select_graph
from graphscope.graph.queries import GraphQueries
from graphscope.graph.repository import GraphRepository
from graphscope.investigation.agent import ModelFailure, run_investigation
from graphscope.investigation.gemini import GeminiModel
from graphscope.investigation.ollama import OllamaModel
from graphscope.investigation.providers import DeterministicPlanner, OpenAIModel
from graphscope.investigation.service import ClarificationRequired, build_report
from graphscope.investigation.tools import BudgetExceeded

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

app = FastAPI(
    title="GraphScope API",
    description="Codebase investigation and change impact analysis backed by FalkorDB.",
    version=__version__,
)
app.include_router(analysis_router)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])


@app.middleware("http")
async def local_origin_guard(request, call_next):
    origin = request.headers.get("origin")
    same_origin = str(request.base_url).rstrip("/")
    if origin and origin not in allowed_origins() and origin != same_origin:
        return JSONResponse(
            {"detail": "Origin is not allowed by the local server"}, status_code=403
        )
    request_id = uuid4().hex
    started = time.monotonic()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logging.getLogger("uvicorn.error").info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%d",
        request_id,
        request.method,
        request.url.path[:200],
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _graph():
    """Obtain a FalkorDB graph handle; raises 503 when unavailable."""
    try:
        return select_graph()
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc


def _make_model(provider: str, target: str | None = None):
    """Resolve provider string to a model instance (or None for deterministic mode)."""
    match provider:
        case "test":
            if not target:
                raise HTTPException(
                    status_code=400,
                    detail="provider=test requires a non-empty target.",
                )
            return DeterministicPlanner(target)
        case "openai":
            return OpenAIModel()
        case "gemini":
            return GeminiModel()
        case "ollama":
            return OllamaModel()
        case _:
            return None  # Deterministic only (no LLM)


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class IndexRequest(BaseModel):
    root: str = Field(
        default="examples/commerce",
        description="Relative or absolute path to the repository root to index.",
    )
    graph: str | None = Field(default=None, description="Override FALKORDB_GRAPH env.")


class IndexResponse(BaseModel):
    snapshot_id: str
    status: str
    files: int
    functions: int
    calls: int
    endpoints: int


class InvestigateRequest(BaseModel):
    snapshot_id: str = Field(description="Snapshot ID returned by /api/index.")
    question: str = Field(min_length=1, max_length=4000, description="Natural language question.")
    target: str | None = Field(
        default=None,
        description="Qualified name or function ID (e.g. inventory.validate_stock).",
    )
    provider: Literal["none", "test", "openai", "gemini", "ollama"] = Field(
        default="none",
        description="LLM provider: none | test | openai | gemini | ollama.",
    )
    share_source: bool = Field(
        default=False,
        description="Allow hash-verified source excerpts to be sent to the model.",
    )
    graph: str | None = Field(default=None, description="Override FALKORDB_GRAPH env.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    """Liveness probe – does not check FalkorDB."""
    return {"status": "ok", "version": __version__}


@app.post("/api/index", response_model=IndexResponse)
def index_repository(req: IndexRequest):
    """
    Parse a Python repository folder with the AST extractor and persist the
    resulting snapshot into FalkorDB. Returns the snapshot ID and coverage stats.
    """
    try:
        root = allowed_path(req.root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, detail="Repository path is missing or invalid") from exc
    if not root.exists():
        raise HTTPException(status_code=400, detail=f"Path not found: {req.root}")
    try:
        snapshot = ingest(root)
    except (OSError, SyntaxError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        graph = select_graph(req.graph)
        GraphRepository(graph).store(snapshot)
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc
    return IndexResponse(
        snapshot_id=snapshot.id,
        status="ready",
        files=len(snapshot.files),
        functions=len(snapshot.functions),
        calls=len(snapshot.calls),
        endpoints=len(snapshot.endpoints),
    )


@app.get("/api/snapshots")
def list_snapshots(graph: str | None = Query(default=None)):
    """List all snapshot IDs stored in the configured FalkorDB graph."""
    try:
        g = select_graph(graph)
        result = g.query(
            "MATCH (s:RepositorySnapshot {status:'ready'}) RETURN s.id, s.root, s.indexed_at ORDER BY s.indexed_at DESC LIMIT 50"
        )
        snapshots = [
            {"snapshot_id": row[0], "root": row[1], "indexed_at": row[2]}
            for row in result.result_set
        ]
        return {"snapshots": snapshots, "count": len(snapshots)}
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str, graph: str | None = Query(default=None)):
    """Retrieve metadata and coverage stats for a specific snapshot."""
    try:
        g = select_graph(graph)
        queries = GraphQueries(g)
        try:
            queries.ready(snapshot_id)
        except ValueError as exc:
            raise HTTPException(404, "Snapshot is missing or not ready") from exc
        counts = {}
        for label, key in (
            ("Function", "function_count"),
            ("File", "file_count"),
            ("Endpoint", "endpoint_count"),
            ("ResourceAccess", "resource_count"),
        ):
            counts[key] = queries.read(
                f"MATCH (n:{label} {{snapshot_id:$sid}}) RETURN count(n)", {"sid": snapshot_id}
            )[0][0]
        return {
            "snapshot_id": snapshot_id,
            **counts,
            "metadata": queries.snapshot_metadata(snapshot_id),
        }

    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc


@app.post("/api/investigate")
async def investigate(req: InvestigateRequest):
    """
    Run a bounded agentic investigation and stream live SSE events.

    Events emitted:
    - `agent_thought`   : Investigation plan step (tool name about to run)
    - `tool_call`       : Tool invocation result from FalkorDB
    - `graph_evidence`  : Final evidence section of the report
    - `report_complete` : Full ImpactReport JSON
    - `error`           : On failures
    """
    if not req.target and req.provider in ("none", "test"):
        raise HTTPException(
            status_code=400,
            detail="target is required when provider is 'none' or 'test'.",
        )

    async def event_stream():
        try:
            graph = select_graph(req.graph)
        except RedisError:
            yield _sse_event(
                "error", {"message": "FalkorDB unavailable; check local configuration"}
            )
            return

        try:
            model = _make_model(req.provider, req.target)
        except HTTPException as exc:
            yield _sse_event("error", {"message": exc.detail})
            return

        # Stream setup confirmation
        yield _sse_event(
            "agent_thought",
            {
                "step": "initializing",
                "detail": f"Investigation started for snapshot {req.snapshot_id}",
                "target": req.target,
                "provider": req.provider,
            },
        )

        # When no live model, we run deterministically and yield each tool step
        if model is None:
            try:
                yield _sse_event(
                    "agent_thought",
                    {
                        "step": "resolve_symbol",
                        "detail": f"Resolving target: {req.target}",
                    },
                )
                report = await run_in_threadpool(
                    build_report,
                    GraphQueries(graph),
                    req.snapshot_id,
                    req.target,
                    req.question,
                    req.share_source,
                )
                yield _sse_event(
                    "agent_thought",
                    {
                        "step": "trace_callers",
                        "detail": f"Found {len(report.graph_evidence.get('paths', []))} caller paths",
                    },
                )
                yield _sse_event(
                    "agent_thought",
                    {
                        "step": "find_endpoints",
                        "detail": f"Found {len(report.graph_evidence.get('potentially_affected_endpoints', []))} affected endpoints",
                    },
                )
                yield _sse_event(
                    "agent_thought",
                    {
                        "step": "get_analysis_gaps",
                        "detail": f"Found {len(report.analysis_gaps.get('unresolved_calls', []))} unresolved calls",
                    },
                )
                yield _sse_event("graph_evidence", report.graph_evidence)
                yield _sse_event("report_complete", json.loads(report.model_dump_json()))
            except ClarificationRequired as exc:
                yield _sse_event(
                    "error",
                    {
                        "message": "Target is ambiguous; clarification required.",
                        "candidates": exc.candidates,
                    },
                )
            except (ModelFailure, BudgetExceeded, ValueError, RedisError, OSError) as exc:
                yield _sse_event("error", {"message": str(exc)})
            return

        # Live model: intercept tool calls for streaming
        class StreamingProxy:
            """Wraps the model to emit SSE events for each tool call."""

            def __init__(self, inner):
                self._inner = inner
                self.events = []

            @property
            def provider_name(self):
                return getattr(self._inner, "provider_name", "custom")

            def complete(self, messages, tools, timeout):
                turn = self._inner.complete(messages, tools, timeout)
                for call in turn.calls or []:
                    self.events.append(
                        _sse_event(
                            "agent_thought",
                            {
                                "step": call.name,
                                "detail": f"Calling {call.name}",
                                "arguments": call.arguments,
                            },
                        )
                    )
                return turn

        proxy = StreamingProxy(model)

        # Since run_investigation is synchronous, we run it and yield pre-buffered events.
        # For a true async approach, the agent loop would need async hooks (future iteration).
        events_buffer = []
        report = None
        try:
            report = await run_in_threadpool(
                run_investigation,
                graph,
                req.snapshot_id,
                req.question,
                req.target,
                proxy,
                req.share_source,
            )
            events_buffer = proxy.events
        except ClarificationRequired as exc:
            yield _sse_event(
                "error",
                {
                    "message": "Target is ambiguous.",
                    "candidates": exc.candidates,
                },
            )
            return
        except (ModelFailure, BudgetExceeded, ValueError, RedisError, OSError) as exc:
            yield _sse_event("error", {"message": str(exc)})
            return

        for buffered_event in events_buffer:
            yield buffered_event

        if report:
            yield _sse_event(
                "tool_call",
                {
                    "tool": "get_analysis_gaps",
                    "unresolved_calls": len(report.analysis_gaps.get("unresolved_calls", [])),
                },
            )
            yield _sse_event("graph_evidence", report.graph_evidence)
            yield _sse_event("report_complete", json.loads(report.model_dump_json()))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/evidence")
def get_evidence(
    snapshot_id: str = Query(description="Snapshot ID."),
    evidence_ids: str = Query(description="Comma-separated evidence edge IDs."),
    include_source: bool = Query(default=False),
    graph: str | None = Query(default=None),
):
    """
    Return source evidence snippets for a list of evidence edge IDs.
    Source lines are included only when include_source=true.
    """
    try:
        g = select_graph(graph)
        queries = GraphQueries(g)
        ids = [e.strip() for e in evidence_ids.split(",") if e.strip()]
        if include_source:
            rows = queries.read(
                "MATCH (s:RepositorySnapshot {id:$sid,status:'ready'}) RETURN s.root",
                {"sid": snapshot_id},
            )
            if rows:
                allowed_path(rows[0][0])
        result = queries.evidence(snapshot_id, ids, include_source=include_source)
        return result
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: str, graph: str | None = Query(default=None)):
    """Delete all nodes belonging to a specific snapshot from FalkorDB."""
    try:
        g = select_graph(graph)
        g.query(
            "MATCH (n) WHERE n.snapshot_id = $sid OR (n:RepositorySnapshot AND n.id=$sid) DETACH DELETE n",
            {"sid": snapshot_id},
        )
        return {"deleted": True, "snapshot_id": snapshot_id}
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="FalkorDB unavailable; check local configuration"
        ) from exc


# API routes are registered first; built assets share the same loopback origin.
_frontend = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if (_frontend / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="dashboard")
