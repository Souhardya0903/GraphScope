"""Resolve supported calls in a second pass and retain unresolved sites as gaps."""

import ast
import builtins

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
    if imported and imported[1] is None:
        return imported[0], ".".join(parts[1:])
    if imported and imported[1] is not None:
        return imported[0], ".".join([imported[1], *parts[1:]])
    if first in module.class_bases:
        return module.name, ".".join(parts)
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
    for module in modules.values():
        for line, function in module.functions.items():
            cls = module.method_classes.get(function.id)
            node = module.definitions[line]
            decorators = {ast.unparse(d) for d in node.decorator_list}
            if (
                cls
                and module.bindings[cls] == 1
                and decorators <= {"staticmethod", "classmethod"}
                and sum(
                    f.name == function.name and module.method_classes.get(f.id) == cls
                    for f in module.functions.values()
                )
                == 1
            ):
                symbols[(module.name, f"{cls}.{function.name}")] = function.id
    owners = {f.id: module for module in modules.values() for f in module.functions.values()}

    def lookup(key):
        if key is None:
            return None
        if key in symbols:
            return symbols[key]
        # `from package import submodule; submodule.work()` binds a module,
        # not a function called `submodule.work` in the package initializer.
        origin, member = key
        parts = member.split(".")
        matches = {
            symbols[(candidate, rest)]
            for index in range(1, len(parts))
            if (candidate := ".".join([origin, *parts[:index]])) in modules
            and (rest := ".".join(parts[index:]))
            and (candidate, rest) in symbols
        }
        return next(iter(matches)) if len(matches) == 1 else None

    # Follow only explicit, unambiguous module-level import re-exports.
    # Cycles without a concrete definition stay unresolved.
    for _ in range(len(modules) + 1):
        added = False
        for module in modules.values():
            for alias, imported in module.imports.items():
                key = (module.name, alias)
                if (
                    key not in symbols
                    and imported[1] is not None
                    and module.bindings[alias] == 1
                    and alias not in module.blocked
                    and not module.wildcard
                    and (target := lookup(imported)) is not None
                ):
                    symbols[key] = target
                    added = True
        if not added:
            break
    # Resolve explicit Class.method lookups through single, statically bound bases.
    # self/super/instance calls remain unresolved because runtime overrides may differ.
    for _ in range(len(modules) + sum(len(m.class_bases) for m in modules.values())):
        added = False
        for module in modules.values():
            for cls, bases in module.class_bases.items():
                if len(bases) != 1 or module.bindings[cls] != 1:
                    continue
                base = binding(module, bases[0])
                if base is None:
                    continue
                base_module, base_name = base
                for (owner_module, member), target in list(symbols.items()):
                    if owner_module == base_module and member.startswith(base_name + "."):
                        inherited = (module.name, cls + member[len(base_name) :])
                        if inherited not in symbols:
                            # A decorated/ambiguous override blocks inheritance too.
                            method = member[len(base_name) + 1 :]
                            if any(
                                module.method_classes.get(f.id) == cls and f.name == method
                                for f in module.functions.values()
                            ):
                                continue
                            symbols[inherited] = target
                            added = True
        if not added:
            break
    for call in snapshot.callsites:
        module = owners[call.owner_id]
        first = call.target_text.split(".")[0]
        if first in module.function_blocks[call.owner_id]:
            call.reason = "Local binding or parameter shadows the target"
            continue
        target = lookup(binding(module, call.target_text))
        if target is None:
            if (
                call.target_text.isidentifier()
                and first not in module.bindings
                and hasattr(builtins, first)
                and not module.wildcard
                and first not in module.blocked
            ):
                call.reason = "Python builtin call; no repository function target"
            else:
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
