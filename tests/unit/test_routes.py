from graphscope.ingestion.pipeline import ingest


def test_router_prefix_mounts_and_source_evidence(tmp_path):
    (tmp_path / "routes.py").write_text(
        'from fastapi import APIRouter as Router\nrouter = Router(prefix="/v1")\n'
        '@router.get("/items")\nasync def items(): return []\n'
    )
    (tmp_path / "app.py").write_text(
        "from fastapi import FastAPI\nfrom .routes import router as routes\napp = FastAPI()\n"
        'app.include_router(routes, prefix="/api")\napp.include_router(routes, prefix="/admin")\n'
    )
    result = ingest(tmp_path)
    assert {(e.method, e.path) for e in result.endpoints} == {
        ("GET", "/api/v1/items"),
        ("GET", "/admin/v1/items"),
    }
    assert all(e.file_path == "routes.py" and e.line == 3 for e in result.endpoints)
    assert {e.mount_evidence[0].line for e in result.endpoints} == {4, 5}


def test_fake_and_unmounted_router_not_exposed(tmp_path):
    (tmp_path / "a.py").write_text(
        "from fastapi import APIRouter\nrouter=APIRouter()\n"
        '@router.get("/hidden")\ndef hidden(): pass\n'
        '@fake.get("/fake")\ndef fake_handler(): pass\n'
    )
    result = ingest(tmp_path)
    assert result.endpoints == []
    assert any("not mounted" in g.reason for g in result.gaps)
    assert any("Unsupported route" in g.reason for g in result.gaps)


def test_route_cycles_and_dynamic_prefix_are_gaps(tmp_path):
    (tmp_path / "a.py").write_text(
        "from fastapi import FastAPI, APIRouter\napp=FastAPI()\nrouter=APIRouter()\n"
        "router.include_router(router)\napp.include_router(router)\n"
        "app.include_router(router, prefix=unknown)\n"
    )
    result = ingest(tmp_path)
    assert any("cycle" in g.reason for g in result.gaps)
    assert any("Unsupported router mount" in g.reason for g in result.gaps)
