# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed conversion of host-supplied entry arguments."""

from __future__ import annotations

import base64
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Mapping, NoReturn

from prism.language.core import (
    CoreType,
    RecordValue,
)
from prism.language.effects import (
    FunctionDefinition,
    RecordDefinition,
)

from .values import CapabilityValue

if TYPE_CHECKING:
    from .execution import _Engine


def _entry_arguments(self: _Engine, definition: FunctionDefinition) -> tuple[Any, ...]:
    supplied = {} if self.entry_arguments is None else self.entry_arguments
    if not isinstance(supplied, Mapping):
        raise TypeError("entry_arguments must be a mapping")
    host_parameters = {
        name: type_
        for name, type_ in definition.parameters
        if not self._is_capability(type_)
    }
    missing = sorted(set(host_parameters) - set(supplied))
    extra = sorted(set(supplied) - set(host_parameters))
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if extra:
            details.append("extra: " + ", ".join(extra))
        raise ValueError("invalid entry arguments (" + "; ".join(details) + ")")
    return tuple(
        self._entry_argument(name, type_, supplied)
        for name, type_ in definition.parameters
    )


def _is_capability(type_: CoreType) -> bool:
    return type_.name in {
        "Model",
        "ModelGenerate",
        "DataRead",
        "FileRead",
        "ClockRead",
        "ToolCall",
        "ContextDisclose",
        "MCPCall",
        "NetworkRequest",
        "ProcessRun",
        "PythonCall",
    }


def _entry_argument(
    self: _Engine,
    name: str,
    type_: CoreType,
    supplied: Mapping[str, Any],
) -> Any:
    if type_.name == "Model":
        return "prism-test-model"
    if self._is_capability(type_):
        return CapabilityValue(type_.name)
    return self._host_value(supplied[name], type_, name)


def _host_value(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    type_ = self._resolve_alias(type_)
    converter = _HOST_VALUES.get(type_.name)
    if converter is not None:
        return converter(self, value, type_, path)
    arity = {"List": 1, "Set": 1, "Map": 2, "Option": 1}.get(type_.name)
    if arity is not None and len(type_.arguments) == arity:
        return _HOST_COLLECTIONS[type_.name](self, value, type_, path)
    return _host_named(self, value, type_, path)


def _resolve_alias(self: _Engine, type_: CoreType) -> CoreType:
    seen: set[str] = set()
    while type_.name in self.program.aliases and type_.name not in seen:
        seen.add(type_.name)
        type_ = self.program.aliases[type_.name]
    return type_


def _host_variant(
    self: _Engine,
    value: Any,
    type_: CoreType,
    constructors: tuple[str, ...],
    path: str,
) -> Any:
    if isinstance(value, str):
        constructor, fields = value, {}
    elif isinstance(value, Mapping) and len(value) == 1:
        constructor, fields = next(iter(value.items()))
        if not isinstance(fields, Mapping):
            self._invalid_host_value(path, type_, value)
    else:
        self._invalid_host_value(path, type_, value)
    if constructor not in constructors:
        self._invalid_host_value(path, type_, value)
    return self._host_value(fields, CoreType(str(constructor)), path)


def _invalid_host_value(path: str, type_: CoreType, value: Any) -> NoReturn:
    raise TypeError(
        f"host argument `{path}` expected {type_.render()}, got {type(value).__name__}"
    )


def _host_any(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    return value


def _host_unit(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if value is None:
        return None
    self._invalid_host_value(path, type_, value)


def _host_bool(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if type(value) is bool:
        return value
    self._invalid_host_value(path, type_, value)


def _host_int(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if type(value) is int and (type_.name != "Nat" or value >= 0):
        return value
    self._invalid_host_value(path, type_, value)


def _host_float(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if type(value) in {int, float}:
        return float(value)
    self._invalid_host_value(path, type_, value)


def _host_decimal(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if type(value) in {int, float, str}:
        try:
            return Decimal(str(value))
        except InvalidOperation:
            pass
    self._invalid_host_value(path, type_, value)


def _host_string(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if isinstance(value, str):
        return value
    self._invalid_host_value(path, type_, value)


def _host_char(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if isinstance(value, str) and len(value) == 1:
        return value
    self._invalid_host_value(path, type_, value)


def _host_bytes(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if isinstance(value, str):
        try:
            return base64.b64decode(value, validate=True)
        except ValueError:
            pass
    self._invalid_host_value(path, type_, value)


def _host_list(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if not isinstance(value, list):
        self._invalid_host_value(path, type_, value)
    converted = [
        self._host_value(item, type_.arguments[0], f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    return converted if type_.name == "List" else set(converted)


def _host_tuple(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if not isinstance(value, list):
        self._invalid_host_value(path, type_, value)
    if len(type_.arguments) != len(value):
        self._invalid_host_value(path, type_, value)
    return tuple(
        self._host_value(item, item_type, f"{path}[{index}]")
        for index, (item, item_type) in enumerate(
            zip(value, type_.arguments, strict=True)
        )
    )


def _host_map(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    if not isinstance(value, Mapping):
        self._invalid_host_value(path, type_, value)
    return {
        self._host_value(key, type_.arguments[0], f"{path}.<key>"): self._host_value(
            item, type_.arguments[1], f"{path}[{key!r}]"
        )
        for key, item in value.items()
    }


def _host_option(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    return None if value is None else self._host_value(value, type_.arguments[0], path)


def _host_named(self: _Engine, value: Any, type_: CoreType, path: str) -> Any:
    variants = self.program.variants.get(type_.name)
    if variants is not None:
        return self._host_variant(value, type_, variants, path)
    definition = next(
        (
            item
            for item in self.program.declarations
            if isinstance(item, RecordDefinition) and item.name == type_.name
        ),
        None,
    )
    if definition is not None:
        if not isinstance(value, Mapping):
            self._invalid_host_value(path, type_, value)
        expected = {name for name, _ in definition.fields}
        if set(value) != expected:
            missing = sorted(expected - set(value))
            extra = sorted(set(value) - expected)
            details = []
            if missing:
                details.append("missing fields: " + ", ".join(missing))
            if extra:
                details.append("extra fields: " + ", ".join(extra))
            raise ValueError(f"invalid host value `{path}` ({'; '.join(details)})")
        return RecordValue(
            definition.name,
            {
                field_name: self._host_value(
                    value[field_name], field_type, f"{path}.{field_name}"
                )
                for field_name, field_type in definition.fields
            },
        )
    self._invalid_host_value(path, type_, value)


_HOST_VALUES = {
    "Any": _host_any,
    "Unit": _host_unit,
    "Bool": _host_bool,
    "Int": _host_int,
    "Nat": _host_int,
    "Float": _host_float,
    "Decimal": _host_decimal,
    "Duration": _host_string,
    "String": _host_string,
    "Time": _host_string,
    "Char": _host_char,
    "Bytes": _host_bytes,
    "Tuple": _host_tuple,
}

_HOST_COLLECTIONS = {
    "List": _host_list,
    "Set": _host_list,
    "Map": _host_map,
    "Option": _host_option,
}
