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


def test_local_boundary_rejects_foreign_origin_host_and_disallowed_root():
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
        assert (
            client.post(
                "/api/analysis/map", json={"root": DEMO}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            client.post("/api/analysis/map", json={"root": str(Path(DEMO).anchor)}).status_code
            == 403
        )


def test_allowed_root_is_explicit(tmp_path, monkeypatch):
    import json

    from graphscope.api.safety import allowed_path

    monkeypatch.setenv("GRAPHSCOPE_ALLOWED_ROOTS", json.dumps([str(tmp_path)]))
    assert allowed_path(tmp_path) == tmp_path.resolve()


def test_request_diagnostics_do_not_echo_payloads():
    with TestClient(app) as client:
        response = client.post("/api/analysis/map", json={"root": DEMO})
        assert response.status_code == 200
        assert len(response.headers["x-request-id"]) == 32
        assert (
            client.post(
                "/api/investigate",
                json={"snapshot_id": "x", "question": "test", "provider": "unknown"},
            ).status_code
            == 422
        )


def test_model_proposal_requires_consent_then_separate_confirmation(monkeypatch):
    import json

    from graphscope.api import analysis
    from graphscope.investigation.agent import ModelTurn, Selection

    calls = []

    class Model:
        provider_name = "gemini"

        def complete(self, messages, tools, timeout):
            calls.append(messages)
            catalog = json.loads(messages[1]["content"])["symbol_catalog"]
            target = next(f for f in catalog if f["name"] == "inventory.validate_stock")
            return ModelTurn(
                selection=Selection(
                    target_id=target["id"], recommended_checks=["Review quantity boundaries"]
                )
            )

    monkeypatch.setattr(analysis, "GeminiModel", Model)
    payload = {
        "root": DEMO,
        "description": "Reject orders when stock is insufficient",
        "provider": "gemini",
    }
    with TestClient(app) as client:
        assert client.post("/api/analysis/propose", json=payload).status_code == 422
        assert calls == []
        response = client.post("/api/analysis/propose", json={**payload, "share_catalog": True})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmation_required"
        assert data["candidates"][0]["qualified_name"] == "inventory.validate_stock"
        assert "report" not in data
        assert len(calls) == 1
        sent = json.loads(calls[0][1]["content"])
        assert set(sent) == {"description", "symbol_catalog"}
        assert all(set(f) == {"id", "name", "file_path"} for f in sent["symbol_catalog"])
        confirmed = client.post(
            "/api/analysis/propose",
            json={
                "root": DEMO,
                "description": payload["description"],
                "targets": ["inventory.validate_stock"],
                "confirm": True,
            },
        )
        assert confirmed.json()["status"] == "confirmed"
        assert len(calls) == 1
        assert {
            e["path"] for e in confirmed.json()["report"]["potentially_affected_endpoints"]
        } == {"/orders", "/reservations"}
        assert (
            client.post(
                "/api/analysis/propose", json={**payload, "share_catalog": True, "confirm": True}
            ).status_code
            == 422
        )


def test_model_failure_and_invalid_target_remain_structured(monkeypatch):
    from graphscope.api import analysis
    from graphscope.investigation.agent import ModelFailure, ModelTurn, Selection

    class BrokenModel:
        provider_name = "ollama"

        def complete(self, *args, **kwargs):
            raise ModelFailure("Provider unavailable")

    monkeypatch.setattr(analysis, "OllamaModel", BrokenModel)
    payload = {
        "root": DEMO,
        "description": "Change stock handling",
        "provider": "ollama",
        "share_catalog": True,
    }
    with TestClient(app) as client:
        response = client.post("/api/analysis/propose", json=payload)
        assert response.status_code == 502
        assert "offline suggestions" in response.json()["detail"]

        class InvalidModel(BrokenModel):
            def complete(self, *args, **kwargs):
                return ModelTurn(selection=Selection(target_id="invented"))

        monkeypatch.setattr(analysis, "OllamaModel", InvalidModel)
        assert client.post("/api/analysis/propose", json=payload).status_code == 502
        fallback = client.post(
            "/api/analysis/propose", json={"root": DEMO, "description": "Change validate_stock"}
        )
        assert fallback.status_code == 200
        assert fallback.json()["status"] == "confirmation_required"
