# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Admission of definitions, theorems, axioms, and exact core modules."""

from __future__ import annotations

from collections.abc import Sequence

from .context import EMPTY_CONTEXT, Context
from .diagnostics import KernelError
from .environment import CheckedModule, Declaration, Environment, ModuleImport
from .reduction import whnf
from .terms import (
    Const,
    InductiveRef,
    Pi,
    Sort,
    constants,
    unfold_apps,
    universe_variables,
)
from .typing import check, infer


def check_declaration(
    environment: Environment, declaration: Declaration
) -> Environment:
    if not declaration.pure:
        raise KernelError(
            f"proof declaration `{declaration.name}` is effectful",
            code="kernel-effectful-declaration",
        )
    if not declaration.total:
        raise KernelError(
            f"proof declaration `{declaration.name}` is not total",
            code="kernel-partial-declaration",
        )
    _validate_universe_parameters(declaration)
    _require_type(environment, declaration.type)
    if declaration.kind == "constructor":
        _validate_constructor(environment, declaration)
    elif declaration.kind == "recursor":
        _validate_recursor(environment, declaration)
    dependencies = _declaration_axioms(environment, declaration)
    if declaration.value is not None:
        check(environment, EMPTY_CONTEXT, declaration.value, declaration.type)
    admitted = Declaration(
        declaration.name,
        declaration.type,
        declaration.value,
        declaration.kind,
        declaration.universe_parameters,
        declaration.transparent,
        declaration.pure,
        declaration.total,
        declaration.inductive_name,
        declaration.recursor,
        dependencies,
    )
    return environment.extend(admitted)


def check_module(
    name: str,
    imports: Sequence[CheckedModule],
    declarations: Sequence[Declaration],
    *,
    expected_imports: Sequence[ModuleImport] | None = None,
) -> CheckedModule:
    if expected_imports is not None:
        supplied = {item.name: item.content_hash for item in imports}
        expected = {item.name: item.content_hash for item in expected_imports}
        if supplied != expected:
            raise KernelError(
                "module imports do not match their exact content hashes",
                code="kernel-import-hash-mismatch",
            )
    environment = Environment()
    module_hashes: list[tuple[str, str]] = []
    for imported in imports:
        if imported.name in {item[0] for item in module_hashes}:
            raise KernelError(
                f"duplicate module import `{imported.name}`",
                code="kernel-duplicate-import",
            )
        module_hashes.append((imported.name, imported.content_hash))
        for declaration in imported.declarations:
            if environment.contains(declaration.name):
                raise KernelError(
                    f"duplicate imported declaration `{declaration.name}`",
                    code="kernel-duplicate-declaration",
                )
            environment = environment.extend(declaration)
    environment = Environment(
        environment.declarations,
        tuple(sorted(module_hashes)),
        environment.calculus_version,
    )
    admitted: list[Declaration] = []
    axiom_map: dict[str, frozenset[str]] = {}
    for declaration in declarations:
        environment = check_declaration(environment, declaration)
        checked = environment.get(declaration.name)
        admitted.append(checked)
        axiom_map[checked.name] = checked.axiom_dependencies | (
            frozenset({checked.name}) if checked.kind == "axiom" else frozenset()
        )
    import_refs = tuple(
        ModuleImport(item.name, item.content_hash)
        for item in sorted(imports, key=lambda module: module.name)
    )
    from .serialization import module_hash

    content_hash = module_hash(name, import_refs, tuple(admitted))
    return CheckedModule(
        name,
        import_refs,
        tuple(admitted),
        environment,
        content_hash,
        axiom_dependencies=axiom_map,
    )


def _declaration_axioms(
    environment: Environment, declaration: Declaration
) -> frozenset[str]:
    referenced = set(constants(declaration.type))
    if declaration.value is not None:
        referenced.update(constants(declaration.value))
    dependencies: set[str] = set()
    for name in referenced:
        item = environment.get(name)
        if item.kind == "axiom":
            dependencies.add(name)
        dependencies.update(item.axiom_dependencies)
    return frozenset(dependencies)


def _require_type(environment: Environment, term) -> Sort:
    inferred = whnf(environment, EMPTY_CONTEXT, infer(environment, EMPTY_CONTEXT, term))
    if not isinstance(inferred, Sort):
        raise KernelError(
            "declaration type is not itself a type",
            code="kernel-expected-sort",
        )
    return inferred


def _validate_universe_parameters(declaration: Declaration) -> None:
    parameters = declaration.universe_parameters
    if len(parameters) != len(set(parameters)):
        raise KernelError(
            f"declaration `{declaration.name}` repeats a universe parameter",
            code="kernel-universe-parameter",
        )
    declared = frozenset(parameters)
    used = universe_variables(declaration.type)
    if declaration.value is not None:
        used |= universe_variables(declaration.value)
    unknown = used - declared
    if unknown:
        raise KernelError(
            f"declaration `{declaration.name}` uses undeclared universe variables: "
            + ", ".join(sorted(unknown)),
            code="kernel-universe-variable",
        )


