"""Explicit versioned service manifests; no hostname or short-name guessing."""

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from graphscope.analysis.repository import analyze
from graphscope.analysis.resources import public_url
from graphscope.models import Contract, EvidenceEdge, Snapshot


class Service(Contract):
    id: str
    root: str
    base_url: str
    message_broker: str | None = None
    revision: str = "worktree"


class Workspace(Contract):
    version: int
    services: list[Service]


def route_matches(pattern, path):
    expected, actual = pattern.strip("/").split("/"), path.strip("/").split("/")
    return len(expected) == len(actual) and all(
        a == b or (a.startswith("{") and a.endswith("}") and ":" not in a)
        for a, b in zip(expected, actual)
    )


def map_workspace(manifest, overrides=None):
    manifest = Path(manifest).resolve(strict=True)
    config = Workspace.model_validate_json(manifest.read_text(encoding="utf-8"))
    if config.version != 1 or not 1 <= len(config.services) <= 50:
        raise ValueError("Workspace version must be 1 with 1..50 services")
    if len({s.id for s in config.services}) != len(config.services):
        raise ValueError("Service IDs must be unique")
    snapshots, links, gaps = {}, [], []
    for service in config.services:
        if not service.id or len(service.id) > 100:
            raise ValueError("Service ID must contain 1..100 characters")
        url = public_url(service.base_url)
        if (
            url is None
            or urlsplit(url).path != "/"
            or service.base_url.rstrip("/") != url.rstrip("/")
        ):
            raise ValueError(
                "Service base_url must be an HTTP(S) origin without credentials/query/path"
            )
        root = (manifest.parent / service.root).resolve(strict=True)
        if overrides and service.id in overrides:
            snapshots[service.id] = overrides[service.id]
        elif service.revision == "worktree":
            snapshots[service.id] = analyze(root)
        else:
            from graphscope.analysis.changes import read_tree, snapshot_files

            files, metadata = read_tree(root, service.revision)
            snapshots[service.id] = snapshot_files(files, root)
            snapshots[service.id].metadata.update(metadata)
        snapshots[service.id].metadata["service_id"] = service.id
    for source in config.services:
        for access in snapshots[source.id].resources:
            if access.kind != "http" or not access.value or not access.method:
                continue
            destination = urlsplit(access.value)
            matches = []
            for service in config.services:
                base = urlsplit(service.base_url)
                if (destination.scheme, destination.netloc.lower()) != (
                    base.scheme,
                    base.netloc.lower(),
                ):
                    continue
                for endpoint in snapshots[service.id].endpoints:
                    if endpoint.method == access.method and route_matches(
                        endpoint.path, destination.path
                    ):
                        matches.append((service.id, endpoint))
            if len(matches) == 1:
                service_id, endpoint = matches[0]
                links.append(
                    {
                        "kind": "http-contract",
                        "caller_id": access.owner_id,
                        "callee_id": endpoint.handler_id,
                        "source_service": source.id,
                        "target_service": service_id,
                        "request_evidence": access.model_dump(),
                        "endpoint_evidence": endpoint.model_dump(),
                        "confidence": "inferred",
                        "rule": "explicit-origin-and-method-route-v1",
                    }
                )
            else:
                gaps.append(
                    {
                        "service": source.id,
                        "access_id": access.id,
                        "reason": "External/unmatched or ambiguous HTTP destination",
                        "candidates": len(matches),
                    }
                )
    # A topic is meaningful only within an explicitly declared broker identity.
    for source in config.services:
        if not source.message_broker:
            continue
        for producer in snapshots[source.id].resources:
            if (
                producer.kind != "message"
                or not producer.value
                or producer.operation not in {"publish", "send", "send_message", "produce"}
            ):
                continue
            for destination in config.services:
                if destination.message_broker != source.message_broker:
                    continue
                for consumer in snapshots[destination.id].resources:
                    if (
                        consumer.kind == "message"
                        and consumer.operation in {"subscribe", "subscriber", "consume"}
                        and consumer.value == producer.value
                    ):
                        links.append(
                            {
                                "kind": "message-contract",
                                "caller_id": consumer.owner_id,
                                "callee_id": producer.owner_id,
                                "source_service": destination.id,
                                "target_service": source.id,
                                "request_evidence": consumer.model_dump(),
                                "endpoint_evidence": producer.model_dump(),
                                "confidence": "inferred",
                                "rule": "explicit-broker-topic-contract-v1",
                            }
                        )
    for service_id, snapshot in snapshots.items():
        for access in snapshot.resources:
            if (
                access.kind == "message"
                and not next(s for s in config.services if s.id == service_id).message_broker
            ):
                gaps.append(
                    {
                        "service": service_id,
                        "access_id": access.id,
                        "reason": "Message broker identity and delivery semantics require explicit contract; no topic-name-only service edge inferred",
                    }
                )
    return config, snapshots, links, gaps


