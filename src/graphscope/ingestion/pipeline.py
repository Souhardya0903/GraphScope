"""Coordinate extraction, validation, and publication of a complete snapshot."""

import ast
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from graphscope.ingestion.discovery import discover, module_name
from graphscope.ingestion.extractor import collect
from graphscope.ingestion.resolver import resolve
from graphscope.ingestion.routes import extract_routes
from graphscope.models import AnalysisGap, FileNode, Snapshot


def ingest(root: Path | str, include_tests: bool = False) -> Snapshot:
    """Return an extracted snapshot; no source imports, execution, or database writes."""
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source root must be a directory")
    snapshot = Snapshot(id=uuid4().hex, root=str(root), indexed_at=datetime.now(UTC).isoformat())
    modules = {}
    for path in discover(root, include_tests):
        relative = path.relative_to(root)
        name, module = relative.as_posix(), module_name(relative)
        try:
            source = path.read_bytes()
        except OSError as error:
            snapshot.gaps.append(AnalysisGap(path=name, reason=f"Unreadable file: {error}"))
            continue
        file = FileNode(
            id=f"{snapshot.id}:file:{name}",
            snapshot_id=snapshot.id,
            relative_path=name,
            module=module,
            content_hash=hashlib.sha256(source).hexdigest(),
            parse_status="parsed",
        )
        snapshot.files.append(file)
        try:
            tree = ast.parse(source, filename=name)
        except (SyntaxError, UnicodeError) as error:
            file.parse_status = "error"
            snapshot.gaps.append(
                AnalysisGap(
                    path=name, line=getattr(error, "lineno", None), reason=f"Parse error: {error}"
                )
            )
            continue
        if module in modules:
            raise ValueError(f"Ambiguous module identity: {module}")
        modules[module] = collect(tree, module, name, snapshot, path.name == "__init__.py")
    resolve(modules, snapshot)
    extract_routes(modules, snapshot)
    return snapshot
