import json
import subprocess

import pytest

from graphscope.analysis.changes import compare, read_tree, snapshot_files
from graphscope.analysis.impact import impact, propose
from graphscope.analysis.repository import analyze
from graphscope.analysis.workspace import map_workspace, workspace_impact
from graphscope.graph.repository import validate_snapshot


def write(root, path, text):
    path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout


def test_class_methods_static_binding_and_dynamic_gap(tmp_path):
    write(
        tmp_path,
        "a.py",
        "class Service:\n @staticmethod\n def check(): return 1\n def run(self): return self.check()\ndef caller(): return Service.check()\n",
    )
    snapshot = analyze(tmp_path)
    names = {f.id: f.qualified_name for f in snapshot.functions}
    assert set(names.values()) == {"a.Service.check", "a.Service.run", "a.caller"}
    assert {(names[e.caller_id], names[e.callee_id]) for e in snapshot.calls} == {
        ("a.caller", "a.Service.check")
    }
    assert any(c.target_text == "self.check" and c.target_id is None for c in snapshot.callsites)
    validate_snapshot(snapshot)


def test_resources_and_static_test_links(tmp_path):
    write(
        tmp_path,
        "app.py",
        'import requests\nimport os\ndef work():\n requests.get("https://user:password@stock.example/items?token=SECRET")\n cache.get("inventory")\n cursor.execute("SELECT secret FROM products WHERE id=123")\n os.getenv("STOCK_URL")\n',
    )
    write(tmp_path, "tests/test_app.py", "from app import work\ndef test_work(): work()\n")
    snapshot = analyze(tmp_path)
    accesses = {(r.kind, r.value) for r in snapshot.resources}
    assert accesses == {
        ("http", "https://stock.example/items"),
        ("redis", "inventory"),
        ("sql", "products"),
        ("environment", "STOCK_URL"),
    }
    target = next(f for f in snapshot.functions if f.name == "work")
    report = impact(snapshot, [target.id])
    assert [f["name"] for f in report["related_tests"]] == ["test_work"]
    assert "SECRET" not in json.dumps([r.model_dump() for r in snapshot.resources])
    validate_snapshot(snapshot)


