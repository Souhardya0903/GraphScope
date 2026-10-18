"""Local operator API for the extended analysis engine; blocking work uses threads."""

import subprocess
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field

from graphscope.analysis.changes import compare
from graphscope.analysis.impact import impact, propose
from graphscope.analysis.proposals import suggest
from graphscope.analysis.repository import analyze
from graphscope.analysis.workspace import map_workspace, workspace_changes, workspace_impact
from graphscope.api.safety import allowed_path
from graphscope.investigation.agent import ModelFailure
from graphscope.investigation.gemini import GeminiModel
from graphscope.investigation.ollama import OllamaModel
from graphscope.investigation.providers import OpenAIModel
from graphscope.models import Contract

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalysisRequest(Contract):
    root: str = Field(min_length=1, max_length=2048)
    base: str = Field(default="HEAD", min_length=1, max_length=200)
    head: str = Field(default="worktree", min_length=1, max_length=200)
    targets: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=4000)
    confirm: bool = False
    provider: Literal["none", "openai", "gemini", "ollama"] = "none"
    share_catalog: bool = False
    resource: str | None = Field(default=None, max_length=2048)
    service: str | None = Field(default=None, max_length=100)
    changed_service: str | None = Field(default=None, max_length=100)


def execute(operation, request):
    try:
        if request.provider != "none":
            if operation != "propose" or request.confirm or request.targets:
                raise ValueError(
                    "Model suggestions require an unconfirmed proposal without targets"
                )
            if not request.share_catalog:
                raise ValueError(
                    "Allow sharing the description and symbol catalog before using a model"
                )
        if request.resource and request.targets:
            raise ValueError("Choose targets or a resource, not both")
        if request.changed_service and (request.service or request.targets):
            raise ValueError("Choose changed service or explicit service target, not both")
        root = allowed_path(request.root)
        if operation == "workspace":
            from graphscope.analysis.workspace import Workspace

            manifest = Workspace.model_validate_json(root.read_text(encoding="utf-8"))
            for service in manifest.services:
                allowed_path(root.parent / service.root)
        if operation == "workspace":
            if request.changed_service:
                return workspace_changes(root, request.changed_service, request.base, request.head)
            if request.service and len(request.targets) == 1:
                return workspace_impact(root, request.service, request.targets[0])
            if request.service or request.targets:
                raise ValueError("Select a service and exactly one target")
            _, snapshots, links, gaps = map_workspace(root)
            return {
                "mode": "workspace-map",
                "snapshots": {k: v.model_dump() for k, v in snapshots.items()},
                "service_links": links,
                "service_gaps": gaps,
            }
        if operation == "changes":
            return compare(root, request.base, request.head)
        snapshot = analyze(root)
        if operation == "map":
            return {"mode": "repository-map", **snapshot.model_dump()}
        if operation == "propose":
            if request.provider != "none":
                model = {"openai": OpenAIModel, "gemini": GeminiModel, "ollama": OllamaModel}[
                    request.provider
                ]()
                return suggest(snapshot, request.description, model)
            return propose(snapshot, request.description, request.targets or None, request.confirm)
        targets = []
        if request.resource:
            kind, sep, value = request.resource.partition(":")
            if not sep or not value:
                raise ValueError("Resource requires kind:value")
            targets = sorted(
                {r.owner_id for r in snapshot.resources if r.kind == kind and r.value == value}
            )
        else:
            for target in request.targets:
                matches = [f.id for f in snapshot.functions if target in {f.id, f.qualified_name}]
                if len(matches) != 1:
                    raise ValueError("Select exact unambiguous qualified targets")
                targets.extend(matches)
        if not targets:
            raise ValueError("Select targets or a matching literal resource")
        return {"mode": "target-impact", "report": impact(snapshot, targets)}
    except ModelFailure as error:
        raise HTTPException(
            502,
            detail=f"Model suggestion failed: {error}. Use offline suggestions or explicit targets.",
        ) from error
    except (ValueError, FileNotFoundError, NotADirectoryError) as error:
        raise HTTPException(422, detail=str(error)) from error
    except subprocess.TimeoutExpired as error:
        raise HTTPException(
            504, detail="Analysis operation timed out; narrow the repository"
        ) from error
    except OSError as error:
        raise HTTPException(
            422, detail="Cannot read repository; check path and permissions"
        ) from error


@router.post("/{operation}")
def run_analysis(
    operation: Literal["map", "changes", "impact", "propose", "workspace"], request: AnalysisRequest
):
    return execute(operation, request)
