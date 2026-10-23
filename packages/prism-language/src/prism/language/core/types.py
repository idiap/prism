# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical type representation for the typed core."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .declarations import ReasoningInvocationContract

from .indices import ValueIndex

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

PROTECTED_TYPES = (
    PROVENANCE_TYPES | ASSURANCE_TYPES | {"Validator", "MaterialPolicy", "Assessment"}
)

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
            "PolicyDecision",
            "SupportError",
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
    parameter_bindings: tuple[str, ...] = field(default=(), compare=False)
    proposition: ValueIndex | None = None
    binder: str | None = field(default=None, compare=False)
    binding_identity: str | None = field(default=None, compare=False)
    invocation: ReasoningInvocationContract | None = None

    @property
    def is_function(self) -> bool:
        return self.result is not None

    def render(self) -> str:
        if self.proposition is not None:
            return self.proposition.render()
        if self.binder is not None:
            return f"{self.binder}: {self.arguments[0].render()}"
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
        rendered = f"{self.name}[{', '.join(item.render() for item in self.arguments)}]"
        return rendered + (
            " ! {" + ", ".join(self.effects) + "}" if self.effects else ""
        )

    def is_assignable_from(self, other: "CoreType") -> bool:
        if self.name == "Any" or other.name == "Never":
            return True
        if self.proposition != other.proposition:
            return False
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


def substitute_type(type_: CoreType, substitutions: Mapping[str, CoreType]) -> CoreType:
    if type_.name in substitutions and not type_.arguments and not type_.is_function:
        return substitutions[type_.name]
    proposition = type_.proposition
    if proposition is not None:
        proposition = _substitute_index_types(proposition, substitutions)
        proposition = proposition.substitute(
            {
                name: replacement.proposition
                or ValueIndex("reference", replacement.name)
                for name, replacement in substitutions.items()
            }
        )
    return replace(
        type_,
        arguments=tuple(
            substitute_type(item, substitutions) for item in type_.arguments
        ),
        parameters=tuple(
            (name, substitute_type(item, substitutions))
            for name, item in type_.parameters
        ),
        result=substitute_type(type_.result, substitutions) if type_.result else None,
        proposition=proposition,
        invocation=(
            replace(
                type_.invocation,
                parameters=tuple(
                    replace(
                        parameter, type=substitute_type(parameter.type, substitutions)
                    )
                    for parameter in type_.invocation.parameters
                ),
                specialization=tuple(
                    substitute_type(item, substitutions)
                    for item in type_.invocation.specialization
                ),
            )
            if type_.invocation
            else None
        ),
    )


def _substitute_index_types(index, substitutions):
    return replace(
        index,
        type_arguments=tuple(
            substitute_type(item, substitutions) for item in index.type_arguments
        ),
        type=substitute_type(index.type, substitutions)
        if index.type is not None
        else None,
        children=tuple(
            _substitute_index_types(child, substitutions) for child in index.children
        ),
    )
