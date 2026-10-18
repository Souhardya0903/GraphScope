import subprocess
from pathlib import Path


def git(root, *args):
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
        check=False,
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise ValueError("Git operation failed; check repository and revision arguments")
    return result.stdout


def revision(root, ref):
    # Resolve to an object ID before using user input in further Git operations.
    return (
        git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    )


def repository_metadata(root):
    result = {
        "languages": ["python"],
        "tests_included": False,
        "coverage": "static subset; unresolved calls and external behavior remain gaps",
    }
    try:
        result.update(
            commit=revision(root, "HEAD"),
            dirty=bool(git(root, "status", "--porcelain", "--untracked-files=normal", "--", ".")),
            repository_root=str(Path(git(root, "rev-parse", "--show-toplevel").decode().strip())),
        )
    except (ValueError, OSError, subprocess.TimeoutExpired):
        result.update(commit=None, dirty=None)
    return result
