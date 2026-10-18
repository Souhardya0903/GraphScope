from pathlib import Path

from graphscope.ingestion.pipeline import ingest
from graphscope.models import Snapshot

DEMO = Path(__file__).resolve().parents[2] / "examples" / "commerce"


def edges(snapshot):
    names = {f.id: f.qualified_name for f in snapshot.functions}
    return {(names[e.caller_id], names[e.callee_id]) for e in snapshot.calls}


def test_commerce_ground_truth():
    result = ingest(DEMO)
    assert edges(result) == {
        ("orders.create_order", "orders.place_order"),
        ("orders.place_order", "inventory.validate_stock"),
        ("reservations.reserve_stock", "inventory.validate_stock"),
        ("inventory.validate_stock", "inventory.read_inventory"),
        ("inventory.read_inventory", "redis_adapter.read_stock"),
    }
    assert {(e.method, e.path) for e in result.endpoints} == {
        ("POST", "/orders"),
        ("POST", "/reservations"),
        ("GET", "/products"),
    }
    assert len(result.functions) == 8
    dynamic = [c for c in result.callsites if c.file_path == "dispatch.py"]
    assert len(dynamic) == 2  # getattr(...) and invocation of its returned object
    assert len({c.id for c in result.callsites}) == len(result.callsites)
    assert all(c.target_id is None and c.resolution_status == "unresolved" for c in dynamic)
    assert any(c.target_text.startswith("getattr(") for c in dynamic)
    for call in result.calls:
        source = (DEMO / call.file_path).read_text().splitlines()[call.line - 1]
        site = next(s for s in result.callsites if s.id == call.callsite_id)
        assert site.target_text in source
    assert Snapshot.model_validate_json(result.model_dump_json()) == result


def test_does_not_execute_source_and_reports_parse_failure(tmp_path):
    (tmp_path / "a.py").write_text(
        'raise RuntimeError("must never run")\nasync def work(x: int): return x\n'
    )
    (tmp_path / "bad.py").write_text("def broken(:")
    result = ingest(tmp_path)
    assert result.functions[0].is_async
    assert "x: int" in result.functions[0].signature
    assert {f.relative_path: f.parse_status for f in result.files} == {
        "a.py": "parsed",
        "bad.py": "error",
    }
    assert any(g.path == "bad.py" and g.line == 1 for g in result.gaps)


def test_discovery_prunes_caches_hidden_and_tests(tmp_path):
    for directory in (".hidden", ".venv", "node_modules", "__pycache__", "tests"):
        folder = tmp_path / directory
        folder.mkdir()
        (folder / "a.py").write_text("def hidden(): pass")
    (tmp_path / "main.py").write_text("def visible(): pass")
    assert [f.relative_path for f in ingest(tmp_path).files] == ["main.py"]
    assert {f.relative_path for f in ingest(tmp_path, include_tests=True).files} == {
        "main.py",
        "tests/a.py",
    }


def test_nested_bodies_not_attributed_to_outer(tmp_path):
    (tmp_path / "a.py").write_text(
        "def target(): pass\ndef outer():\n    def inner(): target()\n    f = lambda: target()\n"
    )
    result = ingest(tmp_path)
    assert result.calls == []
    assert len(result.gaps) == 2


def test_explicit_reexports_and_from_package_module_calls(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("from .bridge import exposed\n")
    (package / "bridge.py").write_text("from .util import work as exposed\n")
    (package / "util.py").write_text("def work(): return 1\n")
    (tmp_path / "app.py").write_text("from pkg import exposed, util\nimport pkg\ndef run():\n    exposed()\n    pkg.exposed()\n    util.work()\n")
    result = ingest(tmp_path)
    assert len(result.calls) == 3
    assert edges(result) == {("app.run", "pkg.util.work")}


def test_reexports_do_not_bypass_rebinding_decorators_or_cycles(tmp_path):
    (tmp_path / "a.py").write_text("from b import work\n")
    (tmp_path / "b.py").write_text("from a import work\n")
    (tmp_path / "decorated.py").write_text("@unknown\ndef work(): pass\n")
    (tmp_path / "exports.py").write_text("from decorated import work\n")
    (tmp_path / "rebound.py").write_text("from original import work\nwork = unknown\n")
    (tmp_path / "original.py").write_text("def work(): pass\n")
    (tmp_path / "app.py").write_text("import a, exports, rebound\ndef run():\n    a.work()\n    exports.work()\n    rebound.work()\n")
    assert ingest(tmp_path).calls == []


def test_builtins_are_explained_without_inventing_edges(tmp_path):
    (tmp_path / "app.py").write_text("def run(): return len([])\ndef shadow(len): return len([])\n")
    result = ingest(tmp_path)
    assert result.calls == []
    assert "Python builtin" in result.callsites[0].reason
    assert "shadows" in result.callsites[1].reason
