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

from prism.language.core import Err, GeneratedValue, Ok
from prism.language.effects import EffectRequest, EffectResult

from .schema import LiteLLMResponseError as LiteLLMResponseError
from .schema import _decode_value as _decode_value
from .schema import _json_value as _json_value
from .schema import _without_prism_extensions as _without_prism_extensions


class LiteLLMConfigurationError(RuntimeError):
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
