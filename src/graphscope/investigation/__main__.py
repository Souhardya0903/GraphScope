"""Investigate an existing snapshot; no indexing, source execution, or automated fixes."""

import argparse
import json
import sys
from pathlib import Path

from redis.exceptions import RedisError

from graphscope.graph.client import select_graph
from graphscope.investigation.agent import ModelFailure, run_investigation
from graphscope.investigation.gemini import GeminiModel
from graphscope.investigation.ollama import OllamaModel
from graphscope.investigation.providers import DeterministicPlanner, OpenAIModel
from graphscope.investigation.service import ClarificationRequired
from graphscope.investigation.tools import BudgetExceeded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_id")
    parser.add_argument("question")
    parser.add_argument(
        "--target", help="Explicit symbol ID or qualified name; enables deterministic fallback"
    )
    parser.add_argument(
        "--provider", choices=["none", "test", "openai", "gemini", "ollama"], default="none"
    )
    parser.add_argument(
        "--share-source",
        action="store_true",
        help="Allow hash-verified excerpts to be sent to the model",
    )
    parser.add_argument("--graph")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.provider in {"none", "test"} and not args.target:
        parser.error("--target is required without a live model provider")
    try:
        graph = select_graph(args.graph)  # Loads .env without printing credentials.
        model = (
            DeterministicPlanner(args.target)
            if args.provider == "test"
            else OpenAIModel()
            if args.provider == "openai"
            else GeminiModel()
            if args.provider == "gemini"
            else OllamaModel()
            if args.provider == "ollama"
            else None
        )
        report = run_investigation(
            graph, args.snapshot_id, args.question, args.target, model, args.share_source
        )
        output = report.model_dump_json(indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output)
    except ClarificationRequired as error:
        print(
            json.dumps({"error": "clarification_required", "candidates": error.candidates}),
            file=sys.stderr,
        )
        return 2
    except RedisError:
        print("FalkorDB unavailable; no investigation report was fabricated.", file=sys.stderr)
        return 1
    except (ModelFailure, BudgetExceeded, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
