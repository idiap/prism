# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Structural value indices used by dependent types.

Symbols are lexical identities after checking. Display labels never participate
in equality, so importing or renaming a symbol does not change its claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .types import CoreType


@dataclass(frozen=True, slots=True)
class ValueIndex:
    kind: str
    symbol: str
    children: tuple["ValueIndex", ...] = ()
    label: str = field(default="", compare=False)
    argument_names: tuple[str | None, ...] = ()
    type_arguments: tuple["CoreType", ...] = ()
    type: "CoreType | None" = field(default=None, compare=False)

    def substitute(self, bindings: Mapping[str, "ValueIndex"]) -> "ValueIndex":
        if self.kind == "reference" and self.symbol in bindings:
            return bindings[self.symbol]
        return replace(
            self, children=tuple(child.substitute(bindings) for child in self.children)
        )

    def render(self) -> str:
        if self.kind in {"reference", "literal"}:
            return self.label or self.symbol
        if self.kind == "field":
            return f"{self.children[0].render()}.{self.symbol}"
        if self.kind == "index":
            return f"{self.children[0].render()}[{self.children[1].render()}]"
        if self.kind == "unary":
            return f"{self.symbol} {self.children[0].render()}"
        if self.kind == "binary":
            return f"({self.children[0].render()} {self.symbol} {self.children[1].render()})"
        if self.kind == "apply":
            specialization = (
                "[" + ", ".join(item.render() for item in self.type_arguments) + "]"
                if self.type_arguments
                else ""
            )
            arguments = ", ".join(
                f"{name} = {child.render()}" if name else child.render()
                for name, child in zip(
                    self.argument_names, self.children[1:], strict=True
                )
            )
            return f"{self.children[0].render()}{specialization}({arguments})"
        raise ValueError(f"unsupported value index {self.kind}")
