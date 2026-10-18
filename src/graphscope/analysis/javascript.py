"""Optional Node/TypeScript syntax adapter, normalized to common snapshot entities."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from graphscope.analysis.resources import public_url
from graphscope.ingestion.discovery import SKIP
from graphscope.models import (
    AnalysisGap,
    CallSiteNode,
    EvidenceEdge,
    FileNode,
    FunctionNode,
    ResourceAccess,
)


def extract_javascript(root, snapshot, include_tests):
    root = Path(root)
    files = {}
    for directory, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(
            n
            for n in folders
            if n not in SKIP
            and not n.startswith(".")
            and not (Path(directory) / n).is_symlink()
            and (include_tests or n not in {"tests", "__tests__"})
        )
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix not in {".js", ".jsx", ".ts", ".tsx"} or path.is_symlink():
                continue
            if not include_tests and any(t in name for t in (".test.", ".spec.")):
                continue
            try:
                files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                snapshot.gaps.append(
                    AnalysisGap(
                        path=path.relative_to(root).as_posix(),
                        reason="Unreadable JavaScript/TypeScript file",
                    )
                )
    if not files:
        return
    script = Path(__file__).resolve().parents[3] / "tools" / "javascript" / "extract.cjs"
    node = shutil.which("node")
    if not node or not (script.parent / "node_modules" / "typescript").is_dir():
        raise ValueError(
            "JavaScript/TypeScript requires Node and: npm ci --prefix tools/javascript --ignore-scripts"
        )
    result = subprocess.run(
        [node, str(script)],
        input=json.dumps(files),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    if result.returncode:
        raise ValueError("JavaScript/TypeScript parser failed")
    rows = json.loads(result.stdout)
    symbols = {}
    exports = {r["path"]: r["exports"] for r in rows if not r["errors"]}
    for row in rows:
        path = row["path"]
        module = str(PurePosixPath(path).with_suffix("")).replace("/", ".")
        snapshot.files.append(
            FileNode(
                id=f"{snapshot.id}:file:{path}",
                snapshot_id=snapshot.id,
                relative_path=path,
                module=module,
                content_hash=hashlib.sha256((root / path).read_bytes()).hexdigest(),
                parse_status="error" if row["errors"] else "parsed",
            )
        )
        for gap in row["errors"] + row["gaps"]:
            snapshot.gaps.append(AnalysisGap(path=path, **gap))
        if row["errors"]:
            continue
        counts = {}
        for fn in row["functions"]:
            counts[fn["name"]] = counts.get(fn["name"], 0) + 1
        for fn in row["functions"]:
            function = FunctionNode(
                id=f"{snapshot.id}:{path}:{fn['name']}:{fn['line']}",
                snapshot_id=snapshot.id,
                qualified_name=f"{module}.{fn['name']}",
                name=fn["name"],
                module=module,
                file_path=path,
                start_line=fn["line"],
                end_line=fn["end"],
                signature=f"{fn['name']}({', '.join(fn['parameters'])})",
                is_async=fn["async"],
            )
            snapshot.functions.append(function)
            fn["id"] = function.id
            if counts[fn["name"]] == 1:
                symbols[path, fn["name"]] = function.id
    for row in rows:
        if row["errors"]:
            continue
        for fn in row["functions"]:
            for call in fn["calls"]:
                target = None
                text = call["target"]
                if not call["blocked"]:
                    parts = text.split(".")
                    imported = row["imports"].get(parts[0])
                    if imported and imported[0].startswith("."):
                        # Normalize relative imports without allowing escape from root.
                        import posixpath

                        base = posixpath.normpath(
                            str(PurePosixPath(row["path"]).parent / imported[0])
                        )
                        candidates = [
                            base,
                            *(base + ext for ext in (".ts", ".tsx", ".js", ".jsx")),
                            *(base + "/index" + ext for ext in (".ts", ".tsx", ".js", ".jsx")),
                        ]
                        member = (
                            imported[1]
                            if len(parts) == 1
                            else parts[1]
                            if len(parts) == 2 and imported[1] is None
                            else None
                        )
                        # Direct API imports with .js extensions can refer to TS sources.
                        if base.endswith(".js"):
                            candidates.extend([base[:-3] + ".ts", base[:-3] + ".tsx"])
                        matches = [
                            symbols[(p, exports[p][member])]
                            for p in candidates
                            if p in exports
                            and member in exports[p]
                            and (p, exports[p][member]) in symbols
                        ]
                        if len(set(matches)) == 1:
                            target = matches[0]
                    elif len(parts) == 1:
                        target = symbols.get((row["path"], text))
                site = CallSiteNode(
                    id=f"{fn['id']}:call:{call['column']}",
                    snapshot_id=snapshot.id,
                    owner_id=fn["id"],
                    file_path=row["path"],
                    line=call["line"],
                    end_line=call["end"],
                    target_text=text,
                    target_id=target,
                    resolution_status="resolved" if target else "unresolved",
                    reason="Explicit syntax binding"
                    if target
                    else "Dynamic, external, shadowed, or unsupported JavaScript binding",
                )
                snapshot.callsites.append(site)
                if target:
                    snapshot.calls.append(
                        EvidenceEdge(
                            caller_id=fn["id"],
                            callee_id=target,
                            callsite_id=site.id,
                            file_path=row["path"],
                            line=call["line"],
                            rule="typescript-explicit-binding-v1",
                        )
                    )
        for r in row["resources"]:
            owner = symbols.get((row["path"], r["owner"]))
            if owner:
                value = public_url(r["value"]) if r["value"] else None
                snapshot.resources.append(
                    ResourceAccess(
                        id=f"{owner}:http:{r['line']}:{r['column']}",
                        snapshot_id=snapshot.id,
                        owner_id=owner,
                        kind="http",
                        operation="fetch",
                        value=value,
                        method=r["method"],
                        file_path=row["path"],
                        line=r["line"],
                        rule="javascript-literal-fetch-v1",
                    )
                )
                if value is None:
                    snapshot.gaps.append(
                        AnalysisGap(
                            path=row["path"],
                            line=r["line"],
                            reason="Dynamic or relative fetch destination needs explicit service mapping",
                        )
                    )
    snapshot.metadata["languages"] = sorted(
        set(snapshot.metadata.get("languages", [])) | {"javascript/typescript"}
    )
