"""Local-beta boundaries: trusted hosts/origins and explicit repository roots."""

import json
import os
from pathlib import Path

from fastapi import HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def allowed_path(value):
    raw = Path(value)
    if str(value).startswith(("\\\\", "//")):
        raise HTTPException(403, "Network share paths are not supported by the local server")
    path = raw.resolve(strict=True)
    configured = json.loads(os.environ.get("GRAPHSCOPE_ALLOWED_ROOTS", "[]"))
    if not isinstance(configured, list) or any(not isinstance(v, str) for v in configured):
        raise ValueError("GRAPHSCOPE_ALLOWED_ROOTS must be a JSON list of directories")
    roots = [PROJECT_ROOT, *(Path(v).resolve(strict=True) for v in configured)]
    if not any(path.is_relative_to(root) for root in roots):
        raise HTTPException(
            403, "Repository is outside allowed roots; restart with --allow-root PATH"
        )
    return path


def allowed_origins():
    return [
        f"http://{host}:{port}"
        for host in ("localhost", "127.0.0.1")
        for port in (5173, 5179, 8000, 8080)
    ]
