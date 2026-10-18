from pathlib import Path

from fastapi.testclient import TestClient

from graphscope.api.main import app

DEMO = str(Path(__file__).resolve().parents[2] / "examples/commerce")


def test_map_impact_and_proposal_through_api():
    with TestClient(app) as client:
        mapping = client.post("/api/analysis/map", json={"root": DEMO})
        assert mapping.status_code == 200
        assert mapping.json()["metadata"]["analysis_version"] == "1"
        response = client.post(
            "/api/analysis/impact", json={"root": DEMO, "targets": ["inventory.validate_stock"]}
        )
        assert response.status_code == 200
        assert {e["path"] for e in response.json()["report"]["potentially_affected_endpoints"]} == {
            "/orders",
            "/reservations",
        }
        proposal = client.post(
            "/api/analysis/propose", json={"root": DEMO, "description": "change validate_stock"}
        )
        assert proposal.json()["status"] == "confirmation_required"


def test_analysis_input_failures_are_structured():
    with TestClient(app) as client:
        assert client.post("/api/analysis/map", json={"root": "missing-repo"}).status_code == 422
        assert client.post("/api/analysis/impact", json={"root": DEMO}).status_code == 422
        assert client.post("/api/analysis/no-such-mode", json={"root": DEMO}).status_code == 422
        assert (
            client.post("/api/analysis/map", json={"root": DEMO, "unexpected": True}).status_code
            == 422
        )
