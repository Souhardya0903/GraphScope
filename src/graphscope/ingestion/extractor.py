"""Extract definitions, imports, routes, and call sites with Python AST."""

import ast
from collections import Counter
from dataclasses import dataclass, field

from graphscope.models import AnalysisGap, CallSiteNode, FunctionNode, Snapshot


class Bindings(ast.NodeVisitor):
    """Count bindings in one scope; nested bodies are separate execution scopes."""

    def __init__(self):
        self.names = Counter()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names[node.id] += 1

    def visit_FunctionDef(self, node):
        self.names[node.name] += 1

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Lambda(self, node):
        pass

    def visit_Import(self, node):
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node):
        self.names.update(alias.asname or alias.name for alias in node.names)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest:
            self.names[node.rest] += 1
        self.generic_visit(node)


@dataclass
class ParsedModule:
    name: str
    path: str
    tree: ast.Module
    is_package: bool
    bindings: Counter
    functions: dict[int, FunctionNode] = field(default_factory=dict)
    imports: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    blocked: set[str] = field(default_factory=set)
    wildcard: bool = False
    method_classes: dict[str, str] = field(default_factory=dict)
    class_bases: dict[str, list[str]] = field(default_factory=dict)
    definitions: dict[int, ast.AST] = field(default_factory=dict)
    function_blocks: dict[str, set[str]] = field(default_factory=dict)


def collect(tree, name, path, snapshot: Snapshot, is_package=False):
    bindings = Bindings()
    bindings.visit(tree)
    module = ParsedModule(name, path, tree, is_package, bindings.names)
    definitions = [(node, None) for node in tree.body]
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef):
            module.class_bases[cls.name] = [ast.unparse(b) for b in cls.bases]
            definitions.extend(
                (node, cls.name)
                for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    for node, class_name in definitions:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            member = f"{class_name}.{node.name}" if class_name else node.name
            function = FunctionNode(
                id=f"{snapshot.id}:{path}:{member}:{node.lineno}",
                snapshot_id=snapshot.id,
                qualified_name=f"{name}.{member}".lstrip("."),
                name=node.name,
                module=name,
                file_path=path,
                start_line=node.lineno,
                end_line=node.end_lineno,
                signature=f"{node.name}({ast.unparse(node.args)})"
                + (f" -> {ast.unparse(node.returns)}" if node.returns else ""),
                is_async=isinstance(node, ast.AsyncFunctionDef),
            )
            snapshot.functions.append(function)
            module.functions[node.lineno] = function
            module.definitions[node.lineno] = node
            if class_name:
                module.method_classes[function.id] = class_name
            local = Bindings()
            for statement in node.body:
                local.visit(statement)
            blocked = set(local.names)
            blocked.update(
                a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            )
            blocked.update(a.arg for a in (node.args.vararg, node.args.kwarg) if a)
            # Dynamic namespace mutations are unsupported, including within nested scopes.
            for child in ast.walk(node):
                if isinstance(child, ast.Global):
                    module.blocked.update(child.names)
                    blocked.update(child.names)
                if isinstance(child, ast.Nonlocal):
                    blocked.update(child.names)
            module.function_blocks[function.id] = blocked
            visitor = Calls(snapshot, module, function)
            for statement in node.body:
                visitor.visit(statement)
        elif isinstance(node, ast.ClassDef):
            snapshot.gaps.append(
                AnalysisGap(
                    path=path,
                    line=node.lineno,
                    reason="Class attributes, constructors and runtime inheritance dispatch are not fully resolved",
                )
            )
    return module


class Calls(ast.NodeVisitor):
    def __init__(self, snapshot, module, function):
        self.snapshot, self.module, self.function = snapshot, module, function

    def gap(self, node, reason):
        self.snapshot.gaps.append(
            AnalysisGap(path=self.module.path, line=node.lineno, reason=reason)
        )

    def visit_FunctionDef(self, node):
        self.gap(node, "Nested function body skipped")

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.gap(node, "Nested class body skipped")

    def visit_Lambda(self, node):
        self.gap(node, "Lambda body skipped")

    def visit_Call(self, node):
        self.snapshot.callsites.append(
            CallSiteNode(
                id=f"{self.function.id}:call:{node.lineno}:{node.col_offset}:{node.end_lineno}:{node.end_col_offset}",
                snapshot_id=self.snapshot.id,
                owner_id=self.function.id,
                file_path=self.module.path,
                line=node.lineno,
                end_line=node.end_lineno,
                target_text=ast.unparse(node.func),
            )
        )
        self.generic_visit(node)
