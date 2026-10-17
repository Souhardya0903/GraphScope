"""In-memory stand-in for Redis GET; no Redis connection is made in this fixture."""

STOCK = {"keyboard": 10, "mouse": 5}


def read_stock(product_id: str) -> int:
    """Represent the resource boundary while keeping demo tests self-contained."""
    return STOCK.get(product_id, 0)
