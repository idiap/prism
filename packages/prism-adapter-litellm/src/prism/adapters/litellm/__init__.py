# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""LiteLLM implementation of the typed AI.Generate effect."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Callable

from prism.language.core import Err, GeneratedValue, Ok, RecordValue
from prism.language.effects import EffectRequest, EffectResult


class LiteLLMConfigurationError(RuntimeError):
    pass


class LiteLLMResponseError(RuntimeError):
    pass


class LiteLLMEffectHandler:
    def __init__(
        self, *, model: str, completion: Callable[..., Any] | None = None
    ) -> None:
        self.model = model
        self._completion = completion

    @classmethod
    def from_environment(
        cls, *, completion: Callable[..., Any] | None = None
    ) -> "LiteLLMEffectHandler":
        model = os.environ.get("PRISM_LLM_MODEL")
        if not model:
            raise LiteLLMConfigurationError(
                "PRISM_LLM_MODEL must be set to use LiteLLMEffectHandler"
            )
        return cls(model=model, completion=completion)

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return symbol == "generate" and "AI.Generate" in effects

    def execute(self, request: EffectRequest) -> EffectResult:
        if not request.arguments:
            return EffectResult(
                Err("generate requires a typed request"),
                request.result_type,
                executor="litellm",
            )
        schema = request.metadata.get("output_schema")
        if not isinstance(schema, Mapping):
            return EffectResult(
                Err("generate requires a typed output schema"),
                request.result_type,
                executor="litellm",
            )
        prompt = _json_value(request.arguments[0])
        system_content = (
            "You are a structured reasoning component. Use only the supplied "
            "request, apply its stated standard, and return the requested JSON "
            "object. Provide a concise rationale, not private chain-of-thought."
        )
        if request.named_arguments.get("hooks"):
            return EffectResult(
                Err("LiteLLM execution cannot activate native Codex or Claude hooks"),
                request.result_type,
                executor="litellm",
            )
        completion = self._completion
        if completion is None:
            from litellm import completion as litellm_completion

            completion = litellm_completion
        public_schema = _without_prism_extensions(schema)
        schema_name = str(schema.get("title", "prism_generated_output"))
        try:
            response = completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_content,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(prompt, sort_keys=True),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": public_schema,
                    },
                },
            )
            payload = _response_payload(response)
            generated = _decode_value(payload, schema)
        except Exception as exc:
            return EffectResult(
                Err(f"structured generation failed: {exc}"),
                request.result_type,
                provenance={"provider": "litellm", "model": self.model},
                executor="litellm",
            )
        value = GeneratedValue(generated, f"litellm:{self.model}")
        return EffectResult(
            Ok(value),
            request.result_type,
            provenance={"provider": "litellm", "model": self.model},
            replay_artifacts={
                "model": self.model,
                "prompt": prompt,
                "output": payload,
            },
            executor="litellm",
        )


def _json_value(value: Any) -> Any:
    if isinstance(value, RecordValue):
        return {
            name: _json_value(field_value) for name, field_value in value.fields.items()
        }
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


def _without_prism_extensions(schema: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: (
            _without_prism_extensions(value)
            if isinstance(value, Mapping)
            else (
                [
                    (
                        _without_prism_extensions(item)
                        if isinstance(item, Mapping)
                        else item
                    )
                    for item in value
                ]
                if isinstance(value, list)
                else value
            )
        )
        for key, value in schema.items()
        if not key.startswith("x-prism-")
    }


def _response_payload(response: Any) -> Any:
    choices = (
        response.get("choices") if isinstance(response, Mapping) else response.choices
    )
    if not choices:
        raise LiteLLMResponseError("model returned no choices")
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, Mapping) else choice.message
    if isinstance(message, Mapping):
        parsed = message.get("parsed")
        content = message.get("content")
    else:
        parsed = getattr(message, "parsed", None)
        content = getattr(message, "content", None)
    if parsed is not None:
        return parsed
    if isinstance(content, Mapping):
        return content
    if not isinstance(content, str) or not content.strip():
        raise LiteLLMResponseError("model returned no structured content")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LiteLLMResponseError("model returned invalid JSON") from exc


def _decode_value(value: Any, schema: Mapping[str, Any]) -> Any:
    if "anyOf" in schema:
        if value is None:
            return None
        options = [item for item in schema["anyOf"] if item.get("type") != "null"]
        if not options:
            raise LiteLLMResponseError("output schema has no non-null option")
        return _decode_value(value, options[0])
    schema_type = schema.get("type")
    if schema_type is not None and not isinstance(schema_type, str):
        raise LiteLLMResponseError("output schema type must be a string")
    if schema_type == "object":
        if not isinstance(value, Mapping):
            raise LiteLLMResponseError("model output must be a JSON object")
        properties = schema.get("properties", {})
        required = schema.get("required", ())
        missing = [name for name in required if name not in value]
        unknown = [name for name in value if name not in properties]
        if missing:
            raise LiteLLMResponseError(
                "model output is missing fields: " + ", ".join(missing)
            )
        if unknown and schema.get("additionalProperties") is False:
            raise LiteLLMResponseError(
                "model output has unknown fields: " + ", ".join(unknown)
            )
        fields = {
            name: _decode_value(value[name], field_schema)
            for name, field_schema in properties.items()
            if name in value
        }
        record_name = schema.get("x-prism-record")
        return RecordValue(str(record_name), fields) if record_name else fields
    if schema_type == "array":
        if not isinstance(value, list):
            raise LiteLLMResponseError("model output must be a JSON array")
        return [_decode_value(item, schema["items"]) for item in value]
    expected_python = {
        "boolean": bool,
        "integer": int,
        "number": (int, float),
        "string": str,
    }.get(schema_type or "")
    if expected_python is not None:
        if schema_type in {"integer", "number"} and isinstance(value, bool):
            raise LiteLLMResponseError(f"model output must be {schema_type}")
        if not isinstance(value, expected_python):
            raise LiteLLMResponseError(f"model output must be {schema_type}")
    return value
