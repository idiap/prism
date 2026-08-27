# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime-configured Python effect adapter."""

from __future__ import annotations

import importlib
from importlib import metadata
from typing import Mapping

from prism.language.core import Err
from prism.language.effects import EffectRequest, EffectResult


class PythonEffectHandler:
    def __init__(self, bindings: Mapping[str, str] | None = None) -> None:
        self.bindings = {
            **_installed_bindings(),
            **dict(bindings or {}),
        }

    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
        return "Python.Call" in effects and symbol in self.bindings

    def execute(self, request: EffectRequest) -> EffectResult:
        if not self.handles(request.symbol, request.effects):
            raise ValueError(f"Python effect handler cannot execute `{request.symbol}`")
        if "PythonCall" not in request.permissions:
            raise PermissionError(
                f"Python effect `{request.symbol}` requires PythonCall permission"
            )
        callable_ref = self.bindings[request.symbol]
        module_name, separator, function_name = callable_ref.partition(":")
        if not separator:
            raise ValueError(f"invalid runtime Python binding `{callable_ref}`")
        try:
            function = getattr(importlib.import_module(module_name), function_name)
            result = function(request)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            return EffectResult(
                Err(message),
                request.result_type,
                diagnostics=(message,),
                provenance={
                    "provider": "python",
                    "operation": request.symbol,
                    "implementation": callable_ref,
                },
                executor=f"python:{module_name}",
            )
        if not isinstance(result, EffectResult):
            raise TypeError(
                f"Python binding `{callable_ref}` returned {type(result).__name__}, expected EffectResult"
            )
        return result


def _installed_bindings() -> dict[str, str]:
    """Discover Python implementations contributed by installed Prism libraries."""

    try:
        entries = metadata.entry_points(group="prism.python_effects")
    except Exception:
        return {}
    bindings: dict[str, str] = {}
    for entry in sorted(entries, key=lambda item: (item.name, item.value)):
        existing = bindings.get(entry.name)
        if existing is not None and existing != entry.value:
            raise ValueError(
                f"duplicate Python effect binding `{entry.name}`: "
                f"`{existing}` and `{entry.value}`"
            )
        bindings[entry.name] = entry.value
    return bindings
