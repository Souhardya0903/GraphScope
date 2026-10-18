"""Read Git trees/index/worktree without checkouts, hooks, or source execution."""

import difflib
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from graphscope.analysis.metadata import git, revision
from graphscope.analysis.repository import UNSUPPORTED
from graphscope.ingestion.discovery import SKIP

SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".sql",
} | UNSUPPORTED
MAX_FILES, MAX_BYTES = 10000, 50_000_000


def accepted(name):
    path = Path(name)
    return (
        path.suffix.lower() in SUFFIXES
        and not path.is_absolute()
        and not any(p.startswith(".") or p in SKIP or p == ".." for p in path.parts)
        and path.name not in {"package-lock.json", "pnpm-lock.yaml"}
    )


def read_tree(root, ref="HEAD"):
    root = Path(root).resolve(strict=True)
    prefix = git(root, "rev-parse", "--show-prefix").decode().strip()
    if ref == "worktree":
        names = set(
            git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", ".")
            .decode()
            .split("\0")
        )
        result = {}
        for name in sorted(names):
            path = root / name
            if name and accepted(name) and path.is_file() and not path.is_symlink():
                if not path.resolve().is_relative_to(root):
                    raise ValueError("Source path escapes repository root")
                if (
                    path.stat().st_size > MAX_BYTES
                    or sum(map(len, result.values())) + path.stat().st_size > MAX_BYTES
                ):
                    raise ValueError("Repository exceeds 50 MB analysis budget")
                result[name] = path.read_bytes()
                check_size(result)
        return result, {
            "revision": "worktree",
            "commit": revision(root, "HEAD"),
            "dirty": bool(git(root, "status", "--porcelain", "--", ".")),
        }
    if ref == "index":
        rows = git(root, "ls-files", "--stage", "-z", "--", ".").decode().split("\0")
        entries = []
        for row in filter(None, rows):
            header, name = row.split("\t", 1)
            mode, oid, stage = header.split()
            if stage != "0":
                raise ValueError("Resolve Git merge conflicts before analysis")
            entries.append((mode, oid, name))
        commit = revision(root, "HEAD")
    else:
        commit = revision(root, ref)
        rows = (
            git(root, "ls-tree", "--full-name", "-r", "-z", commit, "--", ".").decode().split("\0")
        )
        entries = []
        for row in filter(None, rows):
            header, name = row.split("\t", 1)
            mode, kind, oid = header.split()
            if prefix:
                if not name.startswith(prefix):
                    continue
                name = name[len(prefix) :]
            if kind == "blob":
                entries.append((mode, oid, name))
    result = {}
    for mode, oid, name in entries:
        if mode in {"100644", "100755"} and accepted(name):
            size = int(git(root, "cat-file", "-s", oid))
            if size > MAX_BYTES or sum(map(len, result.values())) + size > MAX_BYTES:
                raise ValueError("Repository exceeds 50 MB analysis budget")
            result[name] = git(root, "cat-file", "blob", oid)
            check_size(result)
    return result, {"revision": ref, "commit": commit, "dirty": None if ref == "index" else False}


def check_size(files):
    if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError("Repository exceeds analysis budget (10,000 files / 50 MB)")


def snapshot_files(files, origin, include_tests=True):
    from graphscope.analysis.repository import analyze

    temporary_root = Path.cwd() / "reports" / "analysis-tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="snapshot-", dir=temporary_root) as directory:
        root = Path(directory)
        for name, content in files.items():
            path = root / name
            if not accepted(name) or not path.resolve().is_relative_to(root):
                raise ValueError("Invalid source path")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        snapshot = analyze(root, include_tests=include_tests)
        snapshot.root = str(origin)
        snapshot.metadata["repository_root"] = str(origin)
        return snapshot


