"""Evidence-backed literal access extraction; conventions are labelled inferred."""

import ast
import re
from urllib.parse import urlsplit, urlunsplit

from graphscope.models import AnalysisGap, ResourceAccess


def public_url(value):
    """Do not retain credentials, query parameters, or fragments from URLs."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if parsed.port:
            host += f":{parsed.port}"
        return urlunsplit((parsed.scheme, host, parsed.path or "/", "", ""))
    except ValueError:
        return None


def extract_resources(modules, snapshot):
    for module in modules.values():
        owned_calls = {}

        class ResourceCalls(ast.NodeVisitor):
            def __init__(self, owner, mapping):
                self.owner = owner
                self.mapping = mapping

            def visit_Call(self, node):
                self.mapping[node] = self.owner
                self.generic_visit(node)

            def visit_FunctionDef(self, node):
                pass

            visit_AsyncFunctionDef = visit_FunctionDef
            visit_ClassDef = visit_FunctionDef
            visit_Lambda = visit_FunctionDef

        for line, function in module.functions.items():
            definition = module.definitions[line]
            visitor = ResourceCalls(function, owned_calls)
            for statement in definition.body:
                visitor.visit(statement)
            for decorator in definition.decorator_list:
                if isinstance(decorator, ast.Call):
                    owned_calls[decorator] = function
        for node, owner in owned_calls.items():
            text = ast.unparse(node.func)
            parts = text.split(".")
            method = parts[-1]
            root = parts[0]
            imported = module.imports.get(root)
            library = imported[0].split(".")[0] if imported else root
            first = (
                node.args[0]
                if node.args
                else next(
                    (k.value for k in node.keywords if k.arg in {"url", "key", "query", "topic"}),
                    None,
                )
            )
            value = (
                first.value
                if isinstance(first, ast.Constant) and isinstance(first.value, str)
                else None
            )
            kind, operation, verb, confidence = None, method, None, "inferred"
            if library in {"requests", "httpx", "aiohttp"} and method in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                kind, verb = "http", method.upper()
                value = public_url(value) if value else None
            elif method == "getenv" and library == "os" or text == "os.environ.get":
                kind, confidence = "environment", "explicit"
            elif any(word in text.lower() for word in ("redis", "cache")) and method in {
                "get",
                "set",
                "delete",
                "hget",
                "hset",
                "incr",
                "decr",
                "publish",
                "subscribe",
            }:
                kind = "message" if method in {"publish", "subscribe"} else "redis"
            elif method in {"execute", "executemany"}:
                kind = "sql"
                match = re.search(
                    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([\w.]+)", value or "", re.IGNORECASE
                )
                value = match.group(1) if match else None  # Never retain full SQL/literals.
            elif method in {
                "publish",
                "subscribe",
                "subscriber",
                "send",
                "send_message",
                "produce",
                "consume",
            }:
                kind = "message"
            if kind:
                snapshot.resources.append(
                    ResourceAccess(
                        id=f"{owner.id}:resource:{node.lineno}:{node.col_offset}",
                        snapshot_id=snapshot.id,
                        owner_id=owner.id,
                        kind=kind,
                        operation=operation,
                        value=value,
                        method=verb,
                        file_path=module.path,
                        line=node.lineno,
                        rule="python-literal-access-v1",
                        confidence=confidence,
                    )
                )
                if value is None:
                    snapshot.gaps.append(
                        AnalysisGap(
                            path=module.path,
                            line=node.lineno,
                            reason=f"Dynamic or unsupported {kind} resource identity",
                        )
                    )
