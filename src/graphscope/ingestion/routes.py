"""Resolve a bounded subset of literal FastAPI routes and router mounts."""

import ast

from graphscope.ingestion.resolver import binding
from graphscope.models import AnalysisGap, EndpointNode, SourceReference

METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def literal_prefix(call):
    keyword = next((k for k in call.keywords if k.arg == "prefix"), None)
    if keyword is None:
        return ""
    if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
        value = keyword.value.value
        if value == "" or (value.startswith("/") and not value.endswith("/")):
            return value
    return None


def extract_routes(modules, snapshot):
    objects, mounts, declarations = {}, {}, {}

    def gap(module, node, reason):
        snapshot.gaps.append(AnalysisGap(path=module.path, line=node.lineno, reason=reason))

    for module in modules.values():
        for node in module.tree.body:
            if not (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                continue
            call = node.value
            kind = binding(module, ast.unparse(call.func))
            if kind not in {("fastapi", "FastAPI"), ("fastapi", "APIRouter")}:
                continue
            name = node.targets[0].id
            prefix = literal_prefix(call)
            if (
                module.bindings[name] != 1
                or prefix is None
                or call.args
                or any(
                    k.arg is None or k.arg in {"routes", "dependencies", "root_path"}
                    for k in call.keywords
                )
            ):
                gap(module, node, "Ambiguous application/router configuration unsupported")
                continue
            key = (module.name, name)
            objects[key] = (kind[1], prefix)
            mounts[key], declarations[key] = [], []

    for module in modules.values():
        for node in module.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                    ):
                        gap(module, decorator, "Unsupported decorator")
                        continue
                    key = binding(module, ast.unparse(decorator.func.value))
                    method = decorator.func.attr
                    path = decorator.args[0] if len(decorator.args) == 1 else None
                    if (
                        key not in objects
                        or method not in METHODS
                        or path is None
                        or not isinstance(path, ast.Constant)
                        or not isinstance(path.value, str)
                        or not path.value.startswith("/")
                        or any(k.arg is None or k.arg == "dependencies" for k in decorator.keywords)
                        or len(node.decorator_list) != 1
                    ):
                        gap(module, decorator, "Unsupported route or stacked decorator")
                        continue
                    declarations[key].append((module, node, decorator, method.upper(), path.value))
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
            ):
                continue
            call = node.value
            if call.func.attr not in {"include_router", "mount"}:
                continue
            parent = binding(module, ast.unparse(call.func.value))
            child = binding(module, ast.unparse(call.args[0])) if len(call.args) == 1 else None
            prefix = literal_prefix(call)
            if (
                call.func.attr != "include_router"
                or parent not in objects
                or child not in objects
                or objects[child][0] != "APIRouter"
                or prefix is None
                or any(k.arg != "prefix" for k in call.keywords)
            ):
                gap(module, node, "Unsupported router mount; effective routes may be missing")
                continue
            mounts[parent].append(
                (
                    child,
                    prefix,
                    SourceReference(
                        path=module.path, line=call.lineno, rule="literal-include-router"
                    ),
                )
            )

    visited_routers = set()
    expansions = 0

    def expand(key, prefix, evidence, ancestry):
        nonlocal expansions
        expansions += 1
        if expansions > 1000 or len(snapshot.endpoints) >= 10000:
            if not any(g.reason == "Route expansion limit reached" for g in snapshot.gaps):
                snapshot.gaps.append(
                    AnalysisGap(path="<routes>", reason="Route expansion limit reached")
                )
            return
        if key in ancestry or len(ancestry) >= 20:
            snapshot.gaps.append(
                AnalysisGap(path="<routes>", reason="Router cycle or mount depth limit")
            )
            return
        visited_routers.add(key)
        prefix += objects[key][1]
        for module, node, decorator, method, route in declarations[key]:
            handler = module.functions[node.lineno]
            snapshot.endpoints.append(
                EndpointNode(
                    id=f"{snapshot.id}:endpoint:{len(snapshot.endpoints)}",
                    snapshot_id=snapshot.id,
                    method=method,
                    path=prefix + route,
                    handler_id=handler.id,
                    file_path=module.path,
                    line=decorator.lineno,
                    mount_evidence=evidence,
                )
            )
        for child, extra, source in mounts[key]:
            expand(child, prefix + extra, [*evidence, source], [*ancestry, key])

    for key, (kind, _) in objects.items():
        if kind == "FastAPI":
            expand(key, "", [], [])
    for key in objects:
        if declarations[key] and key not in visited_routers:
            module = modules[key[0]]
            gap(
                module,
                module.tree.body[0],
                "Router declarations are not mounted on a supported application",
            )
