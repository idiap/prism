# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Normalize checked high-level occurrences for execution and inspection."""

from dataclasses import replace

from prism.language.core import CoreType
from prism.language.core.occurrences import (
    OccurrenceContract,
    ReasoningClassification,
    RelationContract,
    value_requirements,
)

from ..syntax.ast import CallExpr, ReasoningDecl, WorkflowDecl
from .helpers import _composition_nodes, _expression_name, _implementation_shape


def occurrence_contracts(checker):
    result = dict(checker.occurrence_contracts)
    for declaration in checker.program.declarations:
        if not isinstance(declaration, (ReasoningDecl, WorkflowDecl)):
            continue
        owner = checker.scope.resolve(declaration.name).identity
        for node in _composition_nodes(declaration.composition):
            component = node.component
            callee = component.callee if isinstance(component, CallExpr) else component
            method = checker.expression_types.get(id(callee))
            expression_type = checker.expression_types[id(component)]
            callable_type = (
                CoreType("Function", result=expression_type)
                if isinstance(component, CallExpr)
                else expression_type
            )
            output = _implementation_shape(callable_type)[0]
            assert output is not None
            input_type = _input_type(checker, declaration, component, method)
            name = _expression_name(callee)
            binding = checker.scope.snapshot().get(name)
            method_identity = (
                method.binding_identity
                if method is not None and method.binding_identity is not None
                else binding.identity
                if binding is not None
                else f"{owner}::parameter:{name}"
            )
            identity = (
                f"{owner}::occurrence:{node.alias}:{node.span.line}:{node.span.column}"
            )
            kind = (
                "method"
                if isinstance(declaration, ReasoningDecl)
                and name in checker.aliases
                and checker.aliases[name].is_function
                else "structural"
                if isinstance(declaration, ReasoningDecl)
                else "workflow"
            )
            contract = OccurrenceContract(
                identity,
                owner,
                method_identity,
                checker.method_classifications.get(
                    method_identity,
                    ReasoningClassification(archetype_state="not_applicable")
                    if kind == "structural"
                    else ReasoningClassification(),
                ),
                input_type,
                output,
                value_requirements(output, checker.records, variants=checker.variants),
                _relation_contract(checker, node),
                value_requirements(
                    input_type, checker.records, variants=checker.variants
                ),
                execution_kind=kind,
            )
            result[id(node)] = _constrain_occurrence(checker, node, contract)
    return result


def _constrain_occurrence(checker, node, contract):
    seen = set()
    for constraint in node.constraints:
        key = (constraint.subject, constraint.path, constraint.dimension)
        if key in seen:
            checker.fail(
                "duplicate occurrence constraint",
                constraint.span,
                "type-occurrence-constraint",
            )
        seen.add(key)
        field = (
            "requirements" if constraint.subject == "output" else "input_requirements"
        )
        requirements = getattr(contract, field)
        if not any(item.path == constraint.path for item in requirements):
            checker.fail(
                "unknown occurrence constraint path",
                constraint.span,
                "type-occurrence-constraint",
            )
        allowed = constraint.allowed
        origins = {
            "literal",
            "supplied",
            "asserted",
            "acquired",
            "generated",
            "computed",
            "external_unknown",
            "unconstrained",
        }
        if (
            len(set(allowed)) != len(allowed)
            or not set(allowed).issubset(origins)
            or ("unconstrained" in allowed and len(allowed) != 1)
        ):
            checker.fail(
                "invalid occurrence origins",
                constraint.span,
                "type-occurrence-constraint",
            )
        requirements = tuple(
            _constrained_requirement(checker, item, constraint)
            if item.path == constraint.path
            else item
            for item in requirements
        )
        contract = replace(contract, **{field: requirements})
    return contract


def _constrained_requirement(checker, requirement, constraint):
    previous = getattr(requirement.origin, constraint.dimension)
    allowed = constraint.allowed
    if previous != ("unconstrained",):
        allowed = (
            previous
            if allowed == ("unconstrained",)
            else tuple(item for item in allowed if item in previous)
        )
    if not allowed:
        checker.fail(
            "occurrence origin contradicts its value type",
            constraint.span,
            "type-occurrence-constraint",
        )
    return replace(
        requirement,
        origin=replace(requirement.origin, **{constraint.dimension: allowed}),
    )


def _relation_contract(checker, node):
    if node.relation is None:
        return None
    relation = checker.expression_types[id(node)]
    _, source, target, certificate = relation.arguments
    return RelationContract(
        checker.scope.resolve(node.relation).identity,
        source,
        target,
        certificate,
        value_requirements(certificate, checker.records, variants=checker.variants),
    )


def _input_type(checker, declaration, component, method):
    if isinstance(component, CallExpr) and not isinstance(declaration, ReasoningDecl):
        inputs = tuple(
            checker.expression_types[id(argument.value)]
            for argument in component.arguments
        )
    else:
        inputs = (
            tuple(type_ for _, type_ in method.parameters) if method is not None else ()
        )
    if not inputs:
        return CoreType("Unit")
    return inputs[0] if len(inputs) == 1 else CoreType("Tuple", inputs)
