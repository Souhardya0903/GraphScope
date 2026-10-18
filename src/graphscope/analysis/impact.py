"""Bounded multi-target reverse dependency traversal with source evidence."""

from collections import defaultdict, deque


def impact(snapshot, target_ids, max_depth=12, max_paths=500):
    if not 1 <= max_depth <= 30 or not 1 <= max_paths <= 2000:
        raise ValueError("Depth must be 1..30 and paths 1..2000")
    functions = {f.id: f for f in snapshot.functions}
    if len(target_ids) > 500 or any(t not in functions for t in target_ids):
        raise ValueError("Select at most 500 valid target IDs")
    incoming = defaultdict(list)
    for edge in snapshot.calls:
        incoming[edge.callee_id].append(edge)
    queue = deque((target, [target], []) for target in sorted(set(target_ids)))
    affected, paths, truncated, depth_limited = set(target_ids), [], False, False
    expansions = 0
    while queue:
        current, nodes, evidence = queue.popleft()
        expansions += 1
        if expansions > 20000:
            truncated = True
            break
        if len(nodes) - 1 >= max_depth:
            depth_limited |= any(e.caller_id not in nodes for e in incoming[current])
            continue
        for edge in incoming[current]:
            if edge.caller_id in nodes:
                continue
            if len(paths) >= max_paths:
                truncated = True
                break
            chain, proof = [edge.caller_id, *nodes], [edge.model_dump(), *evidence]
            affected.add(edge.caller_id)
            paths.append(
                {
                    "function_ids": chain,
                    "functions": [functions[i].qualified_name for i in chain],
                    "evidence": proof,
                    "depth": len(chain) - 1,
                }
            )
            queue.append((edge.caller_id, chain, proof))
        if truncated:
            break
    endpoints = [e.model_dump() for e in snapshot.endpoints if e.handler_id in affected]
    tests = [
        f.model_dump()
        for f in snapshot.functions
        if f.id in affected and (f.name.startswith("test_") or "/tests/" in "/" + f.file_path)
    ]
    resources = [r.model_dump() for r in snapshot.resources if r.owner_id in affected]
    return {
        "snapshot_id": snapshot.id,
        "metadata": snapshot.metadata,
        "targets": [functions[t].model_dump() for t in sorted(set(target_ids))],
        "affected_functions": [functions[i].model_dump() for i in sorted(affected)],
        "potentially_affected_endpoints": endpoints,
        "related_tests": tests,
        "resource_accesses": resources,
        "source_files": [
            f.model_dump()
            for f in snapshot.files
            if any(
                fn.file_path == f.relative_path and fn.snapshot_id == f.snapshot_id
                for fn in snapshot.functions
                if fn.id in affected
            )
        ],
        "paths": paths,
        "limits": {
            "max_depth": max_depth,
            "max_paths": max_paths,
            "truncated": truncated,
            "depth_limited": depth_limited,
        },
        "analysis_gaps": [g.model_dump() for g in snapshot.gaps],
        "unresolved_calls": [c.model_dump() for c in snapshot.callsites if c.target_id is None],
        "completeness": "partial",
        "caveat": "Static potential impact. Test links are static calls, not coverage or test results; resource conventions may be inferred.",
    }


def propose(snapshot, description, targets=None, confirmed=False):
    if not description.strip() or len(description) > 4000:
        raise ValueError("Description must contain 1..4000 characters")
    if targets:
        selected = []
        for target in targets:
            matches = [f for f in snapshot.functions if target in {f.id, f.qualified_name}]
            if len(matches) != 1:
                raise ValueError(f"Target must identify one exact qualified symbol: {target}")
            selected.append(matches[0])
    else:
        import re

        tokens = set(re.findall(r"[a-zA-Z_]\w*(?:\.\w+)*", description.lower()))
        selected = [
            f
            for f in snapshot.functions
            if f.name.lower() in tokens or f.qualified_name.lower() in tokens
        ]
    if not confirmed or not selected:
        return {
            "mode": "hypothetical",
            "status": "confirmation_required",
            "description": description,
            "candidates": [f.model_dump() for f in selected],
            "instruction": "Confirm exact qualified targets with --target (repeatable) and --confirm. Description matching is lexical and does not infer complete intent.",
        }
    return {
        "mode": "hypothetical",
        "status": "confirmed",
        "description": description,
        "report": impact(snapshot, [f.id for f in selected]),
    }
