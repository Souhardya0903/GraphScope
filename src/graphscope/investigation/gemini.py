"""Gemini function-calling adapter using the same bounded investigation loop."""

import json
import os
import re
import time
from uuid import uuid4

import httpx
from pydantic import ValidationError

from graphscope.investigation.agent import ModelFailure, ModelTurn, Selection, ToolCall


class GeminiModel:
    provider_name = "gemini"

    def __init__(self, api_key=None, model=None, transport=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL")
        self.transport = transport

    def complete(self, messages, tools, timeout):
        if not self.api_key or not self.model:
            raise ModelFailure("Set GEMINI_API_KEY and GEMINI_MODEL to enable Gemini")
        if not re.fullmatch(r"[a-zA-Z0-9._-]{1,200}", self.model):
            raise ModelFailure("GEMINI_MODEL must be a plain model ID")
        contents, provider_ids = [], set()
        for message in messages:
            if message["role"] == "system":
                continue
            if message["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": message["content"]}]})
            elif message["role"] == "assistant":
                # Replay opaque signatures verbatim, without putting them in activity/report output.
                raw_contents = message["provider_content"] or []
                contents.extend(raw_contents)
                for content in raw_contents:
                    provider_ids.update(
                        p["functionCall"]["id"]
                        for p in content["parts"]
                        if "functionCall" in p and p["functionCall"].get("id")
                    )
            else:
                response = {"name": message["name"], "response": json.loads(message["content"])}
                if message["tool_call_id"] in provider_ids:
                    response["id"] = message["tool_call_id"]
                part = {"functionResponse": response}
                if (
                    contents
                    and contents[-1]["role"] == "user"
                    and "functionResponse" in contents[-1]["parts"][0]
                ):
                    contents[-1]["parts"].append(part)
                else:
                    contents.append({"role": "user", "parts": [part]})
        declarations = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "parametersJsonSchema": tool["parameters"],
            }
            for tool in tools
        ]
        declarations.extend(
            [
                {
                    "name": "finish_investigation",
                    "description": "Finish with a verified target ID and manual checks; graph findings are generated separately.",
                    "parametersJsonSchema": Selection.model_json_schema(),
                },
                {
                    "name": "request_clarification",
                    "description": "Ask the user to disambiguate a target.",
                    "parametersJsonSchema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                    },
                },
            ]
        )
        payload = {
            "systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
            "contents": contents,
            "tools": [{"functionDeclarations": declarations}],
            "toolConfig": {"functionCallingConfig": {"mode": "ANY"}},
            "generationConfig": {"maxOutputTokens": 2000, "temperature": 0},
        }
        deadline = time.monotonic() + timeout
        try:
            with (
                httpx.Client(
                    timeout=timeout, transport=self.transport, follow_redirects=False
                ) as client,
                client.stream(
                    "POST",
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                raw = b""
                for chunk in response.iter_bytes():
                    raw += chunk
                    if len(raw) > 100000 or time.monotonic() > deadline:
                        raise ModelFailure("Gemini response exceeded size/time budget")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ModelFailure("Invalid Gemini response object")
            candidate = data["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ModelFailure("Gemini generation was incomplete or blocked")
            content = candidate["content"]
            raw_calls = [p["functionCall"] for p in content["parts"] if "functionCall" in p]
            calls = []
            for call in raw_calls:
                arguments = call.get("args", {})
                if not isinstance(arguments, dict) or not isinstance(call["name"], str):
                    raise ModelFailure("Invalid Gemini function call")
                if call["name"] == "finish_investigation":
                    if len(raw_calls) != 1:
                        raise ModelFailure("Gemini mixed final selection with tool calls")
                    return ModelTurn(selection=Selection.model_validate(arguments))
                if call["name"] == "request_clarification":
                    return ModelTurn(clarification=str(arguments.get("message", "Choose a target")))
                calls.append(ToolCall(call["name"], arguments, call.get("id") or uuid4().hex))
            return ModelTurn(calls=calls, provider_content=[content])
        except httpx.HTTPStatusError as error:
            raise ModelFailure(
                f"Gemini request failed (HTTP {error.response.status_code}); check model access, key, or quota"
            ) from error
        except (
            httpx.HTTPError,
            ValidationError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise ModelFailure(
                "Gemini request or response failed; check provider configuration"
            ) from error
