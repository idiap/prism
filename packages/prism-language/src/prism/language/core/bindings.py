# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Immutable scopes and symbols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .types import CoreType


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    type: CoreType
    value: Any = None


class BindingError(ValueError):
    pass


class BindingScope:
    def __init__(self, initial: Mapping[str, Binding] | None = None) -> None:
        self._bindings = dict(initial or {})

    def bind(self, binding: Binding) -> None:
        if binding.name in self._bindings:
            raise BindingError(f"duplicate immutable binding `{binding.name}`")
        self._bindings[binding.name] = binding

    def resolve(self, name: str) -> Binding:
        try:
            return self._bindings[name]
        except KeyError as exc:
            raise BindingError(f"unknown name `{name}`") from exc

    def snapshot(self) -> dict[str, Binding]:
        return dict(self._bindings)
