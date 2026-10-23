# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""One checked contract for occurrence classification, origins, and assurance."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Mapping

from .declarations import RecordContract
from .types import CoreType, substitute_type


@dataclass(frozen=True, slots=True)
class TaxonomyReference:
    taxonomy: str
    version: str
    facet: str
    taxon: str
    status: Literal["active", "provisional"]


@dataclass(frozen=True, slots=True)
class ReasoningClassification:
    state: Literal["unclassified", "classified"] = "unclassified"
    references: tuple[TaxonomyReference, ...] = ()
    archetype_state: Literal["unclassified", "applicable", "not_applicable"] = (
        "unclassified"
    )


@dataclass(frozen=True, slots=True)
class OriginConstraint:
    producers: tuple[str, ...] = ("unconstrained",)
    ancestors: tuple[str, ...] = ("unconstrained",)


@dataclass(frozen=True, slots=True)
class AssuranceRequirement:
    kind: Literal["unchecked", "supported", "validated", "proof", "verified"] = (
        "unchecked"
    )
    proposition: CoreType | None = None


@dataclass(frozen=True, slots=True)
class ValueRequirement:
    path: tuple[str, ...]
    type: CoreType
    origin: OriginConstraint = OriginConstraint()
    assurance: AssuranceRequirement = AssuranceRequirement()


@dataclass(frozen=True, slots=True)
class RelationContract:
    identity: str
    source_type: CoreType
    target_type: CoreType
    certificate_type: CoreType
    requirements: tuple[ValueRequirement, ...]


@dataclass(frozen=True, slots=True)
class OccurrenceContract:
    identity: str
    owner_identity: str
    method_identity: str
    classification: ReasoningClassification
    input_type: CoreType
    output_type: CoreType
    requirements: tuple[ValueRequirement, ...]
    relation: RelationContract | None = None
    input_requirements: tuple[ValueRequirement, ...] = ()
    execution_kind: Literal["method", "structural", "workflow"] = "method"

    def specialize(
        self,
        substitutions: Mapping[str, CoreType],
        records: Mapping[str, RecordContract],
        variants: Mapping[str, tuple[str, ...]] | None = None,
    ) -> OccurrenceContract:
        input_type = substitute_type(self.input_type, substitutions)
        output = substitute_type(self.output_type, substitutions)
        relation = self.relation
        if relation is not None:
            certificate = substitute_type(relation.certificate_type, substitutions)
            relation = replace(
                relation,
                source_type=substitute_type(relation.source_type, substitutions),
                target_type=substitute_type(relation.target_type, substitutions),
                certificate_type=certificate,
                requirements=value_requirements(
                    certificate, records, variants=variants
                ),
            )
        return replace(
            self,
            input_type=input_type,
            input_requirements=_specialized_requirements(
                self.input_requirements,
                value_requirements(input_type, records, variants=variants),
            ),
            output_type=output,
            requirements=_specialized_requirements(
                self.requirements,
                value_requirements(output, records, variants=variants),
            ),
            relation=relation,
        )


def _specialized_requirements(original, specialized):
    prior = {item.path: item.origin for item in original}
    return tuple(
        replace(
            item,
            origin=OriginConstraint(
                _intersect_origins(
                    prior.get(item.path, OriginConstraint()).producers,
                    item.origin.producers,
                ),
                _intersect_origins(
                    prior.get(item.path, OriginConstraint()).ancestors,
                    item.origin.ancestors,
                ),
            ),
        )
        for item in specialized
    )


def _intersect_origins(left, right):
    if left == ("unconstrained",):
        return right
    if right == ("unconstrained",):
        return left
    intersection = tuple(item for item in left if item in right)
    if not intersection:
        raise ValueError("specialized occurrence has incompatible origin requirements")
    return intersection


def value_requirements(
    type_: CoreType,
    records: Mapping[str, RecordContract],
    path: tuple[str, ...] = (),
    seen: frozenset[str] = frozenset(),
    *,
    variants: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[ValueRequirement, ...]:
    """Normalize type requirements without inferring an origin or a trust rank."""
    producers = {
        "Generated": ("generated",),
        "Computed": ("computed",),
        "Evidence": ("asserted", "acquired", "computed"),
    }.get(type_.name, ("unconstrained",))
    assurance = _assurance_requirement(type_)
    root = ValueRequirement(path, type_, OriginConstraint(producers), assurance)
    children = _requirement_children(type_, records, seen, variants or {})
    return (
        root,
        *(
            requirement
            for name, child in children
            for requirement in value_requirements(
                child, records, (*path, name), seen | {type_.name}, variants=variants
            )
        ),
    )


def _assurance_requirement(type_):
    if type_.name in {"Supported", "Proof"}:
        return AssuranceRequirement(
            "supported" if type_.name == "Supported" else "proof", type_.arguments[0]
        )
    if type_.name in {"Validated", "Verified"}:
        return AssuranceRequirement(
            "validated" if type_.name == "Validated" else "verified", type_.arguments[1]
        )
    return AssuranceRequirement()


def _requirement_children(type_, records, seen, variants):
    if type_.name in {"Generated", "Computed", "Evidence"}:
        return (("value", type_.arguments[0]),)
    if type_.name in {"Validated", "Verified"}:
        value = type_.arguments[0]
        return (("value", value.arguments[0] if value.binder is not None else value),)
    if type_.name == "Option":
        return (("some", type_.arguments[0]),)
    if type_.name in {"List", "Set"}:
        return (("*", type_.arguments[0]),)
    if type_.name == "Tuple":
        return tuple((str(index), item) for index, item in enumerate(type_.arguments))
    if type_.name == "Map":
        return tuple(zip(("keys", "values"), type_.arguments, strict=True))
    if type_.name in variants and type_.name not in seen:
        return tuple(
            (f"case:{name}", CoreType(name, type_.arguments))
            for name in variants[type_.name]
        )
    record = records.get(type_.name)
    if record is None or type_.name in seen:
        return ()
    substitutions = dict(zip(record.type_parameters, type_.arguments, strict=True))
    return tuple(
        (field.name, substitute_type(field.type, substitutions))
        for field in record.fields
    )
