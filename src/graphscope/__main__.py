"""Single-origin local server and configuration diagnostics."""

import argparse
import json
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--allow-root", action="append", default=[])
    commands.add_parser("doctor")
    args = parser.parse_args()
    if args.command == "doctor":
        report = {
            "python": True,
            "git": bool(shutil.which("git")),
            "node": bool(shutil.which("node")),
            "parser_installed": (root / "tools/javascript/node_modules/typescript").is_dir(),
            "frontend_built": (root / "frontend/dist/index.html").is_file(),
            "falkordb_host_configured": bool(os.environ.get("FALKORDB_HOST")),
            "providers_configured": {
                name: bool(os.environ.get(name.upper() + "_API_KEY"))
                and bool(os.environ.get(name.upper() + "_MODEL"))
                for name in ("ollama", "gemini", "openai")
            },
        }
        print(json.dumps(report, indent=2))
        return (
            0
            if all(report[k] for k in ("git", "node", "parser_installed", "frontend_built"))
            else 1
        )
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1..65535")
    if not (root / "frontend/dist/index.html").is_file():
        parser.error(
            "Frontend is not built. Run npm ci --prefix frontend and npm --prefix frontend run build"
        )
    paths = []
    for value in args.allow_root:
        path = Path(value).resolve(strict=True)
        if not path.is_dir():
            parser.error("Allowed roots must be directories")
        paths.append(str(path))
    if paths:
        os.environ["GRAPHSCOPE_ALLOWED_ROOTS"] = json.dumps(paths)
    import uvicorn

    uvicorn.run("graphscope.api.main:app", host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
