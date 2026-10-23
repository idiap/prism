# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Relation certificate construction, specialization, and tracing."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    CoreType,
    Err,
    Ok,
    substitute_type,
)
from prism.language.workflows import (
    NodeOccurrence,
    RelationDefinition,
)
from prism.runtime.results import OccurrenceOutcome, TraceEvent

from .certificates import _check_certificate
from .components import (
    _component_behavior,
    _component_contract_type,
    _runtime_callable_name,
)
from .occurrences import check_requirements
from .outcomes import observed_values
from .provenance import CallReferences
from .values import (
    RelationBuilderValue,
    _Propagate,
)

if TYPE_CHECKING:
    from .execution import _Engine


def _specialize_relation_types(
    definition: RelationDefinition,
    source_type: CoreType | None,
    target_type: CoreType | None,
) -> tuple[CoreType, CoreType, CoreType]:
    declared_source = definition.parameters[0][1]
    declared_target = definition.parameters[1][1]
    substitutions: dict[str, CoreType] = {}

    if source_type is not None:
        _match_relation_type(
            declared_source, source_type, definition.type_parameters, substitutions
        )
    if target_type is not None:
        _match_relation_type(
            declared_target, target_type, definition.type_parameters, substitutions
        )

    return (
        source_type or _substitute_relation_type(declared_source, substitutions),
        target_type or _substitute_relation_type(declared_target, substitutions),
        _substitute_relation_type(definition.certificate_type, substitutions),
    )


def _trace_relation(
    self,
    node,
    alias,
    reasoning_input,
    result,
    environment,
    *,
    occurrence_instance_id,
    source_reference=None,
    target_reference=None,
):
    if node.relation is None:
        return
    start = len(self.trace)
    try:
        _run_relation(
            self,
            node,
            alias,
            reasoning_input,
            result,
            environment,
            occurrence_instance_id=occurrence_instance_id,
            source_reference=source_reference,
            target_reference=target_reference,
        )
    except (_Propagate, ValueError) as exc:
        error = str(exc.error) if isinstance(exc, _Propagate) else str(exc)
        _finish_relation(self, node, occurrence_instance_id, start, error)
        raise
    _finish_relation(self, node, occurrence_instance_id, start, None)


def _finish_relation(self, node, instance, start, error):
    index = next(
        (
            index
            for index in range(start, len(self.trace))
            if self.trace[index].kind == "reasoning-relation"
            and self.trace[index].metadata.get("target_occurrence_instance") == instance
        ),
        None,
    )
    if index is None:
        index = len(self.trace)
        self.trace.append(
            TraceEvent(
                "reasoning-relation",
                node.relation,
                metadata={
                    "target_occurrence_instance": instance,
                    "target_occurrence_identity": node.contract.identity,
                },
            )
        )
    event = self.trace[index]
    metadata = {
        **event.metadata,
        "relation_instance_id": f"{instance}/relation",
        "declared_relation": asdict(node.contract.relation),
    }
    if error is not None:
        metadata.update(error=error, certificate_valid=False)
    observed = ()
    if "certificate" in metadata:
        observed = observed_values(
            self.provenance,
            metadata["certificate"],
            metadata.get("certificate_reference"),
        )
    self.trace[index] = replace(
        event,
        metadata=metadata,
        status="accepted" if error is None else "rejected",
        outcome=OccurrenceOutcome(
            execution="completed"
            if "certificate" in metadata
            and not isinstance(metadata["certificate"], Err)
            else "failed",
            contract="satisfied" if error is None else "rejected",
            observed=observed,
        ),
    )


