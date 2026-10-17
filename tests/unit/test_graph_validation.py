import pytest

from graphscope.graph.queries import GraphQueries
from graphscope.graph.repository import validate_snapshot
from graphscope.ingestion.pipeline import ingest


def test_reject_cross_snapshot_and_missing_evidence(tmp_path):
    (tmp_path / "a.py").write_text("def a(): pass\ndef b(): a()\n")
    snapshot = ingest(tmp_path)
    validate_snapshot(snapshot)
    snapshot.functions[0].snapshot_id = "other"
    with pytest.raises(ValueError, match="Cross-snapshot"):
        validate_snapshot(snapshot)
    snapshot.functions[0].snapshot_id = snapshot.id
    snapshot.calls.clear()
    with pytest.raises(ValueError, match="disagree"):
        validate_snapshot(snapshot)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "8", 1001])
def test_reject_invalid_query_limits(value):
    with pytest.raises(ValueError):
        GraphQueries.limit(value)
