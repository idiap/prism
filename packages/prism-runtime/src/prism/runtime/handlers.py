# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in typed effect handlers and handler composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from prism.language.core import Err, GeneratedValue, Ok, RecordValue
from prism.language.effects import EffectHandler, EffectRequest, EffectResult


class FakeEffectHandler:
    """Deterministic generator for tests and structural demonstrations."""

    def __init__(
        self,
        *,
        reject_symbols: tuple[str, ...] = (),
        generated_outputs: Mapping[str, Any] | None = None,
    ) -> None:
        self.reject_symbols = reject_symbols
        self.generated_outputs = dict(generated_outputs or {})

    @classmethod
    def accepting_common_standards(cls) -> "FakeEffectHandler":
        return cls()

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return "AI.Generate" in effects or symbol == "generate"

    def execute(self, request: EffectRequest) -> EffectResult:
        if request.symbol in self.reject_symbols:
            value = Err(f"synthetic rejection for {request.symbol}")
        elif request.symbol == "generate" and request.arguments:
            supplied = request.arguments[0]
            output_type = request.metadata.get("output_type")
            output_schema = request.metadata.get("output_schema")
            if (
                isinstance(output_type, str)
                and isinstance(supplied, RecordValue)
                and supplied.type_name != output_type
            ):
                fixture = self.generated_outputs.get(output_type)
                if fixture is not None:
                    value = Ok(GeneratedValue(fixture, "fake"))
                elif _matches_record_schema(supplied, output_schema):
                    value = Ok(
                        GeneratedValue(
                            RecordValue(output_type, dict(supplied.fields)),
                            "fake",
                        )
                    )
                else:
                    value = Err(
                        "fake handler requires a generated output fixture for "
                        + output_type
                    )
            elif (
                isinstance(output_type, str)
                and isinstance(output_schema, Mapping)
                and output_schema.get("type") == "object"
            ):
                fixture = self.generated_outputs.get(output_type)
                generated = (
                    fixture
                    if fixture is not None
                    else _value_from_schema(output_schema)
                )
                value = Ok(GeneratedValue(generated, "fake"))
            else:
                value = Ok(GeneratedValue(supplied, "fake"))
        else:
            value = Ok(GeneratedValue(request.arguments, "fake"))
        return EffectResult(
            value,
            request.result_type,
            provenance={"handler": "fake", "synthetic": True},
            replay_artifacts={"request": request.arguments},
            executor="fake",
        )


def _matches_record_schema(value: RecordValue, schema: Any) -> bool:
    if not isinstance(schema, Mapping) or schema.get("type") != "object":
        return False
    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list) or not isinstance(properties, Mapping):
        return False
    fields = set(value.fields)
    return fields == set(required) == set(properties)


def _value_from_schema(schema: Mapping[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties")
        if not isinstance(properties, Mapping):
            return RecordValue(str(schema.get("title", "Generated")), {})
        return RecordValue(
            str(schema.get("title", "Generated")),
            {
                str(name): _value_from_schema(property_schema)
                for name, property_schema in properties.items()
                if isinstance(property_schema, Mapping)
            },
        )
    if schema_type == "array":
        return []
    if schema_type == "boolean":
        return False
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    return "synthetic"


class CompositeEffectHandler:
    def __init__(self, handlers: Iterable[EffectHandler]) -> None:
        self.handlers = tuple(handlers)

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return any(handler.handles(symbol, effects) for handler in self.handlers)

    def execute(self, request: EffectRequest) -> EffectResult:
        for handler in self.handlers:
            if handler.handles(request.symbol, request.effects):
                return handler.execute(request)
        raise ValueError(f"no effect handler accepts `{request.symbol}`")


@dataclass(frozen=True, slots=True)
class RoutedEffectHandler:
    """Injected handler port for process, network, MCP, or disclosure effects."""

    effect: str
    executor: Callable[[EffectRequest], EffectResult]

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return self.effect in effects

    def execute(self, request: EffectRequest) -> EffectResult:
        if not self.handles(request.symbol, request.effects):
            raise ValueError(f"{self.effect} handler cannot execute `{request.symbol}`")
        return self.executor(request)


def process_effect_handler(
    executor: Callable[[EffectRequest], EffectResult],
) -> RoutedEffectHandler:
    return RoutedEffectHandler("Process.Run", executor)


def network_effect_handler(
    executor: Callable[[EffectRequest], EffectResult],
) -> RoutedEffectHandler:
    return RoutedEffectHandler("Network.Request", executor)


def mcp_effect_handler(
    executor: Callable[[EffectRequest], EffectResult],
) -> RoutedEffectHandler:
    return RoutedEffectHandler("MCP.Call", executor)
