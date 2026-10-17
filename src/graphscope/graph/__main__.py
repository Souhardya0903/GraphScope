"""Index source in FalkorDB or investigate an already stored snapshot."""

import argparse
import json
import sys
from pathlib import Path

from redis.exceptions import RedisError

from graphscope.graph.client import select_graph
from graphscope.graph.queries import GraphQueries
from graphscope.graph.repository import GraphRepository
from graphscope.ingestion.pipeline import ingest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", help="Defaults to FALKORDB_GRAPH from .env")
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index")
    index.add_argument("root", type=Path)
    index.add_argument("--target", help="Investigate after indexing")
    impact = commands.add_parser("investigate")
    impact.add_argument("snapshot_id")
    impact.add_argument("target")
    for command in (index, impact):
        command.add_argument("--max-depth", type=int, default=8)
        command.add_argument("--max-paths", type=int, default=100)
    args = parser.parse_args()
    try:
        graph = select_graph(args.graph)
        if args.command == "index":
            snapshot = ingest(args.root)
            GraphRepository(graph).store(snapshot)
            result = {
                "snapshot_id": snapshot.id,
                "status": "ready",
                "files": len(snapshot.files),
                "functions": len(snapshot.functions),
                "calls": len(snapshot.calls),
                "endpoints": len(snapshot.endpoints),
            }
            if args.target:
                result["investigation"] = GraphQueries(graph).investigate(
                    snapshot.id, args.target, args.max_depth, args.max_paths
                )
        else:
            result = GraphQueries(graph).investigate(
                args.snapshot_id, args.target, args.max_depth, args.max_paths
            )
        print(json.dumps(result, indent=2))
    except RedisError:
        print(
            "FalkorDB operation failed. Check the service and .env connection settings.",
            file=sys.stderr,
        )
        return 1
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
