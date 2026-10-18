"""Integration tests for the FastAPI backend with a live FalkorDB Cloud instance.

Run with:
    $env:GRAPHSCOPE_INTEGRATION = "1"
    pytest tests/integration/test_api.py -v
"""

import json
import logging
import os
from pathlib import Path
from uuid import uuid4

import pytest
from redis.exceptions import RedisError

pytestmark = pytest.mark.skipif(
    os.environ.get("GRAPHSCOPE_INTEGRATION") != "1",
    reason="API integration tests require GRAPHSCOPE_INTEGRATION=1",
)

DEMO = Path(__file__).resolve().parents[2] / "examples" / "commerce"

# Use a uniquely named graph per test run to avoid interference.
TEST_GRAPH = f"graphscope_api_test_{uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client():
    """Build a TestClient with a test-isolated FalkorDB graph."""
    from fastapi.testclient import TestClient

    from graphscope.api.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    # Cleanup: delete the test graph from FalkorDB Cloud.
    try:
        from graphscope.graph.client import select_graph

        select_graph(TEST_GRAPH).delete()
    except RedisError:
        logging.getLogger(__name__).warning("Could not clean up isolated API test graph")


@pytest.fixture(scope="module")
def indexed_snapshot_id(client):
    """Index the commerce fixture into the test graph, return snapshot_id."""
    response = client.post(
        "/api/index",
        json={"root": str(DEMO), "graph": TEST_GRAPH},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "ready"
    assert data["files"] >= 6
    assert data["functions"] >= 5
    assert data["calls"] >= 4
    assert data["endpoints"] >= 3
    return data["snapshot_id"]


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestIndex:
    def test_index_commerce(self, indexed_snapshot_id):
        assert indexed_snapshot_id, "snapshot_id must be non-empty"

    def test_index_missing_path(self, client):
        resp = client.post("/api/index", json={"root": "/nonexistent/path", "graph": TEST_GRAPH})
        assert resp.status_code == 400

    def test_index_idempotent(self, client, indexed_snapshot_id):
        """Indexing the same snapshot twice must not raise."""
        resp = client.post("/api/index", json={"root": str(DEMO), "graph": TEST_GRAPH})
        assert resp.status_code == 200


class TestSnapshots:
    def test_list_snapshots(self, client, indexed_snapshot_id):
        resp = client.get("/api/snapshots", params={"graph": TEST_GRAPH})
        assert resp.status_code == 200
        data = resp.json()
        assert "snapshots" in data
        ids = [s["snapshot_id"] for s in data["snapshots"]]
        assert indexed_snapshot_id in ids

    def test_get_snapshot(self, client, indexed_snapshot_id):
        resp = client.get(f"/api/snapshots/{indexed_snapshot_id}", params={"graph": TEST_GRAPH})
        assert resp.status_code == 200
        data = resp.json()
        assert data["snapshot_id"] == indexed_snapshot_id


class TestInvestigate:
    def _collect_sse(self, response) -> dict[str, list]:
        """Parse SSE body into {event_name: [data, ...]}."""
        events: dict[str, list] = {}
        current_event = None
        for line in response.text.splitlines():
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip()
            elif line.startswith("data:") and current_event:
                payload = json.loads(line[len("data:") :].strip())
                events.setdefault(current_event, []).append(payload)
        return events

    def test_deterministic_investigation_validate_stock(self, client, indexed_snapshot_id):
        """Deterministic (no LLM) investigation of validate_stock returns both endpoints."""
        resp = client.post(
            "/api/investigate",
            json={
                "snapshot_id": indexed_snapshot_id,
                "question": "What depends on validate_stock?",
                "target": "inventory.validate_stock",
                "provider": "test",
                "graph": TEST_GRAPH,
            },
        )
        assert resp.status_code == 200
        events = self._collect_sse(resp)

        assert "report_complete" in events, "Must emit report_complete event"
        assert "graph_evidence" in events, "Must emit graph_evidence event"

        report = events["report_complete"][0]
        paths = report["graph_evidence"]["paths"]
        endpoint_paths = {
            e["path"] for e in report["graph_evidence"]["potentially_affected_endpoints"]
        }
        assert "/orders" in endpoint_paths, "POST /orders must be in affected endpoints"
        assert "/reservations" in endpoint_paths, "POST /reservations must be in affected endpoints"
        assert len(paths) >= 2, "Must find at least 2 caller paths"

    def test_analysis_gaps_reported(self, client, indexed_snapshot_id):
        """Unresolved dynamic calls from dispatch.py must surface in analysis_gaps."""
        resp = client.post(
            "/api/investigate",
            json={
                "snapshot_id": indexed_snapshot_id,
                "question": "What depends on validate_stock?",
                "target": "inventory.validate_stock",
                "provider": "test",
                "graph": TEST_GRAPH,
            },
        )
        events = self._collect_sse(resp)
        report = events["report_complete"][0]
        unresolved = report["analysis_gaps"]["unresolved_calls"]
        # dispatch.py has getattr dynamic call — must appear
        sources = [u["file_path"] for u in unresolved]
        assert "dispatch.py" in sources, "Dynamic call from dispatch.py must be flagged as a gap"

    def test_missing_target_returns_error(self, client, indexed_snapshot_id):
        """provider=test without target must return HTTP 400."""
        resp = client.post(
            "/api/investigate",
            json={
                "snapshot_id": indexed_snapshot_id,
                "question": "What does validate_stock affect?",
                "provider": "test",  # no target
                "graph": TEST_GRAPH,
            },
        )
        assert resp.status_code == 400

    def test_sse_agent_thought_events_emitted(self, client, indexed_snapshot_id):
        """At least one agent_thought event must be emitted before report_complete."""
        resp = client.post(
            "/api/investigate",
            json={
                "snapshot_id": indexed_snapshot_id,
                "question": "What depends on validate_stock?",
                "target": "inventory.validate_stock",
                "provider": "test",
                "graph": TEST_GRAPH,
            },
        )
        events = self._collect_sse(resp)
        assert len(events.get("agent_thought", [])) >= 1


class TestEvidence:
    def test_evidence_no_source(self, client, indexed_snapshot_id):
        """GET /api/evidence returns edge metadata without source when not requested."""
        # First, get some evidence IDs from an investigation.
        inv_resp = client.post(
            "/api/investigate",
            json={
                "snapshot_id": indexed_snapshot_id,
                "question": "What depends on validate_stock?",
                "target": "inventory.validate_stock",
                "provider": "test",
                "graph": TEST_GRAPH,
            },
        )
        import json as j

        events = {}
        current = None
        for line in inv_resp.text.splitlines():
            if line.startswith("event:"):
                current = line[len("event:") :].strip()
            elif line.startswith("data:") and current:
                events.setdefault(current, []).append(j.loads(line[len("data:") :]))
        report = events["report_complete"][0]
        evidence_ids = [e["id"] for e in report["graph_evidence"]["evidence"]]
        assert evidence_ids, "Report must contain evidence IDs"

        resp = client.get(
            "/api/evidence",
            params={
                "snapshot_id": indexed_snapshot_id,
                "evidence_ids": ",".join(evidence_ids[:2]),
                "include_source": False,
                "graph": TEST_GRAPH,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "evidence" in data


class TestDeleteSnapshot:
    def test_delete_snapshot(self, client, indexed_snapshot_id):
        """Deleting a snapshot must return deleted=True."""
        # Use a fresh index so we don't break other tests.
        idx_resp = client.post("/api/index", json={"root": str(DEMO), "graph": TEST_GRAPH})
        sid = idx_resp.json()["snapshot_id"]
        resp = client.delete(f"/api/snapshots/{sid}", params={"graph": TEST_GRAPH})
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


class TestSnapshotLifecycle:
    def test_counts_and_delete_remove_metadata(self, client, indexed_snapshot_id):
        response = client.get(f"/api/snapshots/{indexed_snapshot_id}", params={"graph": TEST_GRAPH})
        assert response.status_code == 200
        assert response.json()["function_count"] > 0
        assert response.headers.get("x-request-id")
        # Use a separate snapshot so existing API tests keep their shared fixture.
        indexed = client.post("/api/index", json={"root": str(DEMO), "graph": TEST_GRAPH}).json()
        sid = indexed["snapshot_id"]
        deleted = client.delete(f"/api/snapshots/{sid}", params={"graph": TEST_GRAPH})
        assert deleted.status_code == 200
        assert client.get(f"/api/snapshots/{sid}", params={"graph": TEST_GRAPH}).status_code == 404
        listed = client.get("/api/snapshots", params={"graph": TEST_GRAPH}).json()
        assert all(s["snapshot_id"] != sid for s in listed["snapshots"])
