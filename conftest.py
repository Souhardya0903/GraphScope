"""Keep pytest's temporary files out of shared Windows temp directories."""

from uuid import uuid4

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Allocate a fresh per-run path; preserve explicitly supplied --basetemp."""
    if config.option.basetemp is not None:
        return
    root = config.rootpath.resolve()
    parent = (root / "reports").resolve()
    if not parent.is_relative_to(root):
        raise pytest.UsageError("Test reports directory must stay inside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    # Do not reuse a directory: pytest may delete the contents of --basetemp.
    config.option.basetemp = str(parent / f"pytest-{uuid4().hex}")
