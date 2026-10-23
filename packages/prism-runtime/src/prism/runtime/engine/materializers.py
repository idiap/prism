# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Materializer signature compatibility; exact claims are checked on actual values."""

from prism.language.core import CoreType, substitute_type

from .components import _component_behavior, _component_contract_type
from .occurrences import _same_record


def check_materializer(engine, node, component):
    if node.method_type is None:
        return
    signature = _component_contract_type(component)
    if signature is None or not signature.parameters or signature.result is None:
        raise ValueError("occurrence materializer has no compatible callable signature")
    variables = getattr(component.definition, "type_parameters", ())
    substitutions = {}
    _match_shape(
        engine, signature.parameters[0][1], node.input_type, variables, substitutions
    )
    output = signature.result
    if output.name in {"Result", "Workflow"}:
        output = output.arguments[0]
    _match_shape(engine, output, node.output_type, variables, substitutions)
    failure, effects = _component_behavior(component)
    workflow = engine._workflow_definition_stack[-1]
    if not set(effects).issubset(workflow.effects):
        raise ValueError("occurrence materializer introduces undeclared effects")
    if not _accepts_failure(
        engine, workflow.failure_type, substitute_type(failure, substitutions)
    ):
        raise ValueError(
            "occurrence materializer introduces an undeclared failure type"
        )


def check_input_adapter(engine, node, adapter):
    if adapter is None:
        return
    signature = _component_contract_type(adapter)
    failure, effects = _component_behavior(adapter)
    if effects or failure.name != "Never":
        raise ValueError("occurrence input adapter must be pure and infallible")
    if signature is None or not signature.parameters or signature.result is None:
        raise ValueError(
            "occurrence input adapter has no compatible callable signature"
        )
    substitutions = {}
    variables = getattr(adapter.definition, "type_parameters", ())
    _match_shape(
        engine,
        signature.parameters[0][1],
        node.topology_input_type,
        variables,
        substitutions,
    )
    _match_shape(engine, signature.result, node.input_type, variables, substitutions)


def _match_shape(engine, actual, expected, variables, substitutions):
    if actual.name in variables and not actual.arguments:
        previous = substitutions.setdefault(actual.name, expected)
        if previous != expected:
            raise ValueError(
                "occurrence materializer has inconsistent type specialization"
            )
        return
    actual = substitute_type(actual, substitutions)
    if actual.binder is not None or expected.binder is not None:
        return _match_shape(
            engine,
            actual.arguments[0] if actual.binder is not None else actual,
            expected.arguments[0] if expected.binder is not None else expected,
            variables,
            substitutions,
        )
    if actual.proposition is not None and expected.proposition is not None:
        return  # The returned certificate must establish the exact expected index.
    if not _same_type_name(engine, actual.name, expected.name):
        raise ValueError(
            f"occurrence materializer returns or accepts {actual.render()}, expected {expected.render()}"
        )
    if len(actual.arguments) != len(expected.arguments):
        raise ValueError("occurrence materializer has incompatible type arguments")
    for left, right in zip(actual.arguments, expected.arguments, strict=True):
        _match_shape(engine, left, right, variables, substitutions)
    if actual.is_function or expected.is_function:
        _match_function(engine, actual, expected, variables, substitutions)


def _match_function(engine, actual, expected, variables, substitutions):
    if (
        len(actual.parameters) != len(expected.parameters)
        or actual.effects != expected.effects
    ):
        raise ValueError(
            "occurrence materializer has an incompatible function parameter"
        )
    for (_, left), (_, right) in zip(
        actual.parameters, expected.parameters, strict=True
    ):
        _match_shape(engine, left, right, variables, substitutions)
    _match_shape(
        engine,
        actual.result or CoreType("Unit"),
        expected.result or CoreType("Unit"),
        variables,
        substitutions,
    )


def _same_type_name(engine, actual, expected):
    return actual == expected or _same_record(engine, actual, expected)


def _accepts_failure(engine, expected, actual):
    if actual.name == "Never" or _same_type_name(engine, actual.name, expected.name):
        return True
    actual_members = engine.program.variants.get(actual.name, (actual.name,))
    expected_members = engine.program.variants.get(expected.name, (expected.name,))
    return all(
        any(_same_type_name(engine, member, allowed) for allowed in expected_members)
        for member in actual_members
    )
