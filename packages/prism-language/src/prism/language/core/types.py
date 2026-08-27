# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical type representation for the typed core."""

from __future__ import annotations

from dataclasses import dataclass

SCALAR_TYPES = frozenset(
    {
        "Bool",
        "Bytes",
        "Char",
        "Decimal",
        "Duration",
        "Float",
        "Int",
        "Nat",
        "Never",
        "Prop",
        "String",
        "Time",
        "Type",
        "Unit",
    }
)

PROVENANCE_TYPES = frozenset(
    {
        "Generated",
        "Evidence",
        "Computed",
    }
)

ASSURANCE_TYPES = frozenset(
    {
        "Supported",
        "Validated",
        "Proof",
        "Verified",
    }
)

PROTECTED_TYPES = PROVENANCE_TYPES | ASSURANCE_TYPES

BUILTIN_TYPES = (
    SCALAR_TYPES
    | PROTECTED_TYPES
    | frozenset(
        {
            "Connection",
            "CoreTerm",
            "Execution",
            "FailureUnion",
            "GraphSource",
            "List",
            "Map",
            "MaterialPolicy",
            "Option",
            "Resource",
            "Result",
            "ProofSyntax",
            "Claim",
            "RefinementAttempt",
            "RefinementFailure",
            "RefinementFeedback",
            "RefinementPolicy",
            "Reasoning",
            "ReasoningStopped",
            "Relation",
            "Set",
            "Skill",
            "Skills",
            "Tool",
            "Tools",
            "Hooks",
            "Codex",
            "Claude",
            "Source",
            "Tuple",
            "Workflow",
        }
    )
)


@dataclass(frozen=True, slots=True)
class CoreType:
    name: str
    arguments: tuple["CoreType", ...] = ()
    parameters: tuple[tuple[str | None, "CoreType"], ...] = ()
    result: "CoreType | None" = None
    effects: tuple[str, ...] = ()

    @property
    def is_function(self) -> bool:
        return self.result is not None

    def render(self) -> str:
        if self.result is not None:
            params = ", ".join(
                f"{name}: {value.render()}" if name else value.render()
                for name, value in self.parameters
            )
            rendered = f"({params}) -> {self.result.render()}"
            if self.effects:
                rendered += f" ! {{{', '.join(self.effects)}}}"
            return rendered
        if not self.arguments:
            return self.name
        return f"{self.name}[{', '.join(item.render() for item in self.arguments)}]"

    def is_assignable_from(self, other: "CoreType") -> bool:
        if self.name == "Any" or other.name == "Never":
            return True
        if self.name != other.name:
            return False
        if self.result is not None or other.result is not None:
            return self == other
        if self.name in {"Skills", "Tools"}:
            return bool(self.arguments) and all(
                any(expected.is_assignable_from(actual) for expected in self.arguments)
                for actual in other.arguments
            )
        return len(self.arguments) == len(other.arguments) and all(
            expected.is_assignable_from(actual)
            for expected, actual in zip(self.arguments, other.arguments, strict=True)
        )


ANY = CoreType("Any")
BOOL = CoreType("Bool")
INT = CoreType("Int")
STRING = CoreType("String")
UNIT = CoreType("Unit")
PROP = CoreType("Prop")


def result_type(value: CoreType, error: CoreType) -> CoreType:
    return CoreType("Result", (value, error))
