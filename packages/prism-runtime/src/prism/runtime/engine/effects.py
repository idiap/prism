# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Effect execution, schemas, and protected-value contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prism.language.core import (
    PROTECTED_TYPES,
    ComputedValue,
    CoreType,
    DependentPair,
    Err,
    GeneratedValue,
    Ok,
    ValidatedValue,
)
from prism.language.effects import (
    EffectContractError,
    EffectRequest,
    RecordDefinition,
)
from prism.language.evidence import Evidence, Supported
from prism.language.kernel import (
    CheckedTerm,
    Term,
)
from prism.runtime.results import TraceEvent

from .values import CapabilityValue

if TYPE_CHECKING:
    from .execution import _Engine


def _invoke_effect(self: _Engine, name, args, named, result_type, effects):
    self.call_counter += 1
    request = EffectRequest(
        f"call:{self.call_counter}",
        name,
        args,
        named,
        result_type,
        effects,
        permissions=tuple(
            value.type_name
            for value in (*args, *named.values())
            if isinstance(value, CapabilityValue)
        ),
        metadata=self._effect_metadata(name, result_type),
    )
    result = self.handler.execute(request)
    self._validate_effect_result(request, result)
    record = self.effect_recorder.record(request, result)
    self.trace.append(
        TraceEvent(
            "effect",
            name,
            provenance=request.metadata["provenance"],
            metadata={
                "effects": effects,
                "record": record.record_id,
            },
        )
    )
    self.provenance.produce(
        result.value,
        "generated" if name == "generate" else "external_unknown",
        name,
        effect_record=record.record_id,
        synthetic=bool(result.provenance.get("synthetic", False)),
    )
    return result.value


def _effect_metadata(self: _Engine, name: str, result_type: CoreType) -> dict[str, Any]:
    provenance = {
        "generate": "Generated",
    }.get(name, "OperationalResult")
    metadata: dict[str, Any] = {"provenance": provenance}
    if (
        name == "generate"
        and result_type.name == "Result"
        and result_type.arguments
        and result_type.arguments[0].name == "Generated"
        and result_type.arguments[0].arguments
    ):
        output_type = result_type.arguments[0].arguments[0]
        metadata["output_type"] = output_type.render()
        metadata["output_schema"] = self._json_schema(output_type)
    return metadata


def _json_schema(self: _Engine, type_: CoreType) -> dict[str, Any]:
    scalar_types = {
        "Bool": "boolean",
        "Int": "integer",
        "Nat": "integer",
        "Float": "number",
        "Decimal": "number",
        "String": "string",
    }
    if type_.name in scalar_types:
        schema: dict[str, Any] = {"type": scalar_types[type_.name]}
        if type_.name == "Nat":
            schema["minimum"] = 0
        return schema
    if type_.name == "List" and type_.arguments:
        return {"type": "array", "items": self._json_schema(type_.arguments[0])}
    if type_.name == "Option" and type_.arguments:
        return {"anyOf": [self._json_schema(type_.arguments[0]), {"type": "null"}]}
    definition = next(
        (
            item
            for item in self.program.declarations
            if isinstance(item, RecordDefinition) and item.name == type_.name
        ),
        None,
    )
    if definition is None:
        return {"type": "string"}
    properties = {
        field_name: self._json_schema(field_type)
        for field_name, field_type in definition.fields
    }
    return {
        "type": "object",
        "title": definition.name,
        "x-prism-record": definition.name,
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _validate_effect_result(self: _Engine, request: EffectRequest, result: Any) -> None:
    if result.type != request.result_type:
        raise EffectContractError(
            f"handler for `{request.symbol}` returned type {result.type.render()}, "
            f"expected {request.result_type.render()}"
        )
    if not isinstance(result.value, Ok | Err):
        raise EffectContractError(
            f"handler for `{request.symbol}` must return a Result value"
        )
    expected = request.result_type.arguments[0]
    protected = self._protected_types(expected)
    if protected:
        allowed_origin = {
            "Generated": ("generate", "AI.Generate"),
        }.get(expected.name)
        origin_allowed = allowed_origin is not None and (
            request.symbol == allowed_origin[0] and allowed_origin[1] in request.effects
        )
        nested = tuple(
            dict.fromkeys(
                protected_type
                for argument in expected.arguments
                for protected_type in self._protected_types(argument)
            )
        )
        if not origin_allowed or nested:
            protected_type = nested[0] if nested else protected[0]
            detail = (
                f"only `{allowed_origin[0]}` with `{allowed_origin[1]}` may do so"
                if allowed_origin is not None and not nested
                else (
                    "effect handlers cannot introduce nested protected values"
                    if nested
                    else "effect handlers are not an authorized introduction boundary"
                )
            )
            raise EffectContractError(
                f"handler for `{request.symbol}` cannot introduce protected "
                f"type `{protected_type}`; {detail}"
            )
    if isinstance(result.value, Err):
        return
    protected_classes = {
        "Computed": ComputedValue,
        "Generated": GeneratedValue,
        "Evidence": Evidence,
        "Validated": ValidatedValue,
        "Proof": CheckedTerm,
        "Supported": Supported,
        "Verified": DependentPair,
    }
    expected_class = protected_classes.get(expected.name)
    if expected_class is not None and not isinstance(
        result.value.value, expected_class
    ):
        raise EffectContractError(
            f"handler for `{request.symbol}` claimed {expected.render()} but returned "
            f"{type(result.value.value).__name__}"
        )


def _protected_types(
    self: _Engine,
    type_: CoreType,
    seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    protected: list[str] = []
    if type_.name in PROTECTED_TYPES:
        protected.append(type_.name)
    for argument in type_.arguments:
        protected.extend(self._protected_types(argument, seen))
    for _, parameter in type_.parameters:
        protected.extend(self._protected_types(parameter, seen))
    if type_.result is not None:
        protected.extend(self._protected_types(type_.result, seen))
    if type_.name not in seen:
        record = next(
            (
                declaration
                for declaration in self.program.declarations
                if isinstance(declaration, RecordDefinition)
                and declaration.name == type_.name
            ),
            None,
        )
        if record is not None:
            next_seen = seen | {type_.name}
            for _, field_type in record.fields:
                protected.extend(self._protected_types(field_type, next_seen))
    return tuple(dict.fromkeys(protected))


def _builtin_python_call(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    if len(args) != 3:
        raise ValueError("python_call requires operation, input, and permission")
    return self._invoke_effect(
        str(args[0]),
        args[1:],
        named,
        result_type or CoreType("Result", (CoreType("Any"), CoreType("PythonError"))),
        ("Python.Call",),
    )


def _builtin_tool_call(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    if len(args) != 4:
        raise ValueError(
            "tool_call requires operation, input, connection, and permission"
        )
    return self._invoke_effect(
        str(args[0]),
        args[1:],
        named,
        result_type or CoreType("Result", (CoreType("Any"), CoreType("ToolError"))),
        ("Tool.Call",),
    )


def _builtin_generate(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    effect_result_type = result_type or CoreType(
        "Result",
        (
            CoreType("Generated", (CoreType("Any"),)),
            CoreType("ModelFailure"),
        ),
    )
    return self._invoke_effect(
        "generate",
        args,
        named,
        effect_result_type,
        ("AI.Generate",),
    )