def _run_relation(
    self: _Engine,
    node: NodeOccurrence,
    alias: str,
    reasoning_input: Any,
    result: Any,
    environment: dict[str, Any],
    *,
    occurrence_instance_id: str,
    source_reference: str | None = None,
    target_reference: str | None = None,
) -> None:
    if node.relation is None:
        return
    implementation = environment.get(f"{alias}_by")
    if not isinstance(implementation, RelationBuilderValue):
        raise ValueError(f"reasoning edge `{alias}_by` has no relation builder")
    contract = node.contract.relation
    if contract is None or contract.identity != implementation.definition.identity:
        raise ValueError(
            "occurrence relation builder has a different declaration identity"
        )
    builder_failure, builder_effects = _component_behavior(implementation.builder)
    if builder_effects:
        self.trace.append(
            TraceEvent(
                "reasoning-relation",
                node.relation,
                status="rejected",
                metadata={
                    "target_occurrence_identity": node.contract.identity,
                    "target_occurrence_instance": occurrence_instance_id,
                    "certificate_valid": False,
                    "effects": builder_effects,
                    "error": "relation builders must be pure",
                },
            )
        )
        raise ValueError("relation builders must be pure")
    source = reasoning_input
    source_reference = source_reference or self.provenance.record(
        source, "external_unknown", "relation input"
    )
    target_reference = target_reference or self.provenance.record(
        result, "external_unknown", "relation output"
    )
    certificate = self._call(
        implementation.builder,
        (source, result),
        {},
        environment,
        references=CallReferences((source_reference, target_reference)),
    )
    certificate_reference = self.provenance.last
    certificate_value = (
        certificate.value if isinstance(certificate, Ok) else certificate
    )
    if isinstance(certificate, Ok):
        certificate_reference = self.provenance.project(
            certificate_reference, "value", certificate_value
        )
    builder_name = _runtime_callable_name(implementation.builder)
    implementation_identity = f"{implementation.definition.name}:{builder_name}"
    relation_types = _specialize_relation_types(
        implementation.definition,
        node.input_type,
        node.output_type,
    )
    builder_type = _component_contract_type(implementation.builder)
    event = TraceEvent(
        "reasoning-relation",
        node.relation,
        metadata={
            "certificate_reference": certificate_reference,
            "contract": implementation.definition.name,
            "source_module": implementation.definition.source_module,
            "module_hashes": dict(self.program.module_hashes),
            "implementation": implementation_identity,
            "implementation_hash": hashlib.sha256(
                repr(
                    (implementation.definition, implementation.builder.definition)
                ).encode()
            ).hexdigest(),
            "target_occurrence_identity": node.contract.identity,
            "target_occurrence_instance": occurrence_instance_id,
            "source_occurrence": (node.dependencies[0] if node.dependencies else None),
            "source_occurrences": tuple(node.dependencies),
            "target_occurrence": alias,
            "source_type": (node.input_type or relation_types[0]).render(),
            "target_type": (node.output_type or relation_types[1]).render(),
            "certificate_type": (node.certificate_type or relation_types[2]).render(),
            "builder_type": (
                builder_type.render() if builder_type is not None else None
            ),
            "failure_type": builder_failure.render(),
            "effects": builder_effects,
            "certificate": certificate_value,
        },
    )
    if isinstance(certificate, Err):
        self.trace.append(
            replace(
                event,
                status="rejected",
                metadata={
                    **event.metadata,
                    "certificate_valid": False,
                    "error": certificate.error,
                },
            )
        )
        raise _Propagate(certificate.error)
    try:
        bindings = dict(
            zip(
                implementation.definition.parameter_bindings,
                (source, result),
                strict=True,
            )
        )
        _check_certificate(self, certificate_value, contract.certificate_type, bindings)
        check_requirements(
            self,
            contract.requirements,
            certificate_value,
            certificate_reference,
            check_assurance=False,
        )
    except ValueError as exc:
        self.trace.append(
            replace(
                event,
                status="rejected",
                metadata={
                    **event.metadata,
                    "certificate_valid": False,
                    "error": str(exc),
                },
            )
        )
        raise ValueError(
            f"relation {node.relation} rejected its certificate: {exc}"
        ) from exc
    self.trace.append(
        replace(event, metadata={**event.metadata, "certificate_valid": True})
    )


def _match_relation_type(
    pattern: CoreType,
    actual: CoreType,
    type_parameters: tuple[str, ...],
    substitutions: dict[str, CoreType],
) -> None:
    if pattern.name in type_parameters and not pattern.arguments:
        substitutions.setdefault(pattern.name, actual)
        return
    if pattern.name == actual.name and len(pattern.arguments) == len(actual.arguments):
        for expected_argument, actual_argument in zip(
            pattern.arguments, actual.arguments, strict=True
        ):
            _match_relation_type(
                expected_argument, actual_argument, type_parameters, substitutions
            )


def _substitute_relation_type(
    type_: CoreType, substitutions: dict[str, CoreType]
) -> CoreType:
    return substitute_type(type_, substitutions)