def changed_symbols(before, after, old_files, new_files):
    changes, gaps = [], []
    for name in sorted(old_files.keys() | new_files.keys()):
        old, new = old_files.get(name), new_files.get(name)
        if old == new or (
            old is not None and new is not None and old.splitlines() == new.splitlines()
        ):
            continue
        ranges = {"before": [], "after": []}
        for tag, a, b, c, d in difflib.SequenceMatcher(
            a=(old or b"").splitlines(), b=(new or b"").splitlines(), autojunk=False
        ).get_opcodes():
            if tag != "equal":
                ranges["before"].append((a + 1, b))
                ranges["after"].append((c + 1, d))
        record = {
            "file_path": name,
            "status": "added" if old is None else "deleted" if new is None else "modified",
            "ranges": ranges,
            "symbols": [],
        }
        for side, snapshot in (("before", before), ("after", after)):
            functions = [f for f in snapshot.functions if f.file_path == name]
            touched = []
            outside = False
            for start, end in ranges[side]:
                if end < start:  # No lines on this side of an insertion/deletion.
                    continue
                covered = set()
                for function in functions:
                    if function.start_line <= end and function.end_line >= start:
                        touched.append(function)
                        covered.update(
                            range(max(start, function.start_line), min(end, function.end_line) + 1)
                        )
                if len(covered) < end - start + 1:
                    outside = True
            if outside:
                touched = functions  # Imports/config/class attributes may affect every function.
                gaps.append(
                    {
                        "file_path": name,
                        "side": side,
                        "reason": "Change outside function bodies; all file functions conservatively selected",
                    }
                )
            seen = set()
            for f in touched:
                if f.id not in seen:
                    seen.add(f.id)
                    record["symbols"].append(
                        {
                            "side": side,
                            "id": f.id,
                            "name": f.qualified_name,
                            "reason": "file-level conservative impact"
                            if outside
                            else "changed line overlaps symbol",
                        }
                    )
        # Retain both sides of modified functions, including pure line deletions.
        originals = list(record["symbols"])
        for selected in originals:
            opposite = "after" if selected["side"] == "before" else "before"
            snapshot = after if opposite == "after" else before
            for function in snapshot.functions:
                if (
                    function.file_path == name
                    and function.qualified_name == selected["name"]
                    and not any(
                        x["side"] == opposite and x["id"] == function.id for x in record["symbols"]
                    )
                ):
                    record["symbols"].append(
                        {
                            "side": opposite,
                            "id": function.id,
                            "name": function.qualified_name,
                            "reason": "counterpart of changed symbol",
                        }
                    )
        if name.lower().endswith(".sql"):
            tables = set(
                re.findall(
                    r"\b(?:ALTER|CREATE|DROP)\s+TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([\w.]+)",
                    (old or b"").decode("utf-8", errors="replace")
                    + "\n"
                    + (new or b"").decode("utf-8", errors="replace"),
                    flags=re.IGNORECASE,
                )
            )
            for side, snapshot in (("before", before), ("after", after)):
                owners = {
                    r.owner_id for r in snapshot.resources if r.kind == "sql" and r.value in tables
                }
                for function in snapshot.functions:
                    if function.id in owners:
                        record["symbols"].append(
                            {
                                "side": side,
                                "id": function.id,
                                "name": function.qualified_name,
                                "reason": "Literal SQL table access matches changed schema; inferred resource impact",
                            }
                        )
            gaps.append(
                {
                    "file_path": name,
                    "reason": "SQL schema matching covers simple unquoted table names only; migration/runtime semantics require review",
                }
            )
        if not record["symbols"]:
            gaps.append(
                {
                    "file_path": name,
                    "reason": "No mapped function; resource/config/schema impact requires review",
                }
            )
        changes.append(record)
    return changes, gaps


def compare(root, base="HEAD", head="worktree", max_depth=12, max_paths=500):
    from graphscope.analysis.impact import impact

    old, old_meta = read_tree(root, base)
    new, new_meta = read_tree(root, head)
    before, after = snapshot_files(old, root), snapshot_files(new, root)
    before.metadata.update(old_meta)
    after.metadata.update(new_meta)
    changes, gaps = changed_symbols(before, after, old, new)
    targets = {
        side: sorted({s["id"] for c in changes for s in c["symbols"] if s["side"] == side})
        for side in ("before", "after")
    }
    return {
        "mode": "actual-change",
        "base": old_meta,
        "head": new_meta,
        "changes": changes,
        "change_gaps": gaps,
        "before": impact(before, targets["before"], max_depth, max_paths),
        "after": impact(after, targets["after"], max_depth, max_paths),
        "caveat": "Potential static impact, not proof of runtime failure. Before paths preserve deleted symbols. Renames appear as deletion/addition or modified files.",
    }