def _validate_constructor(environment: Environment, declaration: Declaration) -> None:
    owner = environment.get(declaration.inductive_name or "")
    if owner.kind != "inductive":
        raise KernelError(
            f"constructor `{declaration.name}` owner is not an inductive family",
            code="kernel-inductive-owner",
        )
    result = declaration.type
    while isinstance(result, Pi):
        result = result.codomain
    head, arguments = unfold_apps(result)
    if isinstance(head, InductiveRef):
        arguments = (*head.arguments, *arguments)
    if not (
        isinstance(head, InductiveRef | Const)
        and head.name == declaration.inductive_name
    ):
        raise KernelError(
            f"constructor `{declaration.name}` does not return `{declaration.inductive_name}`",
            code="kernel-constructor-result",
        )
    family_arity = _pi_arity(owner.type)
    if len(arguments) != family_arity:
        raise KernelError(
            f"constructor `{declaration.name}` returns its family with "
            f"{len(arguments)} arguments, expected {family_arity}",
            code="kernel-constructor-result-arity",
        )


def _validate_recursor(environment: Environment, declaration: Declaration) -> None:
    owner = environment.get(declaration.inductive_name or "")
    if owner.kind != "inductive":
        raise KernelError(
            f"recursor `{declaration.name}` owner is not an inductive family",
            code="kernel-inductive-owner",
        )
    spec = declaration.recursor
    if spec is None:
        raise KernelError(
            f"recursor `{declaration.name}` requires reduction metadata",
            code="kernel-recursor-metadata",
        )
    recursor_arity = _pi_arity(declaration.type)
    if not 0 <= spec.scrutinee_index < recursor_arity:
        raise KernelError(
            f"recursor `{declaration.name}` has an invalid scrutinee position",
            code="kernel-recursor-metadata",
        )
    rules = {rule.constructor: rule for rule in spec.rules}
    if len(rules) != len(spec.rules):
        raise KernelError(
            f"recursor `{declaration.name}` repeats a constructor rule",
            code="kernel-recursor-metadata",
        )
    constructors = {
        item.name: item
        for item in environment.declarations
        if item.kind == "constructor"
        and item.inductive_name == declaration.inductive_name
    }
    if set(rules) != set(constructors):
        raise KernelError(
            f"recursor `{declaration.name}` rules do not cover its constructors",
            code="kernel-recursor-coverage",
        )
    for constructor_name, rule in rules.items():
        if not 0 <= rule.method_index < recursor_arity:
            raise KernelError(
                f"recursor `{declaration.name}` has an invalid method position",
                code="kernel-recursor-metadata",
            )
        constructor_domains = _pi_domains(constructors[constructor_name].type)
        constructor_arity = len(constructor_domains)
        if rule.constructor_arity != constructor_arity:
            raise KernelError(
                f"recursor rule for `{constructor_name}` has arity "
                f"{rule.constructor_arity}, expected {constructor_arity}",
                code="kernel-recursor-metadata",
            )
        positions = (
            *rule.recursive_positions,
            *(rule.field_positions or ()),
        )
        if any(position < 0 or position >= constructor_arity for position in positions):
            raise KernelError(
                f"recursor rule for `{constructor_name}` has an invalid field position",
                code="kernel-recursor-metadata",
            )
        for position in rule.recursive_positions:
            head, _ = unfold_apps(constructor_domains[position])
            if not (
                isinstance(head, InductiveRef | Const)
                and head.name == declaration.inductive_name
            ):
                raise KernelError(
                    f"recursor rule for `{constructor_name}` marks a non-recursive field",
                    code="kernel-recursor-metadata",
                )

    family_result = owner.type
    while isinstance(family_result, Pi):
        family_result = family_result.codomain
    if isinstance(family_result, Sort) and family_result.level is None:
        result_sort = _telescope_result_sort(environment, declaration.type)
        if result_sort.level is not None:
            raise KernelError(
                f"recursor `{declaration.name}` eliminates Prop into data",
                code="kernel-prop-elimination",
            )


def _pi_arity(term) -> int:
    arity = 0
    while isinstance(term, Pi):
        arity += 1
        term = term.codomain
    return arity


def _pi_domains(term) -> tuple:
    domains = []
    while isinstance(term, Pi):
        domains.append(term.domain)
        term = term.codomain
    return tuple(domains)


def _telescope_result_sort(environment: Environment, term) -> Sort:
    context = Context()
    while isinstance(term, Pi):
        context = context.push(term.name, term.domain)
        term = term.codomain
    inferred = whnf(environment, context, infer(environment, context, term))
    if not isinstance(inferred, Sort):
        raise KernelError(
            "recursor result is not a type",
            code="kernel-recursor-type",
        )
    return inferred
