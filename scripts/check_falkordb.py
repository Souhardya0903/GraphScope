"""Verify a real graph write/read in a disposable, uniquely named graph."""

import os
from uuid import uuid4

from falkordb import FalkorDB


def main() -> None:
    """Check the server without modifying any application graph."""
    db = FalkorDB(
        host=os.environ.get("FALKORDB_HOST", "localhost"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        password=os.environ.get("FALKORDB_PASSWORD") or None,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    graph = db.select_graph(f"graphscope_check_{uuid4().hex}")
    created = False
    try:
        graph.query("CREATE (:SetupCheck {value: $value})", {"value": "ok"})
        created = True
        result = graph.query("MATCH (n:SetupCheck) RETURN n.value")
        if result.result_set != [["ok"]]:
            raise RuntimeError(f"Unexpected graph result: {result.result_set!r}")
        print("FalkorDB graph write/read passed.")
    finally:
        if created:
            graph.delete()


if __name__ == "__main__":
    main()
