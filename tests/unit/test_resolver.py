from graphscope.ingestion.pipeline import ingest


def pairs(snapshot):
    names = {f.id: f.qualified_name for f in snapshot.functions}
    return {(names[e.caller_id], names[e.callee_id]) for e in snapshot.calls}


def test_aliases_relative_imports_module_alias_and_duplicate_short_names(tmp_path):
    (tmp_path / "a.py").write_text("def helper(): pass\n")
    (tmp_path / "b.py").write_text("def helper(): pass\n")
    (tmp_path / "use.py").write_text(
        "from .a import helper as chosen\nimport b as other\ndef run():\n    chosen()\n    other.helper()\n"
    )
    result = ingest(tmp_path)
    assert pairs(result) == {("use.run", "a.helper"), ("use.run", "b.helper")}
    assert {e.line for e in result.calls} == {4, 5}


def test_local_shadowing_duplicate_definitions_and_unbound_names(tmp_path):
    (tmp_path / "a.py").write_text(
        "def helper(): pass\ndef helper(): pass\n"
        "def caller(): helper()\n"
        "def shadow(helper): helper()\n"
        "def unknown(): missing()\n"
    )
    result = ingest(tmp_path)
    assert not result.calls
    assert len(result.callsites) == 3


def test_recursion_wildcard_and_global_rebinding(tmp_path):
    (tmp_path / "a.py").write_text("def recurse(): recurse()\n")
    assert pairs(ingest(tmp_path)) == {("a.recurse", "a.recurse")}
    (tmp_path / "a.py").write_text("from something import *\ndef recurse(): recurse()\n")
    assert not ingest(tmp_path).calls
    (tmp_path / "a.py").write_text(
        "def helper(): pass\ndef replace():\n    global helper\n    helper = None\ndef run(): helper()\n"
    )
    assert not ingest(tmp_path).calls


def test_snapshot_identity_and_nested_package_imports(tmp_path):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "a.py").write_text("def helper(): pass\n")
    (package / "b.py").write_text("from .a import helper\ndef run(): helper()\n")
    first, second = ingest(tmp_path), ingest(tmp_path)
    assert pairs(first) == {("pkg.b.run", "pkg.a.helper")}
    assert {f.id for f in first.functions}.isdisjoint(f.id for f in second.functions)
