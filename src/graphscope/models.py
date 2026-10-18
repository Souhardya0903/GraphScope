"""Snapshot, source evidence, analysis gap, and investigation report contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisGap(Contract):
    path: str
    line: int | None = None
    reason: str


class SourceReference(Contract):
    path: str
    line: int
    rule: str


class FileNode(Contract):
    id: str
    snapshot_id: str
    relative_path: str
    module: str
    content_hash: str
    parse_status: Literal["parsed", "error"]


class FunctionNode(Contract):
    id: str
    snapshot_id: str
    qualified_name: str
    name: str
    module: str
    file_path: str
    start_line: int
    end_line: int
    signature: str
    is_async: bool


class CallSiteNode(Contract):
    id: str
    snapshot_id: str
    owner_id: str
    file_path: str
    line: int
    end_line: int
    target_text: str
    resolution_status: Literal["resolved", "unresolved"] = "unresolved"
    target_id: str | None = None
    reason: str = "Unsupported call expression"


class EvidenceEdge(Contract):
    caller_id: str
    callee_id: str
    callsite_id: str
    file_path: str
    line: int
    rule: str = "explicit-python-binding-v1"
    confidence: Literal["explicit", "inferred"] = "explicit"


class EndpointNode(Contract):
    id: str
    snapshot_id: str
    method: str
    path: str
    handler_id: str
    file_path: str
    line: int
    mount_evidence: list[SourceReference] = Field(default_factory=list)


class Snapshot(Contract):
    id: str
    root: str
    indexed_at: str
    extractor_version: str = "0.3.0"
    metadata: dict = Field(default_factory=dict)
    resources: list["ResourceAccess"] = Field(default_factory=list)
    status: Literal["extracted"] = "extracted"
    files: list[FileNode] = Field(default_factory=list)
    functions: list[FunctionNode] = Field(default_factory=list)
    callsites: list[CallSiteNode] = Field(default_factory=list)
    calls: list[EvidenceEdge] = Field(default_factory=list)
    endpoints: list[EndpointNode] = Field(default_factory=list)
    gaps: list[AnalysisGap] = Field(default_factory=list)


class ResourceAccess(Contract):
    id: str
    snapshot_id: str
    owner_id: str
    kind: Literal["http", "redis", "sql", "environment", "message"]
    operation: str
    value: str | None = None
    method: str | None = None
    file_path: str
    line: int
    rule: str
    confidence: Literal["explicit", "inferred"] = "inferred"


class ImpactReport(Contract):
    """Deterministic graph findings and separately labelled recommendations."""

    investigation_id: str
    snapshot_id: str
    target_id: str
    question: str
    generated_at: str
    graph_evidence: dict
    recommended_checks: list[dict] = Field(default_factory=list)
    analysis_gaps: dict
    completeness: Literal["within_supported_scope", "partial"]
    agent: dict
    activity: list[dict] = Field(default_factory=list)
