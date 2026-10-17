"""A second operation depending on the same inventory function."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .inventory import validate_stock

router = APIRouter()


class ReservationRequest(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(gt=0)


@router.post("/reservations")
def reserve_stock(request: ReservationRequest) -> dict:
    if not validate_stock(request.product_id, request.quantity):
        raise HTTPException(status_code=409, detail="Insufficient stock")
    return {"status": "reserved", "product_id": request.product_id, "quantity": request.quantity}
