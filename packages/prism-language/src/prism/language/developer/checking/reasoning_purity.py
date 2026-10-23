# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Semantic operational dependencies in abstract reasoning values."""

from dataclasses import replace

from prism.language.core import CallableContract, CoreType, substitute_type

from ..syntax.ast import CallExpr, FieldExpr, FunctionDecl, NameExpr
from .helpers import _expression_name, _expression_values

OPERATIONAL_TYPES = {
    "Model",
    "Connection",
    "Source",
    "GraphSource",
    "Resource",
    "ModelGenerate",
    "ToolCall",
    "ContextDisclose",
    "DataRead",
    "FileRead",
    "ClockRead",
    "MCPCall",
    "NetworkRequest",
    "ProcessRun",
    "PythonCall",
    "Skill",
    "Skills",
    "Tool",
    "Tools",
    "Hooks",
    "Workflow",
    "MaterialPolicy",
    "Validator",
}


def audit_structural_helpers(checker):
    for declaration in checker.program.declarations:
        if isinstance(declaration, FunctionDecl):
            error = _helper_error(checker, declaration.name, frozenset())
            checker.callables[declaration.name] = replace(
                checker.callables[declaration.name], structural_error=error
            )
    for name, span in checker.structural_helpers.items():
        error = _helper_error(checker, name, frozenset())
        if error is not None:
            checker.fail(
                f"structural helper `{name}` is not pure structure: {error}",
                span,
                "type-reasoning-structural-helper",
            )


def _helper_error(checker, name, seen):
    contract = checker.callables.get(name)
    if contract is None:
        return "calls an unresolved or dynamic operation"
    binding = checker.scope.snapshot().get(name)
    declaration = binding.value if binding is not None else None
    if contract.structural_error != "not audited":
        return (
            contract.structural_error
            if isinstance(declaration, FunctionDecl)
            else "does not denote its audited function body"
        )
    if name in seen:
        return None
    dependency = operational_dependency(checker, contract.type)
    if dependency is not None:
        return f"depends on {dependency}"
    if isinstance(declaration, CallableContract):
        return (
            None
            if name in {"length", "compute", "map_evidence", "combine_evidence", "Ok"}
            else f"uses operation {name}"
        )
    if (
        not isinstance(declaration, FunctionDecl)
        or declaration.is_proposition_declaration
    ):
        return "does not denote a structural function body"
    return _helper_body_error(checker, declaration, seen | {name})


def _helper_body_error(checker, declaration, seen):
    for expression in _expression_values(declaration):
        type_ = checker.expression_types.get(id(expression))
        dependency = (
            operational_dependency(checker, type_) if type_ is not None else None
        )
        if dependency is not None:
            return f"body depends on {dependency}"
        called = (
            _expression_name(expression.callee)
            if isinstance(expression, CallExpr)
            else _expression_name(expression)
            if isinstance(expression, NameExpr | FieldExpr)
            and type_ is not None
            and type_.is_function
            else None
        )
        if called in checker.records:
            continue
        if called in checker.callables:
            error = _helper_error(checker, called, seen)
            if error is not None:
                return error
        elif called is not None:
            return "uses an unresolved or dynamic callable"
    return None


def operational_dependency(checker, type_, seen=frozenset()):
    if type_.name in OPERATIONAL_TYPES:
        return type_.name
    if type_.effects:
        return "effectful callable"
    if _fallible_callable(type_):
        return "fallible callable"
    for child in _type_children(checker, type_, seen):
        found = operational_dependency(checker, child, seen | {type_.name})
        if found is not None:
            return found
    return None


def _fallible_callable(type_):
    result = type_.result
    return (
        type_.is_function
        and result is not None
        and result.name == "Result"
        and len(result.arguments) == 2
        and result.arguments[1].name != "Never"
    )


def _type_children(checker, type_, seen):
    yield from type_.arguments
    yield from (item for _, item in type_.parameters)
    if type_.result is not None:
        yield type_.result
    if type_.name in seen:
        return
    alias = checker.aliases.get(type_.name)
    if alias is not None:
        substitutions = dict(
            zip(
                checker.type_parameters.get(type_.name, ()),
                type_.arguments,
                strict=True,
            )
        )
        yield substitute_type(alias, substitutions)
    record = checker.records.get(type_.name)
    if record is not None:
        substitutions = dict(zip(record.type_parameters, type_.arguments, strict=True))
        yield from (
            substitute_type(field.type, substitutions) for field in record.fields
        )
    yield from (
        CoreType(name, type_.arguments) for name in checker.variants.get(type_.name, ())
    )
