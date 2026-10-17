"""Extract a local Python repository without executing it or connecting to FalkorDB."""

import argparse
from pathlib import Path

from graphscope.ingestion.pipeline import ingest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--include-tests", action="store_true")
    parser.add_argument("--output", type=Path, help="Write full snapshot JSON to this file")
    args = parser.parse_args()
    snapshot = ingest(args.root, args.include_tests)
    summary = {
        "snapshot_id": snapshot.id,
        "files": len(snapshot.files),
        "parse_errors": sum(f.parse_status == "error" for f in snapshot.files),
        "functions": len(snapshot.functions),
        "resolved_calls": len(snapshot.calls),
        "unresolved_calls": sum(c.resolution_status == "unresolved" for c in snapshot.callsites),
        "endpoints": [f"{e.method} {e.path}" for e in snapshot.endpoints],
        "gaps": len(snapshot.gaps),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    import json

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
