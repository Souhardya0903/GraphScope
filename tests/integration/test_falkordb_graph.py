"""Opt in with GRAPHSCOPE_INTEGRATION=1. All writes use a disposable graph."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from graphscope.graph.client import select_graph
from graphscope.graph.queries import GraphQueries
from graphscope.graph.repository import GraphRepository
from graphscope.ingestion.pipeline import ingest

pytestmark = pytest.mark.skipif(
    os.environ.get("GRAPHSCOPE_INTEGRATION") != "1",
    reason="Cloud graph tests require explicit opt-in",
)
DEMO = Path(__file__).resolve().parents[2] / "examples" / "commerce"


@pytest.fixture(scope="module")
def graph():
    selected = select_graph(f"graphscope_stage3_test_{uuid4().hex}")
    selected.query("CREATE (:IntegrationMarker)")
    try:
        yield selected
    finally:
        selected.delete()


def test_commerce_storage_queries_evidence_isolation_and_retry(graph):
    repository, queries = GraphRepository(graph), GraphQueries(graph)
    first, second = ingest(DEMO), ingest(DEMO)
    repository.store(first)
    repository.store(first)  # Retrying the identical ready snapshot must not duplicate it.
    repository.store(second)
    report = queries.investigate(first.id, "inventory.validate_stock")
    callers = {p["functions"][0] for p in report["caller_paths"]}
    assert callers == {"orders.create_order", "orders.place_order", "reservations.reserve_stock"}
    assert {e["path"] for e in report["potentially_affected_endpoints"]["endpoints"]} == {
        "/orders",
        "/reservations",
    }
    assert all(
        i.startswith(first.id + ":") for p in report["caller_paths"] for i in p["function_ids"]
    )
    assert len(queries.analysis_gaps(first.id)["unresolved_calls"]) == 5
    evidence_ids = {i for p in report["caller_paths"] for i in p["evidence_ids"]}
    evidence = queries.evidence(first.id, evidence_ids, include_source=True)
    assert len(evidence["evidence"]) == len(evidence_ids)
    assert all(e["target_text"] in e["source"] for e in evidence["evidence"])
    assert queries.evidence(second.id, evidence_ids)["evidence"] == []
    target = queries.resolve_symbol(first.id, "orders.create_order")["candidates"][0]["id"]
    forward = queries.traverse(first.id, target, "callees")
    assert any(p["functions"][-1] == "redis_adapter.read_stock" for p in forward["paths"])
    zero_hop = queries.investigate(first.id, "orders.create_order")
    assert [e["path"] for e in zero_hop["potentially_affected_endpoints"]["endpoints"]] == [
        "/orders"
    ]
    limited = queries.investigate(first.id, "inventory.validate_stock", max_paths=1)
    assert limited["limits"]["truncated"]
    with pytest.raises(ValueError, match="selected snapshot"):
        queries.traverse(second.id, target)
    assert queries.find_related_tests(first.id, [target])["supported"] is False


def test_cycles_stale_evidence_parse_gaps_and_ambiguous_symbols(graph, tmp_path):
    (tmp_path / "a.py").write_text("def helper(): other()\ndef other(): helper()\n")
    (tmp_path / "b.py").write_text("def helper(): pass\n")
    (tmp_path / "bad.py").write_text("def broken(:")
    snapshot = ingest(tmp_path)
    GraphRepository(graph).store(snapshot)
    queries = GraphQueries(graph)
    assert len(queries.resolve_symbol(snapshot.id, "helper")["candidates"]) == 2
    with pytest.raises(ValueError, match="unambiguous"):
        queries.investigate(snapshot.id, "helper")
    report = queries.investigate(snapshot.id, "a.helper", max_depth=3)
    assert len(report["caller_paths"]) <= 3
    assert any(g["path"] == "bad.py" for g in report["analysis_gaps"]["extraction_gaps"])
    evidence_id = snapshot.calls[0].callsite_id
    (tmp_path / "a.py").write_text("# source changed\n")
    with pytest.raises(ValueError, match="changed"):
        queries.evidence(snapshot.id, [evidence_id], include_source=True)


def test_incomplete_snapshot_is_never_queryable(graph, tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("def helper(): pass\n")
    snapshot = ingest(tmp_path)
    repo = GraphRepository(graph)

    def fail(*args):
        raise RuntimeError("Injected write failure")

    monkeypatch.setattr(repo, "batches", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        repo.store(snapshot)
    assert repo.read(
        "MATCH (s:RepositorySnapshot {id:$sid}) RETURN s.status", {"sid": snapshot.id}
    ) == [["failed"]]
    with pytest.raises(ValueError, match="not ready"):
        GraphQueries(graph).investigate(snapshot.id, "a.helper")


def test_concurrent_same_snapshot_has_one_build(graph, tmp_path):
    (tmp_path / "a.py").write_text("def helper(): helper()\n")
    snapshot = ingest(tmp_path)

    def store_once():
        try:
            return GraphRepository(graph).store(snapshot)
        except ValueError:
            return "already claimed"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store_once(), range(2)))
    assert snapshot.id in results
    repo = GraphRepository(graph)
    assert repo.read(
        "MATCH (s:RepositorySnapshot {id:$sid}) RETURN count(s)", {"sid": snapshot.id}
    ) == [[1]]
    assert len(GraphQueries(graph).investigate(snapshot.id, "a.helper")["caller_paths"]) == 1
