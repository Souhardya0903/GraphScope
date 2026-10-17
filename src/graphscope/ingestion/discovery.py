"""Discover Python files and collect repository metadata and file hashes."""

import os
from pathlib import Path

SKIP = {"venv", "env", "__pycache__", "node_modules", "build", "dist", "reports", "cloned_repos"}


def discover(root: Path, include_tests: bool = False):
    """Prune ignored directories before walking; never follow symlink directories."""
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(
            name
            for name in folders
            if not name.startswith(".")
            and name not in SKIP
            and (include_tests or name != "tests")
            and not (Path(directory) / name).is_symlink()
        )
        for name in sorted(names):
            if name.startswith(".") or not name.endswith(".py"):
                continue
            if not include_tests and (name.startswith("test_") or name.endswith("_test.py")):
                continue
            path = Path(directory) / name
            if not path.is_symlink() and path.resolve().is_relative_to(root):
                yield path


def module_name(relative: Path) -> str:
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)