def test_proposal_requires_confirmation(tmp_path):
    write(tmp_path, "app.py", "def work(): pass\n")
    snapshot = analyze(tmp_path)
    assert propose(snapshot, "change work")["status"] == "confirmation_required"
    assert propose(snapshot, "change work", ["app.work"], True)["status"] == "confirmed"
    with pytest.raises(ValueError):
        propose(snapshot, "change", ["missing"], True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    write(tmp_path, "app.py", "def stock():\n return 1\ndef order():\n return stock()\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "base")
    return tmp_path


def test_git_worktree_staged_revision_and_deleted_symbols(repo):
    write(repo, "app.py", "def order():\n return 0\n")
    report = compare(repo)
    assert {f["name"] for f in report["before"]["affected_functions"]} == {"stock", "order"}
    assert {
        s["name"] for c in report["changes"] for s in c["symbols"] if s["side"] == "before"
    } >= {"app.stock"}
    assert compare(repo, head="index")["changes"] == []
    git(repo, "add", ".")
    assert compare(repo, head="index")["changes"]
    git(repo, "commit", "-m", "remove stock")
    assert compare(repo, base="HEAD~1", head="HEAD")["changes"]
    assert compare(repo)["changes"] == []


def test_git_subdirectory_untracked_and_module_change(repo):
    write(repo, "pkg/a.py", "def work(): return 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "package")
    files, _ = read_tree(repo / "pkg")
    assert set(files) == {"a.py"}
    write(repo, "pkg/a.py", "SETTING = True\ndef work(): return 1\n")
    write(repo, "new.py", "def added(): pass\n")
    report = compare(repo)
    assert any(c["status"] == "added" for c in report["changes"])
    assert report["change_gaps"]
    with pytest.raises(ValueError):
        read_tree(repo, "--invalid")
    with pytest.raises(ValueError):
        snapshot_files({"../escape.py": b""}, repo)


def test_typescript_alias_call_and_shadowing(tmp_path):
    write(tmp_path, "stock.ts", "export function check(q: number) { return q > 0; }")
    write(
        tmp_path,
        "orders.ts",
        'import {check as validate} from "./stock";\nexport const order = () => validate(1);\nfunction shadow(validate: any) { return validate(); }',
    )
    snapshot = analyze(tmp_path)
    names = {f.id: f.qualified_name for f in snapshot.functions}
    assert {(names[e.caller_id], names[e.callee_id]) for e in snapshot.calls} == {
        ("orders.order", "stock.check")
    }
    assert any(c.reason.startswith("Dynamic") for c in snapshot.callsites)
    validate_snapshot(snapshot)


def test_workspace_python_typescript_http_and_unmatched(tmp_path):
    write(
        tmp_path,
        "api/app.py",
        'from fastapi import FastAPI\napp = FastAPI()\ndef stock(): return 1\n@app.get("/stock/{item}")\ndef get_stock(item: str): return stock()\n',
    )
    write(
        tmp_path,
        "client/index.ts",
        'export async function load() { return fetch("https://stock.example/stock/123"); }\nexport function page() { return load(); }',
    )
    manifest = tmp_path / "workspace.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "services": [
                    {"id": "api", "root": "api", "base_url": "https://stock.example"},
                    {"id": "client", "root": "client", "base_url": "https://client.example"},
                ],
            }
        )
    )
    report = workspace_impact(manifest, "api", "app.stock")
    assert len(report["service_links"]) == 1
    assert {f["qualified_name"] for f in report["report"]["affected_functions"]} >= {
        "app.stock",
        "app.get_stock",
        "index.load",
        "index.page",
    }
    write(
        tmp_path,
        "client/index.ts",
        'export function load() { return fetch("https://other.example/stock/123"); }',
    )
    _, _, links, gaps = map_workspace(manifest)
    assert not links and gaps


def test_broker_topic_requires_explicit_identity(tmp_path):
    write(tmp_path, "producer/a.py", 'def send():\n broker.publish("orders")\n')
    write(tmp_path, "consumer/a.py", '@broker.subscriber("orders")\ndef handle(): pass\n')
    services = [
        {"id": "producer", "root": "producer", "base_url": "https://producer.example"},
        {"id": "consumer", "root": "consumer", "base_url": "https://consumer.example"},
    ]
    manifest = tmp_path / "workspace.json"
    manifest.write_text(json.dumps({"version": 1, "services": services}))
    _, _, links, gaps = map_workspace(manifest)
    assert not links and gaps
    for service in services:
        service["message_broker"] = "orders-broker"
    manifest.write_text(json.dumps({"version": 1, "services": services}))
    report = workspace_impact(manifest, "producer", "a.send")
    assert len(report["service_links"]) == 1
    assert {f["name"] for f in report["report"]["affected_functions"]} == {"send", "handle"}


def test_traversal_limits(tmp_path):
    write(tmp_path, "a.py", "def a(): pass\ndef b(): a()\ndef c(): b()\n")
    snapshot = analyze(tmp_path)
    target = next(f for f in snapshot.functions if f.name == "a")
    assert impact(snapshot, [target.id], max_depth=1)["limits"]["depth_limited"]
    assert impact(snapshot, [target.id], max_paths=1)["limits"]["truncated"]
    with pytest.raises(ValueError):
        impact(snapshot, ["missing"])


def test_src_layout_and_explicit_single_inheritance(tmp_path):
    write(
        tmp_path,
        "src/pkg/core.py",
        "class Base:\n @staticmethod\n def check(): return 1\nclass Child(Base): pass\ndef caller(): return Child.check()\n",
    )
    write(
        tmp_path,
        "src/pkg/client.py",
        "from pkg.core import Child\ndef client(): return Child.check()\n",
    )
    snapshot = analyze(tmp_path)
    names = {f.id: f.qualified_name for f in snapshot.functions}
    assert {(names[e.caller_id], names[e.callee_id]) for e in snapshot.calls} == {
        ("pkg.core.caller", "pkg.core.Base.check"),
        ("pkg.client.client", "pkg.core.Base.check"),
    }


