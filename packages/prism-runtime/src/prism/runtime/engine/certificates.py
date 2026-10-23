# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Check relation certificates against resolved claims and actual endpoint values."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256

from prism.language.core import (
    ComputedValue,
    CoreType,
    DependentPair,
    GeneratedValue,
    RecordValue,
    ValidatedValue,
    substitute_type,
)
from prism.language.developer import reify_runtime_value
from prism.language.evidence import Assessment, Evidence, Supported
from prism.language.kernel import CheckedTerm, Const, Context, apps, is_def_eq

from .expressions import _binary
from .values import ClaimValue, _Callable, _RecordFactory


def _index_value(engine, index, bindings):
    if index.kind == "literal":
        return ast.literal_eval(index.symbol)
    if index.kind == "reference":
        return _binding_value(engine, index.symbol, bindings)
    children = tuple(_index_value(engine, child, bindings) for child in index.children)
    if index.kind == "field":
        return engine._field(children[0], index.symbol)
    if index.kind == "index":
        return children[0][children[1]]
    if index.kind == "binary":
        return _binary(index.symbol, *children)
    if index.kind == "apply":
        callee, *arguments = children
        if isinstance(callee, _RecordFactory):
            return RecordValue(
                callee.definition.name,
                dict(
                    zip(
                        (name for name, _ in callee.definition.fields),
                        arguments,
                        strict=True,
                    )
                ),
            )
        return engine._call(
            callee,
            tuple(arguments),
            {},
            engine.global_env,
            CoreType("Proposition", proposition=index),
        )
    raise ValueError(f"unsupported certificate claim expression {index.kind}")


def _binding_value(engine, identity, bindings):
    if identity in bindings:
        return bindings[identity]
    for name, candidate in engine.program.binding_identities.items():
        if candidate == identity and name in engine.global_env:
            return engine.global_env[name]
    raise ValueError(f"unbound certificate claim identity {identity}")


def _native_claim(engine, index, bindings):
    if index is None or index.kind != "apply":
        raise ValueError("relation proof requires a resolved native proposition")
    symbol = index.children[0].symbol
    engine.kernel.environment.get(symbol)
    arguments = []
    for child in index.children[1:]:
        if child.type is None:
            raise ValueError("relation proof argument has no checked type")
        arguments.append(
            reify_runtime_value(_index_value(engine, child, bindings), child.type.name)
        )
    return apps(Const(symbol), *arguments)


def _check_proof(engine, value, proposition, bindings):
    if not isinstance(value, CheckedTerm):
        raise ValueError("relation certificate requires a kernel-checked Proof")
    proof = engine.kernel.recheck(value)
    expected = _native_claim(engine, proposition.proposition, bindings)
    if not is_def_eq(engine.kernel.environment, Context(), expected, proof.type):
        raise ValueError(
            "relation proof certifies different endpoints or a different claim"
        )


def _check_supported(engine, value, expected, bindings):
    if not isinstance(value, Supported) or value.assessment.disposition != "accepted":
        raise ValueError("relation certificate requires accepted material support")
    claim = _index_value(engine, expected.arguments[0].proposition, bindings)
    if not isinstance(claim, ClaimValue) or value.assessment.claim != claim:
        raise ValueError(
            "relation support certifies different endpoints or a different claim"
        )


def _check_assessment(engine, value, expected, bindings):
    if not isinstance(value, Assessment):
        raise ValueError("occurrence contract requires a completed Assessment")
    claim = _index_value(engine, expected.arguments[0].proposition, bindings)
    if not isinstance(claim, ClaimValue) or value.claim != claim:
        raise ValueError("occurrence assessment concerns a different claim")


def _check_validated(engine, value, expected, bindings):
    if not isinstance(value, ValidatedValue) or value.result is not True:
        raise ValueError("relation certificate requires an accepted validation")
    binder, proposition = expected.arguments
    local = {**bindings, binder.binding_identity: value.value}
    _check_certificate(engine, value.value, binder.arguments[0], local)
    if value.claim != _index_value(engine, proposition.proposition, local):
        raise ValueError("relation validation certifies a different claim")
    validator = next(
        (
            item
            for item in engine.global_env.values()
            if isinstance(item, _Callable)
            and item.definition.identity == value.validator
            and sha256(repr(item.definition).encode()).hexdigest()
            == value.validator_hash
        ),
        None,
    )
    if validator is None:
        raise ValueError("relation validation has an unknown validator identity")
    if _recheck_validator(engine, validator, value.value) is not True:
        raise ValueError("relation validator rejected the certificate value")


