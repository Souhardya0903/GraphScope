import os
from uuid import uuid4

import pytest

from graphscope.analysis.repository import analyze
from graphscope.graph.client import select_graph
from graphscope.graph.queries import GraphQueries
from graphscope.graph.repository import GraphRepository


@pytest.mark.skipif(os.environ.get("GRAPHSCOPE_INTEGRATION") != "1", reason="Cloud tests opt-in")
def test_extended_resources_metadata_and_tests_are_persisted(tmp_path):
    (tmp_path / "app.py").write_text('def stock(): return cache.get("inventory")\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_stock.py").write_text(
        "from app import stock\ndef test_stock(): stock()\n"
    )
    snapshot = analyze(tmp_path)
    graph = select_graph("graphscope_extended_test_" + uuid4().hex)
    try:
        GraphRepository(graph).store(snapshot)
        queries = GraphQueries(graph)
        accesses = queries.trace_resource_consumers(snapshot.id, "redis:inventory")
        assert accesses["supported"] and len(accesses["accesses"]) == 1
        assert queries.snapshot_metadata(snapshot.id)["analysis_version"] == "1"
        test_id = next(f.id for f in snapshot.functions if f.name == "test_stock")
        assert queries.find_related_tests(snapshot.id, [test_id])["tests"][0]["id"] == test_id
        assert graph.ro_query("MATCH ()-[r:ACCESSES]->() RETURN count(r)").result_set == [[1]]
    finally:
        graph.delete()