def workspace_impact(manifest, service_id, target):
    config, snapshots, links, gaps = map_workspace(manifest)
    if service_id not in snapshots:
        raise ValueError("Unknown service ID")
    targets = [f.id for f in snapshots[service_id].functions if target in {f.id, f.qualified_name}]
    if len(targets) != 1:
        raise ValueError("Select one exact qualified symbol in the target service")
    return combined_impact(manifest, config, snapshots, links, gaps, targets)


def combined_impact(manifest, config, snapshots, links, gaps, targets):
    from graphscope.analysis.impact import impact

    combined = Snapshot(
        id=uuid4().hex, root=str(Path(manifest).resolve()), indexed_at=datetime.now(UTC).isoformat()
    )
    for snapshot in snapshots.values():
        for attr in ("files", "functions", "callsites", "calls", "endpoints", "resources", "gaps"):
            getattr(combined, attr).extend(getattr(snapshot, attr))
    for link in links:
        access = link["request_evidence"]
        combined.calls.append(
            EvidenceEdge(
                caller_id=link["caller_id"],
                callee_id=link["callee_id"],
                callsite_id=access["id"],
                file_path=access["file_path"],
                line=access["line"],
                rule=link["rule"],
                confidence="inferred",
            )
        )
    combined.metadata = {
        "workspace_version": config.version,
        "services": {k: v.metadata for k, v in snapshots.items()},
        "cross_service_edges_are_inferred": True,
    }
    return {
        "mode": "workspace-impact",
        "report": impact(combined, targets),
        "service_links": links,
        "service_gaps": gaps,
    }


def workspace_changes(manifest, service_id, base="HEAD", head="worktree"):
    from graphscope.analysis.changes import changed_symbols, read_tree, snapshot_files

    manifest = Path(manifest).resolve(strict=True)
    config = Workspace.model_validate_json(manifest.read_text(encoding="utf-8"))
    selected = [s for s in config.services if s.id == service_id]
    if len(selected) != 1:
        raise ValueError("Select one configured changed service")
    root = (manifest.parent / selected[0].root).resolve(strict=True)
    old, old_meta = read_tree(root, base)
    new, new_meta = read_tree(root, head)
    before, after = snapshot_files(old, root), snapshot_files(new, root)
    before.metadata.update(old_meta)
    after.metadata.update(new_meta)
    changes, change_gaps = changed_symbols(before, after, old, new)
    # Pin the other services to one captured set for both comparisons.
    _, others, _, _ = map_workspace(manifest, {service_id: after})
    result = {
        "mode": "workspace-change",
        "changed_service": service_id,
        "base": old_meta,
        "head": new_meta,
        "changes": changes,
        "change_gaps": change_gaps,
        "caveat": "Other services are held at their manifest snapshots. Runtime compatibility across revisions is not proven.",
    }
    for side, snapshot in (("before", before), ("after", after)):
        overrides = {**others, service_id: snapshot}
        config, snapshots, links, gaps = map_workspace(manifest, overrides)
        targets = sorted({s["id"] for c in changes for s in c["symbols"] if s["side"] == side})
        result[side] = combined_impact(manifest, config, snapshots, links, gaps, targets)
    return result
