"""Ollama Cloud native chat adapter; credentials stay on the fixed cloud host."""

import json
import os
import time
from uuid import uuid4

import httpx
from pydantic import ValidationError

from graphscope.investigation.agent import ModelFailure, ModelTurn, Selection, ToolCall


class OllamaModel:
    provider_name = "ollama"

    def __init__(self, api_key=None, model=None, transport=None):
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        self.model = model or os.environ.get("OLLAMA_MODEL")
        self.transport = transport

    def complete(self, messages, tools, timeout):
        if not self.api_key or not self.model:
            raise ModelFailure("Set OLLAMA_API_KEY and OLLAMA_MODEL to enable Ollama Cloud")
        if len(self.model) > 200 or not self.model.strip():
            raise ModelFailure("OLLAMA_MODEL must contain 1..200 characters")
        history = []
        for message in messages:
            if message["role"] == "assistant":
                # Replay provider messages (including opaque thinking) privately.
                history.extend(message["provider_content"] or [])
            elif message["role"] == "tool":
                history.append(
                    {"role": "tool", "tool_name": message["name"], "content": message["content"]}
                )
            else:
                history.append({"role": message["role"], "content": message["content"]})
        history[0]["content"] += (
            "\nUse function calls for actions. Finish by calling finish_investigation; "
            "do not return a prose final answer."
        )
        declarations = [dict(tool) for tool in tools]
        declarations.extend(
            [
                {
                    "name": "finish_investigation",
                    "description": "Finish with a verified target ID and manual checks; graph findings are generated separately.",
                    "parameters": Selection.model_json_schema(),
                },
                {
                    "name": "request_clarification",
                    "description": "Ask the user to disambiguate a target.",
                    "parameters": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                },
            ]
        )
        payload = {
            "model": self.model,
            "messages": history,
            "stream": False,
            "tools": [{"type": "function", "function": t} for t in declarations],
            "options": {"num_predict": 2000, "temperature": 0},
        }
        deadline = time.monotonic() + timeout
        try:
            with (
                httpx.Client(
                    timeout=timeout, transport=self.transport, follow_redirects=False
                ) as client,
                client.stream(
                    "POST",
                    "https://ollama.com/api/chat",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                raw = b""
                for chunk in response.iter_bytes():
                    raw += chunk
                    if len(raw) > 100000 or time.monotonic() > deadline:
                        raise ModelFailure("Ollama response exceeded size/time budget")
            data = json.loads(raw)
            if data.get("done") is not True or data.get("done_reason") != "stop":
                raise ModelFailure("Ollama generation was incomplete or blocked")
            content = data["message"]
            if content["role"] != "assistant":
                raise ModelFailure("Invalid Ollama response role")
            raw_calls = content.get("tool_calls", [])
            calls = []
            for item in raw_calls:
                call = item["function"]
                name, arguments = call["name"], call["arguments"]
                if not isinstance(name, str) or not isinstance(arguments, dict):
                    raise ModelFailure("Invalid Ollama function call")
                if name in {"finish_investigation", "request_clarification"}:
                    if len(raw_calls) != 1:
                        raise ModelFailure("Ollama mixed final selection with tool calls")
                    if name == "finish_investigation":
                        return ModelTurn(selection=Selection.model_validate(arguments))
                    return ModelTurn(clarification=str(arguments.get("message", "Choose a target")))
                calls.append(ToolCall(name, arguments, uuid4().hex))
            return ModelTurn(calls=calls, provider_content=[content])
        except httpx.HTTPStatusError as error:
            raise ModelFailure(
                f"Ollama request failed (HTTP {error.response.status_code}); check model access, key, or quota"
            ) from error
        except (
            httpx.HTTPError,
            ValidationError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as error:
            raise ModelFailure(
                "Ollama request or response failed; check provider configuration"
            ) from error
