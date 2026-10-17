"""Product browsing deliberately has no dependency on inventory validation."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/products")
def list_products() -> list[dict]:
    return [{"id": "keyboard", "name": "Keyboard"}, {"id": "mouse", "name": "Mouse"}]
