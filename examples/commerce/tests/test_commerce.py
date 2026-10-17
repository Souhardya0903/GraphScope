"""Fixture behavior tests run independently of GraphScope and FalkorDB."""

import pytest
from fastapi.testclient import TestClient

from examples.commerce import inventory
from examples.commerce.app import app
from examples.commerce.dispatch import dispatch


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_order_and_reservation_share_inventory_validation(client):
    payload = {"product_id": "keyboard", "quantity": 2}
    assert client.post("/orders", json=payload).json() == {"status": "accepted", **payload}
    assert client.post("/reservations", json=payload).json() == {"status": "reserved", **payload}


@pytest.mark.parametrize("route", ["/orders", "/reservations"])
@pytest.mark.parametrize("product,quantity", [("keyboard", 11), ("unknown", 1)])
def test_insufficient_or_unknown_stock(client, route, product, quantity):
    response = client.post(route, json={"product_id": product, "quantity": quantity})
    assert response.status_code == 409
    assert response.json() == {"detail": "Insufficient stock"}


@pytest.mark.parametrize("quantity", [0, -1])
@pytest.mark.parametrize("route", ["/orders", "/reservations"])
def test_invalid_quantity(client, route, quantity):
    assert client.post(route, json={"product_id": "mouse", "quantity": quantity}).status_code == 422


def test_products_remain_available_when_inventory_is_unavailable(client, monkeypatch):
    def unavailable(_product_id):
        raise RuntimeError("Synthetic inventory outage")

    monkeypatch.setattr(inventory, "read_stock", unavailable)
    assert client.get("/products").json() == [
        {"id": "keyboard", "name": "Keyboard"},
        {"id": "mouse", "name": "Mouse"},
    ]
    with pytest.raises(RuntimeError, match="Synthetic inventory outage"):
        client.post("/orders", json={"product_id": "mouse", "quantity": 1})


def test_inventory_adapter_boundary(monkeypatch):
    monkeypatch.setattr(inventory, "read_stock", lambda product: 3 if product == "mouse" else 0)
    assert inventory.read_inventory("mouse") == 3
    assert inventory.validate_stock("mouse", 3)
    assert not inventory.validate_stock("mouse", 4)
    assert not inventory.validate_stock("mouse", 0)


def test_dynamic_dispatch_fixture():
    class Handlers:
        @staticmethod
        def ping():
            return "pong"

    assert dispatch(Handlers(), "ping") == "pong"
    with pytest.raises(AttributeError):
        dispatch(Handlers(), "missing")
