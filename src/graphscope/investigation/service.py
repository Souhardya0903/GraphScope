"""Find reverse callers, affected endpoints, evidence paths, and analysis gaps."""

from datetime import UTC, datetime
from uuid import uuid4

from graphscope.models import ImpactReport


class ClarificationRequired(ValueError):
    def __init__(self, candidates):
        super().__init__("Select one unambiguous function ID or qualified name")
        self.candidates = candidates


def resolve_target(queries, snapshot_id, target):
    result = queries.resolve_symbol(snapshot_id, target)
    if len(result["candidates"]) != 1 or result["truncated"]:
        raise ClarificationRequired(result["candidates"])
    return result["candidates"][0]


def build_report(queries, snapshot_id, target, question, include_source=False):
    """Facts are assembled independently of anything the model says."""
    target = resolve_target(queries, snapshot_id, target)["id"]
    finding = queries.investigate(snapshot_id, target, max_depth=8, max_paths=30)
    target_id = finding["target"]["id"]
    evidence_ids = sorted({e for p in finding["caller_paths"] for e in p["evidence_ids"]})
    source_gap = None
    try:
        evidence = queries.evidence(snapshot_id, evidence_ids, include_source=include_source)
    except ValueError as error:
        source_gap = str(error)
        evidence = queries.evidence(snapshot_id, evidence_ids, include_source=False)
    depths = {}
    for path in finding["caller_paths"]:
        for index, function_id in enumerate(path["function_ids"][:-1]):
            if function_id != target_id:
                depth = len(path["function_ids"]) - index - 1
                if function_id not in depths or depth < depths[function_id]["depth"]:
                    depths[function_id] = {
                        "id": function_id,
                        "name": path["functions"][index],
                        "depth": depth,
                    }
    endpoints = finding["potentially_affected_endpoints"]
    gaps = {
        **finding["analysis_gaps"],
        "source_error": source_gap,
        "missing_evidence_ids": evidence["missing_ids"],
        "tests": queries.find_related_tests(snapshot_id, [target_id, *depths]),
        "resources": queries.trace_resource_consumers(snapshot_id, ""),
    }
    limited = (
        any(finding["limits"][k] for k in ("truncated", "depth_boundary_reached"))
        or endpoints["truncated"]
        or gaps["truncated"]
    )
    partial = limited or bool(
        gaps["unresolved_calls"] or gaps["extraction_gaps"] or source_gap or evidence["missing_ids"]
    )
    checks = [
        {
            "text": f"Manually review {e['method']} {e['path']} and its dependency path.",
            "origin": "deterministic",
        }
        for e in endpoints["endpoints"]
    ]
    if gaps["unresolved_calls"]:
        checks.append(
            {
                "text": "Review unresolved call sites; additional dependents may be missing.",
                "origin": "deterministic",
            }
        )
    return ImpactReport(
        investigation_id=uuid4().hex,
        snapshot_id=snapshot_id,
        target_id=target_id,
        question=question,
        generated_at=datetime.now(UTC).isoformat(),
        graph_evidence={
            "target": finding["target"],
            "direct_callers": [f for f in depths.values() if f["depth"] == 1],
            "indirect_callers": [f for f in depths.values() if f["depth"] > 1],
            "potentially_affected_endpoints": endpoints["endpoints"],
            "paths": finding["caller_paths"],
            "evidence": evidence["evidence"],
            "limits": {**finding["limits"], "endpoints_truncated": endpoints["truncated"]},
            "caveat": finding["caveat"],
        },
        recommended_checks=checks,
        analysis_gaps=gaps,
        completeness="partial" if partial else "within_supported_scope",
        agent={
            "status": "disabled",
            "provider": "none",
            "reason": "Deterministic report; no model used",
        },
    )
