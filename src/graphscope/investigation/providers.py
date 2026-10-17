"""OpenAI Responses adapter and an explicitly non-LLM local test planner."""

import json
import os
import time

import httpx
from pydantic import ValidationError

from graphscope.investigation.agent import ModelFailure, ModelTurn, Selection, ToolCall


class DeterministicPlanner:
    """Exercise the real tool loop without pretending to generate AI analysis."""

    provider_name = "test"

    def __init__(self, target):
        self.target = target

    def complete(self, messages, tools, timeout):
        results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        if not results:
            return ModelTurn(calls=[ToolCall("resolve_symbol", {"query": self.target}, "resolve")])
        candidates = results[0].get("data", {}).get("candidates", [])
        if len(candidates) != 1:
            return ModelTurn(clarification="Choose a unique qualified target")
        target_id = candidates[0]["id"]
        if len(results) == 1:
            return ModelTurn(calls=[ToolCall("trace_callers", {"function_id": target_id}, "trace")])
        if len(results) == 2:
            traversal = results[1].get("data", {})
            ids = sorted(
                {target_id, *(i for p in traversal.get("paths", []) for i in p["function_ids"])}
            )
            return ModelTurn(
                calls=[
                    ToolCall("find_endpoints", {"function_ids": ids}, "endpoints"),
                    ToolCall("get_analysis_gaps", {}, "gaps"),
                ]
            )
        return ModelTurn(selection=Selection(target_id=target_id))


def strict_schema(schema):
    """Make every object property required for OpenAI strict function schemas."""
    schema = json.loads(json.dumps(schema))
    schema.pop("default", None)
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
        schema["required"] = list(schema.get("properties", {}))
    for key, value in schema.items():
        if isinstance(value, dict):
            schema[key] = {
                k: strict_schema(v) if isinstance(v, dict) else v for k, v in value.items()
            }
        elif isinstance(value, list):
            schema[key] = [strict_schema(v) if isinstance(v, dict) else v for v in value]
    return schema


class OpenAIModel:
    """Fixed OpenAI endpoint; storage disabled and provider failures sanitized."""

    provider_name = "openai"

    def __init__(self, api_key=None, model=None, transport=None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model or os.environ.get("OPENAI_MODEL")
        self.transport = transport

    def complete(self, messages, tools, timeout):
        if not self.api_key or not self.model:
            raise ModelFailure("Set OPENAI_API_KEY and OPENAI_MODEL to enable OpenAI")
        if len(self.model) > 200:
            raise ModelFailure("OPENAI_MODEL is too long")
        inputs = []
        for message in messages:
            if message["role"] == "user":
                inputs.append({"role": "user", "content": message["content"]})
            elif message["role"] == "assistant":
                # Replay all raw output items, including opaque reasoning, only to the provider.
                inputs.extend(message["provider_content"] or [])
            elif message["role"] == "tool":
                inputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": message["tool_call_id"],
                        "output": message["content"],
                    }
                )
        declarations = [
            {
                "type": "function",
                "name": t["name"],
                "description": t["description"],
                "parameters": strict_schema(t["parameters"]),
                "strict": True,
            }
            for t in tools
        ]
        declarations.extend(
            [
                {
                    "type": "function",
                    "name": "finish_investigation",
                    "description": "Finish with a verified target ID and manual-check suggestions; never supply graph findings.",
                    "parameters": strict_schema(Selection.model_json_schema()),
                    "strict": True,
                },
                {
                    "type": "function",
                    "name": "request_clarification",
                    "description": "Ask the user to disambiguate the target.",
                    "parameters": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            ]
        )
        payload = {
            "model": self.model,
            "instructions": messages[0]["content"],
            "input": inputs,
            "tools": declarations,
            "tool_choice": "required",
            "parallel_tool_calls": False,
            "max_output_tokens": 2000,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        deadline = time.monotonic() + timeout
        try:
            with (
                httpx.Client(
                    timeout=timeout, transport=self.transport, follow_redirects=False
                ) as client,
                client.stream(
                    "POST",
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                raw = b""
                for chunk in response.iter_bytes():
                    raw += chunk
                    if len(raw) > 100000 or time.monotonic() > deadline:
                        raise ModelFailure("Model response exceeded size/time budget")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ModelFailure("OpenAI returned an invalid response object")
            if data.get("status") != "completed":
                raise ModelFailure("OpenAI response was incomplete or refused")
            outputs = data["output"]
            function_calls = [item for item in outputs if item["type"] == "function_call"]
            calls = []
            for item in function_calls:
                arguments = json.loads(item["arguments"])
                if not isinstance(arguments, dict):
                    raise ModelFailure("Invalid model tool arguments")
                if item["name"] == "finish_investigation":
                    if len(function_calls) != 1:
                        raise ModelFailure("Model mixed final selection with tool calls")
                    return ModelTurn(selection=Selection.model_validate(arguments))
                if item["name"] == "request_clarification":
                    return ModelTurn(clarification=str(arguments.get("message", "Choose a target")))
                if not isinstance(item["name"], str) or not isinstance(arguments, dict):
                    raise ModelFailure("Invalid model tool call")
                calls.append(ToolCall(item["name"], arguments, item["call_id"]))
            return ModelTurn(calls=calls, provider_content=outputs)
        except (
            httpx.HTTPError,
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise ModelFailure(
                "OpenAI request or response failed; check provider configuration/quota"
            ) from error
