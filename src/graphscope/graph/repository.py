"""Persist snapshot entities, dependency relationships, and source evidence."""

import hashlib
import json
import logging
from uuid import uuid4

from redis.exceptions import RedisError, ResponseError

from graphscope.models import Snapshot

TIMEOUT = 5000
BATCH_SIZE = 200


def validate_snapshot(snapshot: Snapshot):
    """Reject cross-snapshot references and missing evidence before touching the DB."""
    entities = [*snapshot.files, *snapshot.functions, *snapshot.callsites, *snapshot.endpoints]
    if len({n.id for n in entities}) != len(entities):
        raise ValueError("Duplicate entity IDs")
    if any(n.snapshot_id != snapshot.id for n in entities):
        raise ValueError("Cross-snapshot entity")
    if any(not n.id.startswith(snapshot.id + ":") for n in entities):
        raise ValueError("Entity ID must be scoped to its snapshot")
    files = {f.relative_path: f for f in snapshot.files}
    functions = {f.id: f for f in snapshot.functions}
    sites = {c.id: c for c in snapshot.callsites}
    if len(files) != len(snapshot.files):
        raise ValueError("Duplicate file paths")
    for function in snapshot.functions:
        if function.file_path not in files:
            raise ValueError("Function references a missing file")
    for site in snapshot.callsites:
        owner = functions.get(site.owner_id)
        if owner is None or owner.file_path != site.file_path:
            raise ValueError("Call site references a missing or inconsistent owner")
        if site.target_id is not None and site.target_id not in functions:
            raise ValueError("Call site target is outside snapshot")
        if (site.resolution_status == "resolved") != (site.target_id is not None):
            raise ValueError("Inconsistent resolution status")
    evidence_ids = set()
    for edge in snapshot.calls:
        site = sites.get(edge.callsite_id)
        if (
            site is None
            or site.owner_id != edge.caller_id
            or site.target_id != edge.callee_id
            or site.file_path != edge.file_path
            or site.line != edge.line
        ):
            raise ValueError("Call edge lacks consistent source evidence")
        if edge.callsite_id in evidence_ids:
            raise ValueError("Duplicate call evidence")
        evidence_ids.add(edge.callsite_id)
    if evidence_ids != {c.id for c in snapshot.callsites if c.target_id is not None}:
        raise ValueError("Resolved call sites and edges disagree")
    for endpoint in snapshot.endpoints:
        handler = functions.get(endpoint.handler_id)
        if handler is None or handler.file_path != endpoint.file_path:
            raise ValueError("Endpoint references a missing or inconsistent handler")


