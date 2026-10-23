# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Enforce normalized requirements against actual values and production records."""

from decimal import Decimal

from prism.language.core import ComputedValue, GeneratedValue, RecordValue
from prism.language.evidence import Evidence

from .certificates import _check_certificate
from .provenance import _children
from .values import _RecordFactory


def check_requirements(engine, requirements, value, reference, *, check_assurance=True):
    for requirement in requirements:
        for actual, ref, bindings in _at_path(
            engine, value, reference, requirement.path, {}
        ):
            _check_shape(engine, actual, requirement.type)
            _check_origin(engine.provenance, ref, requirement.origin)
            if check_assurance and (
                requirement.assurance.kind != "unchecked"
                or requirement.type.name == "Assessment"
            ):
                _check_certificate(engine, actual, requirement.type, bindings)


def _same_record(engine, actual, expected):
    left = engine.global_env.get(actual)
    right = engine.global_env.get(expected)
    return (
        isinstance(left, _RecordFactory)
        and isinstance(right, _RecordFactory)
        and (left.definition.identity or left.definition.name)
        == (right.definition.identity or right.definition.name)
    )


def _check_shape(engine, value, expected):
    _check_representation(value, expected)
    containers = {"List": list, "Set": (set, frozenset), "Tuple": tuple, "Map": dict}
    representation = containers.get(expected.name)
    if representation is not None and not isinstance(value, representation):
        raise ValueError(f"occurrence contract requires {expected.name}")
    if expected.name == "Tuple" and len(value) != len(expected.arguments):
        raise ValueError("occurrence tuple has the wrong arity")
    variants = engine.program.variants.get(expected.name)
    if variants is not None:
        if not isinstance(value, RecordValue) or not any(
            _same_record(engine, value.type_name, member) for member in variants
        ):
            raise ValueError("occurrence contract has an invalid variant")
    elif expected.name in engine.program.record_contracts:
        _check_record_shape(engine, value, expected)


def _check_representation(value, expected):
    representations = {
        "Int": (int,),
        "Nat": (int,),
        "Float": (float, int),
        "Decimal": (Decimal,),
        "Bool": (bool,),
        "String": (str,),
        "Char": (str,),
        "Bytes": (bytes,),
        "Unit": (type(None),),
        "Generated": (GeneratedValue,),
        "Computed": (ComputedValue,),
        "Evidence": (Evidence,),
    }
    permitted = representations.get(expected.name)
    if permitted is not None and type(value) not in permitted:
        raise ValueError(f"occurrence contract requires {expected.render()}")
    if expected.name == "Nat" and value < 0:
        raise ValueError("occurrence Nat value must be nonnegative")
    if expected.name == "Char" and len(value) != 1:
        raise ValueError("occurrence Char value must contain one character")


def _check_record_shape(engine, value, expected):
    if not isinstance(value, RecordValue) or not _same_record(
        engine, value.type_name, expected.name
    ):
        raise ValueError("occurrence contract has an invalid record")
    fields = {
        field.name for field in engine.program.record_contracts[expected.name].fields
    }
    if set(value.fields) != fields:
        raise ValueError("occurrence record has missing or extra fields")


def _record_bindings(engine, value, bindings):
    if not isinstance(value, RecordValue):
        return bindings
    factory = engine.global_env.get(value.type_name)
    if not isinstance(factory, _RecordFactory):
        return bindings
    return {
        **bindings,
        **{
            identity: value.fields[name]
            for (name, _), identity in zip(
                factory.definition.fields,
                factory.definition.field_bindings,
                strict=True,
            )
            if name in value.fields
        },
    }


def _at_path(engine, value, reference, path, bindings):
    bindings = _record_bindings(engine, value, bindings)
    if not path:
        yield value, reference, bindings
        return
    head, *tail = path
    if head == "some":
        yield from _optional_path(engine, value, reference, tail, bindings)
        return
    if head.startswith("case:"):
        if isinstance(value, RecordValue) and _same_record(
            engine, value.type_name, head[5:]
        ):
            yield from _at_path(engine, value, reference, tail, bindings)
        return
    ref = engine.provenance.values.get(reference)
    references = dict(ref.children) if ref is not None else {}
    if head in {"keys", "values"} and isinstance(value, dict):
        yield from _map_path(engine, value, ref, head, tail, bindings)
        return
    children = dict(_children(value))
    if head == "*":
        selected = children.items()
    else:
        if head not in children:
            raise ValueError(f"occurrence contract is missing required field {head!r}")
        selected = ((head, children[head]),)
    for name, child in selected:
        yield from _at_path(engine, child, references.get(name), tail, bindings)


def _optional_path(engine, value, reference, tail, bindings):
    if value is not None:
        yield from _at_path(engine, value, reference, tail, bindings)


def _map_path(engine, value, ref, head, tail, bindings):
    entries = ref.entries if ref is not None else ((None, None),) * len(value)
    for (key, item), pair in zip(value.items(), entries, strict=True):
        child = key if head == "keys" else item
        child_ref = pair[0] if head == "keys" else pair[1]
        yield from _at_path(engine, child, child_ref, tail, bindings)


def _check_origin(tracker, reference, constraint):
    if constraint.producers != ("unconstrained",):
        ref = tracker.values.get(reference)
        producer = tracker.activities[ref.activity].kind if ref else "external_unknown"
        if producer not in constraint.producers:
            raise ValueError(
                f"occurrence origin mismatch: producer {producer!r}; "
                f"permitted {constraint.producers!r}"
            )
    if constraint.ancestors != ("unconstrained",):
        actual = _ancestor_kinds(tracker, reference)
        if not actual.issubset(constraint.ancestors):
            raise ValueError(
                f"occurrence origin mismatch: ancestors {sorted(actual)!r}; "
                f"permitted {constraint.ancestors!r}"
            )


def _ancestor_kinds(tracker, reference):
    root = tracker.values.get(reference)
    producer = root.activity if root is not None else None
    pending = [reference]
    visited = set()
    kinds = set()
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        ref = tracker.values.get(current)
        if ref is None:
            kinds.add("external_unknown")
            continue
        activity = tracker.activities[ref.activity]
        if activity.identity != producer:
            kinds.add(activity.kind)
        pending.extend((*activity.inputs, *ref.dependencies))
    return kinds
