# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""JSON schema conversion and typed response decoding."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from prism.language.core import RecordValue


class LiteLLMResponseError(RuntimeError):
    pass


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
        return _decode_object(value, schema)
    if schema_type == "array":
        if not isinstance(value, list):
            raise LiteLLMResponseError("model output must be a JSON array")
        return [_decode_value(item, schema["items"]) for item in value]
    return _decode_primitive(value, schema_type)


def _decode_object(value: Any, schema: Mapping[str, Any]) -> Any:
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


def _decode_primitive(value: Any, schema_type: str | None) -> Any:
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
