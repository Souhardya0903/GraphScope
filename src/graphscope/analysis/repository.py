import os
from pathlib import Path

from graphscope.analysis.javascript import extract_javascript
from graphscope.ingestion.discovery import SKIP
from graphscope.ingestion.pipeline import ingest
from graphscope.models import AnalysisGap

UNSUPPORTED = {
    ".go",
    ".java",
    ".rs",
    ".cs",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".kt",
    ".scala",
    ".swift",
    ".vue",
    ".svelte",
    ".mjs",
    ".cjs",
}


def analyze(root, include_tests=True):
    root = Path(root).resolve(strict=True)
    count, size = 0, 0
    unsupported = []

    def unreadable(error):
        raise ValueError(
            "Repository contains unreadable directories; narrow the root or fix permissions"
        ) from error

    for directory, folders, names in os.walk(root, followlinks=False, onerror=unreadable):
        folders[:] = [
            name
            for name in folders
            if not name.startswith(".")
            and name not in SKIP
            and not (Path(directory) / name).is_symlink()
        ]
        for name in names:
            path = Path(directory) / name
            if path.suffix in UNSUPPORTED and not path.is_symlink():
                unsupported.append(path.relative_to(root).as_posix())
            if path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"} and not path.is_symlink():
                count += 1
                size += path.stat().st_size
                if count > 10000 or size > 50_000_000:
                    raise ValueError(
                        "Repository exceeds analysis budget (10,000 files / 50 MB); narrow the root"
                    )
    snapshot = ingest(root, include_tests=include_tests)
    snapshot.metadata["languages"] = ["python"] if snapshot.files else []
    extract_javascript(root, snapshot, include_tests)
    for path in sorted(unsupported):
        snapshot.gaps.append(
            AnalysisGap(
                path=path,
                reason="Source language/framework adapter is not supported; dependencies may be missing",
            )
        )
    snapshot.metadata["analysis_version"] = "1"
    return snapshot
