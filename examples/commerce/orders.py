"""Order endpoint and service function with an explicit inventory call."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .inventory import validate_stock

router = APIRouter()


class OrderRequest(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)


def place_order(product_id: str, quantity: int) -> dict:
    if not validate_stock(product_id, quantity):
        raise HTTPException(status_code=409, detail="Insufficient stock")
    return {"status": "accepted", "product_id": product_id, "quantity": quantity}


@router.post("/orders")
def create_order(request: OrderRequest) -> dict:
    return place_order(request.product_id, request.quantity)