def _recheck_validator(engine, validator, value):
    start = len(engine.trace)
    try:
        return engine._call(validator, (value,), {}, engine.global_env)
    finally:
        for index in range(start, len(engine.trace)):
            event = engine.trace[index]
            engine.trace[index] = replace(
                event, metadata={**event.metadata, "phase": "assurance-recheck"}
            )


def _check_verified(engine, value, expected, bindings):
    if not isinstance(value, DependentPair):
        raise ValueError("relation certificate requires a verified pair")
    binder, proposition = expected.arguments
    local = {**bindings, binder.binding_identity: value.value}
    value_type = binder.arguments[0] if binder.binder is not None else binder
    _check_certificate(engine, value.value, value_type, local)
    return _check_proof(engine, value.proof, proposition, local)


def _check_certificate(engine, value, expected, bindings):
    if expected.name == "Proof":
        return _check_proof(engine, value, expected.arguments[0], bindings)
    assurance = {
        "Assessment": _check_assessment,
        "Supported": _check_supported,
        "Validated": _check_validated,
        "Verified": _check_verified,
    }.get(expected.name)
    if assurance is not None:
        return assurance(engine, value, expected, bindings)
    wrapper = {
        "Computed": ComputedValue,
        "Generated": GeneratedValue,
        "Evidence": Evidence,
    }.get(expected.name)
    if wrapper is not None:
        if not isinstance(value, wrapper):
            raise ValueError(
                "relation certificate has the wrong provenance representation"
            )
        return _check_certificate(engine, value.value, expected.arguments[0], bindings)
    if isinstance(value, RecordValue):
        return _check_record_certificate(engine, value, expected, bindings)
    if expected.name in {"List", "Set", "Tuple", "Map"}:
        return _check_collection_certificate(engine, value, expected, bindings)
    scalar = {
        "Nat": int,
        "Int": int,
        "Bool": bool,
        "String": str,
        "Bytes": bytes,
        "Float": float,
        "Unit": type(None),
    }.get(expected.name)
    if (
        scalar is None
        or type(value) is not scalar
        or (expected.name == "Nat" and value < 0)
    ):
        raise ValueError(
            f"invalid runtime certificate representation for {expected.render()}"
        )


def _check_collection_certificate(engine, value, expected, bindings):
    if expected.name == "Map":
        if not isinstance(value, Mapping):
            raise ValueError("relation certificate map is malformed")
        for key, item in value.items():
            _check_certificate(engine, key, expected.arguments[0], bindings)
            _check_certificate(engine, item, expected.arguments[1], bindings)
        return
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError("relation certificate collection is malformed")
    types = (
        expected.arguments
        if expected.name == "Tuple"
        else expected.arguments * len(value)
    )
    if len(types) != len(value):
        raise ValueError("relation certificate collection has the wrong arity")
    for item, type_ in zip(value, types, strict=True):
        _check_certificate(engine, item, type_, bindings)


def _check_record_certificate(engine, value, expected, bindings):
    name = (
        value.type_name if expected.name in engine.program.variants else expected.name
    )
    factory = engine.global_env.get(name)
    actual = engine.global_env.get(value.type_name)
    if (
        not isinstance(factory, _RecordFactory)
        or not isinstance(actual, _RecordFactory)
        or (factory.definition.identity or factory.definition.name)
        != (actual.definition.identity or actual.definition.name)
    ):
        raise ValueError(
            f"relation certificate has the wrong record representation: "
            f"expected {expected.render()}, received {value.type_name}"
        )
    if (
        expected.name in engine.program.variants
        and value.type_name not in engine.program.variants[expected.name]
    ):
        raise ValueError("relation certificate has the wrong variant")
    definition = factory.definition
    if set(value.fields) != {name for name, _ in definition.fields}:
        raise ValueError(
            "relation certificate is missing required fields or has extra fields"
        )
    substitutions = dict(
        zip(definition.type_parameters, expected.arguments, strict=True)
    )
    local = {
        **bindings,
        **{
            identity: value.fields[name]
            for (name, _), identity in zip(
                definition.fields, definition.field_bindings, strict=True
            )
        },
    }
    for name, type_ in definition.fields:
        _check_certificate(
            engine, value.fields[name], substitute_type(type_, substitutions), local
        )
