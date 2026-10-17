"""Predefined parameterized queries with snapshot isolation and bounded traversal."""

import hashlib
import io
import json
import tokenize
from pathlib import Path

from graphscope.graph.repository import GraphRepository


class GraphQueries(GraphRepository):
    def ready(self, snapshot_id):
        rows = self.read(
            "MATCH (s:RepositorySnapshot {id:$sid,status:'ready'}) RETURN s.id",
            {"sid": snapshot_id},
        )
        if not rows:
            raise ValueError("Snapshot is missing or not ready")

    @staticmethod
    def limit(value, maximum=1000):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"Limit must be an integer in 1..{maximum}")
        return value

    def resolve_symbol(self, snapshot_id, query, limit=20):
        self.ready(snapshot_id)
        self.limit(limit)
        rows = self.read(
            "MATCH (f:Function {snapshot_id:$sid}) "
            "WHERE f.id=$query OR f.qualified_name=$query OR f.name=$query "
            "RETURN f.id,f.qualified_name,f.file_path,f.start_line "
            "ORDER BY f.qualified_name,f.start_line LIMIT $limit",
            {"sid": snapshot_id, "query": query, "limit": limit + 1},
        )
        return {
            "candidates": [
                {"id": i, "qualified_name": n, "file_path": p, "line": line}
                for i, n, p, line in rows[:limit]
            ],
            "truncated": len(rows) > limit,
        }

    def traverse(self, snapshot_id, function_id, direction="callers", max_depth=8, max_paths=100):
        self.ready(snapshot_id)
        self.limit(max_depth, 20)
        self.limit(max_paths)
        if direction not in {"callers", "callees"}:
            raise ValueError("Direction must be callers or callees")
        matches = self.resolve_symbol(snapshot_id, function_id)["candidates"]
        matches = [f for f in matches if f["id"] == function_id]
        if not matches:
            raise ValueError("Function is not in the selected snapshot")
        # Only the range literal is interpolated, after strict integer validation.
        pattern = (
            f"(a:Function)-[:CALLS*1..{max_depth}]->(t:Function {{id:$target}})"
            if direction == "callers"
            else f"(t:Function {{id:$target}})-[:CALLS*1..{max_depth}]->(a:Function)"
        )
        rows = self.read(
            f"MATCH p={pattern} WHERE all(n IN nodes(p) WHERE n.snapshot_id=$sid) "
            "AND all(r IN relationships(p) WHERE r.snapshot_id=$sid) "
            "RETURN [n IN nodes(p) | n.id], [n IN nodes(p) | n.qualified_name], "
            "[r IN relationships(p) | r.callsite_id], length(p) "
            "ORDER BY length(p) LIMIT $limit",
            {"sid": snapshot_id, "target": function_id, "limit": max_paths + 1},
        )
        return {
            "paths": [
                {"function_ids": ids, "functions": names, "evidence_ids": evidence, "depth": depth}
                for ids, names, evidence, depth in rows[:max_paths]
            ],
            "target": matches[0],
            "direction": direction,
            "limits": {
                "max_depth": max_depth,
                "max_paths": max_paths,
                "truncated": len(rows) > max_paths,
                "depth_boundary_reached": any(r[3] == max_depth for r in rows[:max_paths]),
            },
        }

    def find_endpoints(self, snapshot_id, function_ids, limit=100):
        self.ready(snapshot_id)
        self.limit(limit)
        if len(function_ids) > 20000:
            raise ValueError("Too many functions")
        rows = self.read(
            "MATCH (e:Endpoint {snapshot_id:$sid})-[:HANDLED_BY]->"
            "(f:Function {snapshot_id:$sid}) WHERE f.id IN $ids "
            "RETURN e.id,e.method,e.path,f.id,e.file_path,e.line,e.mount_evidence "
            "ORDER BY e.method,e.path LIMIT $limit",
            {"sid": snapshot_id, "ids": list(function_ids), "limit": limit + 1},
        )
        return {
            "endpoints": [
                {
                    "id": i,
                    "method": m,
                    "path": p,
                    "handler_id": h,
                    "file_path": f,
                    "line": line,
                    "mount_evidence": json.loads(mounts),
                }
                for i, m, p, h, f, line, mounts in rows[:limit]
            ],
            "truncated": len(rows) > limit,
        }

    def analysis_gaps(self, snapshot_id, limit=100):
        self.ready(snapshot_id)
        self.limit(limit)
        rows = self.read(
            "MATCH (c:CallSite {snapshot_id:$sid,resolution_status:'unresolved'}) "
            "RETURN c.id,c.file_path,c.line,c.target_text,c.reason "
            "ORDER BY c.file_path,c.line LIMIT $limit",
            {"sid": snapshot_id, "limit": limit + 1},
        )
        gaps = self.read(
            "MATCH (s:RepositorySnapshot {id:$sid}) RETURN s.gaps", {"sid": snapshot_id}
        )
        return {
            "unresolved_calls": [
                {"id": i, "file_path": p, "line": line, "target_text": t, "reason": r}
                for i, p, line, t, r in rows[:limit]
            ],
            "extraction_gaps": json.loads(gaps[0][0])[:limit],
            "truncated": len(rows) > limit or len(json.loads(gaps[0][0])) > limit,
        }

    def evidence(self, snapshot_id, evidence_ids, include_source=False):
        self.ready(snapshot_id)
        if len(evidence_ids) > 1000:
            raise ValueError("At most 1000 evidence IDs per request")
        rows = self.read(
            "MATCH (s:RepositorySnapshot {id:$sid}), (f:File {snapshot_id:$sid}), "
            "(c:CallSite {snapshot_id:$sid}) WHERE c.id IN $ids AND f.relative_path=c.file_path "
            "RETURN c.id,c.file_path,c.line,c.end_line,c.target_text,c.resolution_status,"
            "f.content_hash,s.root ORDER BY c.id",
            {"sid": snapshot_id, "ids": list(evidence_ids)},
        )
        results = []
        for i, path, line, end, text, status, content_hash, root in rows:
            item = {
                "id": i,
                "file_path": path,
                "line": line,
                "end_line": end,
                "target_text": text,
                "resolution_status": status,
                "content_hash": content_hash,
            }
            if include_source:
                base = Path(root).resolve()
                source = (base / path).resolve()
                if not source.is_relative_to(base):
                    raise ValueError("Source path escapes indexed repository")
                try:
                    raw = source.read_bytes()
                    if hashlib.sha256(raw).hexdigest() != content_hash:
                        raise ValueError(
                            "Indexed source has changed; reindex before retrieving evidence"
                        )
                    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
                    item["source"] = "".join(
                        raw.decode(encoding).splitlines(keepends=True)[
                            line - 1 : min(end, line + 49)
                        ]
                    )
                    item["source_truncated"] = end > line + 49
                except OSError as error:
                    raise ValueError("Indexed source is no longer available") from error
            results.append(item)
        found = {r["id"] for r in results}
        return {"evidence": results, "missing_ids": [i for i in evidence_ids if i not in found]}

    def investigate(self, snapshot_id, target, max_depth=8, max_paths=100):
        candidates = self.resolve_symbol(snapshot_id, target)["candidates"]
        if len(candidates) != 1:
            raise ValueError("Choose one unambiguous symbol ID or qualified name")
        target_id = candidates[0]["id"]
        traversal = self.traverse(snapshot_id, target_id, "callers", max_depth, max_paths)
        ids = {target_id}
        for path in traversal["paths"]:
            ids.update(path["function_ids"])
        return {
            "snapshot_id": snapshot_id,
            "target": candidates[0],
            "caller_paths": traversal["paths"],
            "limits": traversal["limits"],
            "potentially_affected_endpoints": self.find_endpoints(snapshot_id, ids),
            "analysis_gaps": self.analysis_gaps(snapshot_id),
            "caveat": "Reachability indicates potential impact. No path is not proof of safety.",
        }

    def find_related_tests(self, snapshot_id, function_ids):
        self.ready(snapshot_id)
        return {"supported": False, "reason": "Static test classification is not yet ingested"}

    def trace_resource_consumers(self, snapshot_id, resource_id):
        self.ready(snapshot_id)
        return {"supported": False, "reason": "Explicit resource declarations are not yet ingested"}