def test_typescript_private_exports_destructuring_and_parse_errors(tmp_path):
    write(tmp_path, "stock.ts", "function privateFn() {} export function check() {}")
    write(
        tmp_path,
        "client.ts",
        'import {privateFn, check} from "./stock";\nfunction a() { privateFn(); }\nfunction b({check}: any) { check(); }',
    )
    write(tmp_path, "bad.ts", "export function broken( {")
    write(tmp_path, "unsupported.go", "package main")
    snapshot = analyze(tmp_path)
    assert not snapshot.calls
    assert any(g.path == "bad.ts" for g in snapshot.gaps)
    assert any(g.path == "unsupported.go" for g in snapshot.gaps)


def test_sql_and_env_changes_are_reported_as_unmapped(repo):
    write(repo, "schema.sql", "ALTER TABLE orders ADD COLUMN status TEXT;")
    report = compare(repo)
    assert any(c["file_path"] == "schema.sql" for c in report["changes"])
    assert any(g["file_path"] == "schema.sql" for g in report["change_gaps"])


def test_schema_change_selects_literal_table_users(repo):
    write(
        repo,
        "app.py",
        'def stock(): return cursor.execute("SELECT * FROM orders")\ndef route(): return stock()\n',
    )
    git(repo, "add", ".")
    git(repo, "commit", "-m", "table access")
    write(repo, "schema.sql", "ALTER TABLE orders ADD COLUMN state TEXT;")
    report = compare(repo)
    assert {f["name"] for f in report["after"]["affected_functions"]} == {"stock", "route"}


def test_model_proposal_validates_catalog_and_never_confirms(tmp_path):
    from unittest.mock import Mock

    from graphscope.analysis.proposals import suggest
    from graphscope.investigation.agent import ModelFailure, ModelTurn, Selection

    write(tmp_path, "app.py", "def stock(): return 1\n")
    snapshot = analyze(tmp_path)
    model = Mock(provider_name="test")
    model.complete.return_value = ModelTurn(selection=Selection(target_id=snapshot.functions[0].id))
    result = suggest(snapshot, "Reject zero quantity", model)
    assert result["status"] == "confirmation_required"
    model.complete.return_value = ModelTurn(selection=Selection(target_id="invented"))
    with pytest.raises(ModelFailure):
        suggest(snapshot, "Reject zero quantity", model)


def test_workspace_git_change_preserves_remote_callers(repo):
    from graphscope.analysis.workspace import workspace_changes

    write(
        repo,
        "app.py",
        'from fastapi import FastAPI\napp=FastAPI()\ndef stock(): return 1\n@app.get("/stock")\ndef route(): return stock()\n',
    )
    write(
        repo,
        "client/api.ts",
        'export function load() { return fetch("https://stock.example/stock"); }',
    )
    git(repo, "add", ".")
    git(repo, "commit", "-m", "service contracts")
    manifest = repo / "workspace.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "services": [
                    {"id": "stock", "root": ".", "base_url": "https://stock.example"},
                    {"id": "client", "root": "client", "base_url": "https://client.example"},
                ],
            }
        )
    )
    write(
        repo,
        "app.py",
        'from fastapi import FastAPI\napp=FastAPI()\ndef stock(): return 2\n@app.get("/stock")\ndef route(): return stock()\n',
    )
    result = workspace_changes(manifest, "stock")
    assert any(
        f["qualified_name"] == "api.load" for f in result["after"]["report"]["affected_functions"]
    )
    assert result["mode"] == "workspace-change"


def test_nested_resource_calls_are_not_attributed_to_outer(tmp_path):
    write(
        tmp_path,
        "a.py",
        'def outer():\n def inner(): return cache.get("hidden")\n return lambda: cache.get("also_hidden")\n',
    )
    assert not analyze(tmp_path).resources