class GraphRepository:
    def __init__(self, graph):
        self.graph = graph

    def write(self, query, params=None):
        return self.graph.query(query, params or {}, timeout=TIMEOUT).result_set

    def read(self, query, params=None):
        return self.graph.ro_query(query, params or {}, timeout=TIMEOUT).result_set

    def batches(self, query, rows):
        for start in range(0, len(rows), BATCH_SIZE):
            self.write(query, {"rows": rows[start : start + BATCH_SIZE]})

    def ensure_index(self, label, property_name):
        try:
            self.write(f"CREATE INDEX ON :{label}({property_name})")
        except ResponseError as error:
            if "already indexed" not in str(error):
                raise

    def store(self, snapshot: Snapshot):
        validate_snapshot(snapshot)
        digest = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
        # A write-form MATCH initializes an absent graph without fabricating data.
        existing = self.write(
            "MATCH (s:RepositorySnapshot {id:$id}) RETURN s.status,s.digest", {"id": snapshot.id}
        )
        if existing:
            if existing == [["ready", digest]]:
                return snapshot.id
            raise ValueError(
                "Snapshot ID already exists with different content or incomplete status"
            )
        for label in ("RepositorySnapshot", "File", "Function", "CallSite", "Endpoint"):
            self.ensure_index(label, "id")
        for label in ("File", "Function", "CallSite", "Endpoint"):
            self.ensure_index(label, "snapshot_id")
        claim = uuid4().hex
        ownership = self.write(
            "MERGE (s:RepositorySnapshot {id:$id}) ON CREATE SET s.status='building',"
            "s.digest=$digest,s.root=$root,s.indexed_at=$time,s.extractor_version=$version,"
            "s.gaps=$gaps,s.claim=$claim RETURN s.claim",
            {
                "id": snapshot.id,
                "claim": claim,
                "digest": digest,
                "root": snapshot.root,
                "time": snapshot.indexed_at,
                "version": snapshot.extractor_version,
                "gaps": json.dumps([g.model_dump() for g in snapshot.gaps]),
            },
        )
        if ownership != [[claim]]:
            raise ValueError("Another writer already claimed this snapshot")
        try:
            for label, nodes in (
                ("File", snapshot.files),
                ("Function", snapshot.functions),
                ("CallSite", snapshot.callsites),
                ("Endpoint", snapshot.endpoints),
            ):
                rows = []
                for node in nodes:
                    row = node.model_dump(exclude_none=True)
                    if label == "Endpoint":
                        row["mount_evidence"] = json.dumps(row["mount_evidence"])
                    rows.append(row)
                self.batches(f"UNWIND $rows AS row CREATE (n:{label}) SET n = row", rows)
            self.batches(
                "UNWIND $rows AS row MATCH (s:RepositorySnapshot {id:row.snapshot_id}),"
                "(f:File {id:row.id}) CREATE (s)-[:CONTAINS]->(f)",
                [f.model_dump() for f in snapshot.files],
            )
            for label, nodes, relation in (
                ("Function", snapshot.functions, "DEFINES"),
                ("CallSite", snapshot.callsites, "HAS_CALLSITE"),
            ):
                file_ids = {f.relative_path: f.id for f in snapshot.files}
                rows = [
                    {
                        "id": n.id,
                        "owner": file_ids[n.file_path] if label == "Function" else n.owner_id,
                    }
                    for n in nodes
                ]
                owner_label = "File" if label == "Function" else "Function"
                self.batches(
                    f"UNWIND $rows AS row MATCH (a:{owner_label} {{id:row.owner}}),"
                    f"(b:{label} {{id:row.id}}) CREATE (a)-[:{relation}]->(b)",
                    rows,
                )
            self.batches(
                "UNWIND $rows AS row MATCH (a:Function {id:row.caller_id}),"
                "(b:Function {id:row.callee_id}) CREATE (a)-[r:CALLS]->(b) SET r = row",
                [{**e.model_dump(), "snapshot_id": snapshot.id} for e in snapshot.calls],
            )
            self.batches(
                "UNWIND $rows AS row MATCH (a:Endpoint {id:row.id}),"
                "(b:Function {id:row.handler}) CREATE (a)-[:HANDLED_BY]->(b)",
                [{"id": e.id, "handler": e.handler_id} for e in snapshot.endpoints],
            )
            for label, expected in (
                ("File", len(snapshot.files)),
                ("Function", len(snapshot.functions)),
                ("CallSite", len(snapshot.callsites)),
                ("Endpoint", len(snapshot.endpoints)),
            ):
                actual = self.read(
                    f"MATCH (n:{label} {{snapshot_id:$id}}) RETURN count(n)", {"id": snapshot.id}
                )[0][0]
                if actual != expected:
                    raise RuntimeError(f"Snapshot validation failed for {label}")
            for relation, expected in (
                ("CONTAINS", len(snapshot.files)),
                ("DEFINES", len(snapshot.functions)),
                ("HAS_CALLSITE", len(snapshot.callsites)),
                ("CALLS", len(snapshot.calls)),
                ("HANDLED_BY", len(snapshot.endpoints)),
            ):
                actual = self.read(
                    f"MATCH (a)-[r:{relation}]->(b) WHERE b.snapshot_id=$id RETURN count(r)",
                    {"id": snapshot.id},
                )[0][0]
                if actual != expected:
                    raise RuntimeError(f"Snapshot relationship validation failed for {relation}")
            self.write(
                "MATCH (s:RepositorySnapshot {id:$id}) SET s.status='ready'", {"id": snapshot.id}
            )
        except Exception:
            try:
                self.write(
                    "MATCH (s:RepositorySnapshot {id:$id}) SET s.status='failed'",
                    {"id": snapshot.id},
                )
            except RedisError:
                logging.getLogger(__name__).warning(
                    "Snapshot remains unpublished after database failure"
                )
            raise
        return snapshot.id
