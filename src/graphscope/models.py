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
    extractor_version: str = "0.2.1"
    status: Literal["extracted"] = "extracted"
    files: list[FileNode] = Field(default_factory=list)
    functions: list[FunctionNode] = Field(default_factory=list)
    callsites: list[CallSiteNode] = Field(default_factory=list)
    calls: list[EvidenceEdge] = Field(default_factory=list)
    endpoints: list[EndpointNode] = Field(default_factory=list)
    gaps: list[AnalysisGap] = Field(default_factory=list)


class ImpactReport(Contract):
    """Future investigation output; extraction does not populate impact findings."""

    snapshot_id: str
    target_id: str
    affected_function_ids: list[str] = Field(default_factory=list)
    affected_endpoint_ids: list[str] = Field(default_factory=list)
    evidence_paths: list[list[EvidenceEdge]] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    gaps: list[AnalysisGap] = Field(default_factory=list)
