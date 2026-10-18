"""Offline maps, Git changes, confirmed proposals, and workspace blast radius."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from redis.exceptions import RedisError

from graphscope.analysis.changes import compare
from graphscope.analysis.impact import impact, propose
from graphscope.analysis.repository import analyze
from graphscope.analysis.workspace import map_workspace, workspace_changes, workspace_impact
from graphscope.investigation.agent import ModelFailure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    mapping = commands.add_parser("map")
    mapping.add_argument("root", type=Path)
    mapping.add_argument(
        "--store",
        action="store_true",
        help="Also persist the extended snapshot to configured FalkorDB",
    )
    changes = commands.add_parser("changes")
    changes.add_argument("root", type=Path)
    changes.add_argument("--base", default="HEAD")
    changes.add_argument(
        "--head",
        default="worktree",
        help="Git revision, index (staged), or worktree (tracked and untracked)",
    )
    changes.add_argument("--max-depth", type=int, default=12)
    changes.add_argument("--max-paths", type=int, default=500)
    proposal = commands.add_parser("propose")
    proposal.add_argument("root", type=Path)
    proposal.add_argument("description")
    proposal.add_argument("--target", action="append")
    proposal.add_argument("--confirm", action="store_true")
    proposal.add_argument(
        "--provider",
        choices=["none", "ollama", "gemini", "openai"],
        default="none",
        help="Optional model suggestion; sends description and bounded symbol catalog, not source snippets",
    )
    selected = commands.add_parser("impact")
    selected.add_argument("root", type=Path)
    group = selected.add_mutually_exclusive_group(required=True)
    group.add_argument("--target", action="append")
    group.add_argument("--resource", help="Literal kind:value; include all users conservatively")
    workspace = commands.add_parser("workspace")
    workspace.add_argument("manifest", type=Path)
    workspace.add_argument("--service")
    workspace.add_argument("--target")
    workspace.add_argument("--changed-service")
    workspace.add_argument("--base", default="HEAD")
    workspace.add_argument("--head", default="worktree")
    for cmd in (mapping, changes, proposal, selected, workspace):
        cmd.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "changes":
            result = compare(args.root, args.base, args.head, args.max_depth, args.max_paths)
        elif args.command == "workspace":
            if bool(args.service) != bool(args.target):
                raise ValueError("Provide both --service and --target for workspace impact")
            if args.changed_service:
                if args.target or args.service:
                    raise ValueError("Choose either explicit target or changed-service analysis")
                result = workspace_changes(
                    args.manifest, args.changed_service, args.base, args.head
                )
            elif args.target:
                result = workspace_impact(args.manifest, args.service, args.target)
            else:
                _, snapshots, links, gaps = map_workspace(args.manifest)
                result = {
                    "snapshots": {k: v.model_dump() for k, v in snapshots.items()},
                    "service_links": links,
                    "service_gaps": gaps,
                }
        else:
            snapshot = analyze(args.root)
            if args.command == "map":
                if args.store:
                    from graphscope.graph.client import select_graph
                    from graphscope.graph.repository import GraphRepository

                    GraphRepository(select_graph()).store(snapshot)
                result = snapshot.model_dump()
            elif args.command == "propose":
                if args.provider != "none":
                    if args.confirm or args.target:
                        raise ValueError(
                            "Model suggestions and confirmed explicit targets are separate steps"
                        )
                    from dotenv import load_dotenv

                    from graphscope.analysis.proposals import suggest
                    from graphscope.investigation.gemini import GeminiModel
                    from graphscope.investigation.ollama import OllamaModel
                    from graphscope.investigation.providers import OpenAIModel

                    load_dotenv(override=False)
                    result = suggest(
                        snapshot,
                        args.description,
                        {"ollama": OllamaModel, "gemini": GeminiModel, "openai": OpenAIModel}[
                            args.provider
                        ](),
                    )
                else:
                    result = propose(snapshot, args.description, args.target, args.confirm)
            else:
                targets = []
                if args.resource:
                    kind, separator, value = args.resource.partition(":")
                    if not separator or not value:
                        raise ValueError("Resource requires kind:value")
                    targets = sorted(
                        {
                            r.owner_id
                            for r in snapshot.resources
                            if r.kind == kind and r.value == value
                        }
                    )
                    if not targets:
                        raise ValueError("No matching literal resource users")
                else:
                    for target in args.target:
                        matches = [
                            f.id for f in snapshot.functions if target in {f.id, f.qualified_name}
                        ]
                        if len(matches) != 1:
                            raise ValueError("Select exact, unambiguous qualified targets")
                        targets.extend(matches)
                result = impact(snapshot, targets)
        output = json.dumps(result, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output)
    except RedisError:
        print("FalkorDB operation failed; check connection settings", file=sys.stderr)
        return 1
    except (ValueError, OSError, subprocess.TimeoutExpired, ModelFailure) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
