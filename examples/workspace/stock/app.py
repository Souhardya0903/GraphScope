"""Static analysis fixture; illustrative broker/cache/cursor bindings are not executed."""

from fastapi import FastAPI

app = FastAPI()


def validate_stock(quantity: int):
    return quantity > 0


def read_stock():
    return cache.get("inventory")  # noqa: F821


@app.get("/stock/{item}")
def get_stock(item: str):
    return {"available": validate_stock(1), "stock": read_stock()}


def publish_order():
    broker.publish("orders.created")  # noqa: F821
