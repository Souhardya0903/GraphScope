"""Runnable demo application, separate from GraphScope's own future API."""

from fastapi import FastAPI

from .orders import router as orders_router
from .products import router as products_router
from .reservations import router as reservations_router

app = FastAPI(title="GraphScope synthetic commerce", version="0.1.0")
app.include_router(orders_router)
app.include_router(reservations_router)
app.include_router(products_router)
