"""Verify a real graph write/read in a disposable, uniquely named graph."""

import os
from uuid import uuid4

from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()


def main() -> None:
    """Check the server without modifying any application graph."""
    raw_host = os.environ.get("FALKORDB_HOST", "localhost").strip()
    raw_port = os.environ.get("FALKORDB_PORT", "").strip()

    if ":" in raw_host:
        host, host_port = raw_host.split(":", 1)
        port = int(host_port)
    else:
        host = raw_host
        port = int(raw_port) if raw_port else 6379

    username = os.environ.get("FALKORDB_USERNAME", "").strip() or None
    password = os.environ.get("FALKORDB_PASSWORD", "").strip() or None
    ssl = os.environ.get("FALKORDB_SSL", "false").lower() in ("true", "1", "yes")

    print(f"Connecting to FalkorDB at {host}:{port} (username={username}, ssl={ssl})...")
    db = FalkorDB(
        host=host,
        port=port,
        username=username,
        password=password,
        ssl=ssl,
        socket_connect_timeout=10,
        socket_timeout=10,
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
