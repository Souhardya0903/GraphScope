"""Resolve supported calls in a second pass and retain unresolved sites as gaps."""

import ast

from graphscope.models import AnalysisGap, EvidenceEdge


def bind_imports(module, snapshot):
    for node in module.tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    module.wildcard = True
                    snapshot.gaps.append(
                        AnalysisGap(
                            path=module.path,
                            line=node.lineno,
                            reason="Wildcard import prevents reliable resolution",
                        )
                    )
                    continue
                base = module.name.split(".") if module.name else []
                if not module.is_package:
                    base = base[:-1]
                if node.level:
                    if node.level - 1 > len(base):
                        continue
                    base = base[: len(base) - node.level + 1]
                    imported = ".".join([*base, *([node.module] if node.module else [])])
                else:
                    imported = node.module or ""
                module.imports[alias.asname or alias.name] = (imported, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module.imports[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0],
                    None,
                )


def binding(module, text):
    """Return an explicit (module, member) binding, never guess by short name."""
    parts = text.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        return None
    first = parts[0]
    if module.wildcard or first in module.blocked or module.bindings[first] != 1:
        return None
    if len(parts) == 1:
        return module.imports.get(first, (module.name, first))
    imported = module.imports.get(first)
    if imported and imported[1] is None and len(parts) == 2:
        return imported[0], parts[1]
    return None


def resolve(modules, snapshot):
    symbols = {}
    for module in modules.values():
        bind_imports(module, snapshot)
        for node in module.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                module.bindings[node.name] == 1
                and node.name not in module.blocked
                and not node.decorator_list
            ):
                symbols[(module.name, node.name)] = module.functions[node.lineno].id
    owners = {f.id: module for module in modules.values() for f in module.functions.values()}
    for call in snapshot.callsites:
        module = owners[call.owner_id]
        first = call.target_text.split(".")[0]
        if first in module.function_blocks[call.owner_id]:
            call.reason = "Local binding or parameter shadows the target"
            continue
        target = symbols.get(binding(module, call.target_text))
        if target is None:
            call.reason = "Dynamic, external, ambiguous, decorated, or unsupported target"
            continue
        call.target_id, call.resolution_status, call.reason = (
            target,
            "resolved",
            "Explicit static binding",
        )
        snapshot.calls.append(
            EvidenceEdge(
                caller_id=call.owner_id,
                callee_id=target,
                callsite_id=call.id,
                file_path=call.file_path,
                line=call.line,
            )
        )
