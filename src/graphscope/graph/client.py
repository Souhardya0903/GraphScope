"""FalkorDB client lifecycle and connection configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from falkordb import FalkorDB


def connect() -> FalkorDB:
    """Use the client's pooled connections; keep credentials out of query results."""
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    host = os.environ.get("FALKORDB_HOST", "localhost").strip()
    port = os.environ.get("FALKORDB_PORT", "6379").strip() or "6379"
    if host.count(":") == 1:
        host, port = host.rsplit(":", 1)
    return FalkorDB(
        host=host,
        port=int(port),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        ssl=os.environ.get("FALKORDB_SSL", "false").lower() in {"true", "1", "yes"},
        ssl_cert_reqs="required",
        socket_connect_timeout=10,
        socket_timeout=15,
        max_connections=10,
    )


def select_graph(name: str | None = None):
    db = connect()
    return db.select_graph(name or os.environ.get("FALKORDB_GRAPH", "graphscope"))
