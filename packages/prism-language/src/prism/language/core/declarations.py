# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Resolved core declaration contracts."""

from __future__ import annotations

from dataclasses import dataclass

from .types import CoreType


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: CoreType


@dataclass(frozen=True, slots=True)
class CallableContract:
    name: str
    parameters: tuple[Parameter, ...]
    result: CoreType
    effects: tuple[str, ...] = ()
    kind: str = "def"
    type_parameters: tuple[str, ...] = ()
    failure: CoreType | None = None

    @property
    def type(self) -> CoreType:
        if self.kind == "relation":
            return CoreType(
                "Relation",
                (
                    CoreType(self.name),
                    *tuple(item.type for item in self.parameters),
                    self.result,
                ),
            )
        result = self.result
        effects = self.effects
        if self.kind == "workflow":
            result = CoreType(
                "Workflow",
                (
                    self.result,
                    self.failure or CoreType("Never"),
                    *(CoreType(effect) for effect in self.effects),
                ),
            )
            effects = ()
        elif self.kind == "reasoning":
            result = CoreType("Reasoning", (self.result,))
            effects = ()
        return CoreType(
            "Function",
            parameters=tuple((item.name, item.type) for item in self.parameters),
            result=result,
            effects=effects,
        )


@dataclass(frozen=True, slots=True)
class RecordContract:
    name: str
    fields: tuple[Parameter, ...]
    type_parameters: tuple[str, ...] = ()
