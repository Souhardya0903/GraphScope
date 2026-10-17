"""Expose validated graph and source-evidence operations to the investigator."""

import json
import time

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from graphscope.graph.queries import GraphQueries


class BudgetExceeded(RuntimeError):
    pass


class BudgetedQueries(GraphQueries):
    """Enforce a query count and total deadline, including internal helper reads."""

    def __init__(self, graph, max_queries=100, seconds=90):
        super().__init__(graph)
        self.query_count = 0
        self.max_queries = max_queries
        self.deadline = time.monotonic() + seconds

    def read(self, query, params=None):
        remaining = self.deadline - time.monotonic()
        if self.query_count >= self.max_queries or remaining <= 0:
            raise BudgetExceeded("Investigation graph/time budget exhausted")
        self.query_count += 1
        return self.graph.ro_query(
            query, params or {}, timeout=max(1, min(5000, int(remaining * 1000)))
        ).result_set


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SymbolArgs(Arguments):
    query: str = Field(min_length=1, max_length=300)


class TraceArgs(Arguments):
    function_id: str = Field(min_length=1, max_length=1024)
    max_depth: int = Field(default=8, ge=1, le=8)
    max_paths: int = Field(default=30, ge=1, le=30)


class FunctionArgs(Arguments):
    function_ids: list[str] = Field(max_length=100)


class EvidenceArgs(Arguments):
    evidence_ids: list[str] = Field(max_length=50)


class GapArgs(Arguments):
    pass


class ResourceArgs(Arguments):
    resource_id: str = Field(min_length=1, max_length=1024)


TOOL_ARGUMENTS = {
    "resolve_symbol": (
        SymbolArgs,
        "Find candidate functions in the bound snapshot; ask for clarification if ambiguous.",
    ),
    "trace_callers": (TraceArgs, "Find reverse caller paths and traversal limits."),
    "trace_dependencies": (TraceArgs, "Find forward callee paths and traversal limits."),
    "find_endpoints": (FunctionArgs, "Find endpoints handled by these functions."),
    "find_related_tests": (
        FunctionArgs,
        "Check static test-link availability; currently unsupported.",
    ),
    "get_source_evidence": (
        EvidenceArgs,
        "Retrieve evidence by indexed IDs; source requires operator opt-in.",
    ),
    "get_analysis_gaps": (GapArgs, "Get unresolved calls and unsupported extraction patterns."),
    "trace_resource_consumers": (
        ResourceArgs,
        "Check resource-analysis availability; currently unsupported.",
    ),
}


class InvestigationTools:
    """The snapshot is bound by the application, never supplied by the model."""

    def __init__(
        self, queries, snapshot_id, share_source=False, max_calls=12, max_result_chars=12000
    ):
        self.queries, self.snapshot_id = queries, snapshot_id
        self.share_source, self.max_calls = share_source, max_calls
        self.max_result_chars = max_result_chars
        self.calls = 0
        self.activity = []
        self.resolved_ids = set()

    @staticmethod
    def schemas():
        return [
            {"name": name, "description": description, "parameters": model.model_json_schema()}
            for name, (model, description) in TOOL_ARGUMENTS.items()
        ]

    def call(self, name, arguments):
        if self.calls >= self.max_calls:
            raise BudgetExceeded("Agent tool-call budget exhausted")
        self.calls += 1
        try:
            if name not in TOOL_ARGUMENTS:
                raise ValueError("Unknown tool")
            args = TOOL_ARGUMENTS[name][0].model_validate(arguments)
            result = self._execute(name, args)
            if len(json.dumps(result)) > self.max_result_chars:
                response = {
                    "ok": False,
                    "error": "Tool result exceeds context budget; request fewer paths or IDs",
                    "truncated": True,
                }
            else:
                response = {"ok": True, "data": result}
        except (ValidationError, ValueError) as error:
            response = {"ok": False, "error": str(error)[:1000]}
        self.activity.append({"tool": name, "status": "completed" if response["ok"] else "error"})
        return {"snapshot_id": self.snapshot_id, **response}

    def _execute(self, name, args):
        q, sid = self.queries, self.snapshot_id
        if name == "resolve_symbol":
            result = q.resolve_symbol(sid, args.query)
            self.resolved_ids.update(f["id"] for f in result["candidates"])
            return result
        if name in {"trace_callers", "trace_dependencies"}:
            return q.traverse(
                sid,
                args.function_id,
                "callers" if name == "trace_callers" else "callees",
                args.max_depth,
                args.max_paths,
            )
        if name == "find_endpoints":
            return q.find_endpoints(sid, args.function_ids)
        if name == "find_related_tests":
            return q.find_related_tests(sid, args.function_ids)
        if name == "get_source_evidence":
            return q.evidence(sid, args.evidence_ids, include_source=self.share_source)
        if name == "get_analysis_gaps":
            return q.analysis_gaps(sid)
        return q.trace_resource_consumers(sid, args.resource_id)
