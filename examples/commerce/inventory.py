"""Shared inventory dependency used by orders and reservations."""

from .redis_adapter import read_stock


def read_inventory(product_id: str) -> int:
    return read_stock(product_id)


def validate_stock(product_id: str, quantity: int) -> bool:
    return quantity > 0 and read_inventory(product_id) >= quantity
