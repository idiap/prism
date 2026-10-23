# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
# SPDX-License-Identifier: MIT

"""Runtime dataflow sidecars; user values and ordinary equality stay unchanged."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

from prism.language.core import (
    ComputedValue,
    DependentPair,
    Err,
    GeneratedValue,
    Ok,
    ProductionActivity,
    ProvenanceGraph,
    RecordValue,
    ValidatedValue,
    ValueReference,
)
from prism.language.evidence import Assessment, Evidence, PolicyDecision, Supported
from prism.language.kernel import CheckedTerm
from prism.language.verification import ProofSyntax, RawProofTerm

from .values import ClaimValue


class ValueEnvironment(dict):
    def __init__(self, *sources):
        super().__init__()
        self.references: dict[str, str] = {}
        for source in sources:
            self.update(source)

    def __setitem__(self, name, value):
        super().__setitem__(name, value)
        self.references.pop(name, None)

    def update(self, source=(), **named):
        values = dict(source, **named)
        for name in values:
            self.references.pop(name, None)
        super().update(values)
        self.references.update(getattr(source, "references", {}))

    def copy(self):
        return ValueEnvironment(self)

    def bind(self, name, value, reference):
        self[name] = value
        if reference is not None:
            self.references[name] = reference


@dataclass
class CallReferences:
    positional: tuple[str, ...] = ()
    named: dict[str, str] = field(default_factory=dict)
    function_result: str | None = None
    result_reference: str | None = None
    implementation: Any = None

    @property
    def inputs(self):
        return (*self.positional, *self.named.values())


class ProvenanceTracker:
    def __init__(self, store):
        self.store = store
        self.activities: dict[str, ProductionActivity] = {}
        self.values: dict[str, ValueReference] = {}
        self.last: str | None = None
        self.last_invocation: (
            tuple[tuple[Any, ...], Mapping[str, Any], CallReferences] | None
        ) = None
        self.calls: list[CallReferences] = []
        self.controls: list[str] = []
        self.evaluations: list[list[tuple[Any, str]]] = []

    @property
    def current_call(self) -> CallReferences | None:
        return self.calls[-1] if self.calls else None

    def record(
        self,
        value,
        kind,
        operation,
        inputs=(),
        *,
        children=None,
        entries=None,
        **metadata,
    ):
        activity_id = f"activity:{len(self.activities) + 1}"
        self.activities[activity_id] = ProductionActivity(
            activity_id,
            kind,
            operation,
            tuple(dict.fromkeys(item for item in inputs if item is not None)),
            **metadata,
        )
        self.last = self._value_tree(value, activity_id, children, entries)
        return self.last

    def _value_tree(self, value, activity, children=None, entries=None):
        if children is None:
            children = {
                name: self._value_tree(child, activity)
                for name, child in _children(value)
            }
        if isinstance(value, dict) and entries is None:
            entries = tuple(
                (self._value_tree(key, activity), children[str(key)]) for key in value
            )
        identity = f"value:{len(self.values) + 1}"
        self.values[identity] = ValueReference(
            identity,
            activity,
            tuple(children.items()),
            self.store.put(value).digest if _is_data(value) else None,
            entries=entries or (),
        )
        return identity

    def binding_reference(self, name, value, environment):
        existing = getattr(environment, "references", {}).get(name)
        if existing is not None:
            return existing
        reference = self.record(value, "supplied", f"binding:{name}")
        if isinstance(environment, ValueEnvironment) and name in environment:
            environment.references[name] = reference
        return reference

    def project(self, reference, name, value):
        if reference is None:
            return self.record(value, "external_unknown", "untracked projection")
        selected = dict(self.values[reference].children).get(str(name))
        if selected is None:
            return self.record(value, "computed", f"projection:{name}", (reference,))
        self.last = selected
        return selected

    def select(self, reference, dependencies):
        dependencies = tuple(
            dict.fromkeys(item for item in dependencies if item is not None)
        )
        if not dependencies:
            self.last = reference
            return reference
        selected = self.values[reference]
        children = tuple(
            (name, self.select(child, dependencies))
            for name, child in selected.children
        )
        entries = tuple(
            (self.select(key, dependencies), self.select(value, dependencies))
            for key, value in selected.entries
        )
        identity = f"value:{len(self.values) + 1}"
        self.values[identity] = ValueReference(
            identity,
            selected.activity,
            children,
            selected.artifact,
            tuple(dict.fromkeys((reference, *dependencies))),
            entries,
        )
        self.last = identity
        return identity

    def produce(self, value, kind, operation, **metadata):
        context = self.current_call
        inputs = list(context.inputs) if context is not None else []
        if context is not None and context.function_result is not None:
            inputs.append(context.function_result)
        if self.evaluations:
            inputs.extend(reference for _, reference in self.evaluations[-1])
        reference = self.record(value, kind, operation, inputs, **metadata)
        if context is not None:
            context.result_reference = reference
        return reference

    def snapshot(self):
        return ProvenanceGraph(
            tuple(self.activities.values()), tuple(self.values.values()), self.last
        )


def _children(value):
    if isinstance(value, RecordValue):
        return tuple(value.fields.items())
    if isinstance(
        value,
        GeneratedValue | ComputedValue | ValidatedValue | Evidence | DependentPair | Ok,
    ):
        return (("value", value.value),)
    if isinstance(value, Err):
        return (("error", value.error),)
    if isinstance(value, list | tuple | set | frozenset):
        return tuple((str(index), item) for index, item in enumerate(value))
    if isinstance(value, dict):
        return tuple((str(key), item) for key, item in value.items())
    return ()


def finish_evaluation(tracker, expression, value, environment, children):
    from prism.language.effects import (
        CallExpression,
        Conditional,
        Execute,
        Field,
        Index,
        ListValue,
        Literal,
        MapValue,
        Reference,
        Solve,
        Try,
        TupleValue,
    )
    from prism.language.evidence import MaterialInference

    references = tuple(reference for _, reference in children)
    if isinstance(expression, Reference):
        return tracker.binding_reference(expression.name, value, environment)
    if isinstance(expression, Field):
        return tracker.project(references[0], expression.name, value)
    if isinstance(expression, Index):
        return tracker.select(
            tracker.project(references[0], children[1][0], value), (references[1],)
        )
    if isinstance(expression, Try):
        return tracker.project(references[0], "value", value)
    if isinstance(expression, CallExpression | Solve | Execute | MaterialInference):
        return tracker.last or tracker.record(
            value, "external_unknown", "untracked invocation", references
        )
    if isinstance(expression, Conditional):
        return tracker.select(references[-1], references[:-1])
    if isinstance(expression, ListValue | TupleValue):
        fields = {str(index): reference for index, reference in enumerate(references)}
        return tracker.record(
            value, "computed", "collection assembly", references, children=fields
        )
    if isinstance(expression, MapValue):
        fields = {
            str(children[index][0]): references[index + 1]
            for index in range(0, len(children), 2)
        }
        return tracker.record(
            value,
            "computed",
            "map assembly",
            references,
            children=fields,
            entries=tuple(zip(references[::2], references[1::2], strict=True)),
        )
    return tracker.record(
        value,
        "literal" if isinstance(expression, Literal) else "computed",
        getattr(expression, "operator", type(expression).__name__),
        references,
    )


def _is_data(value):
    return value is None or isinstance(
        value,
        (
            str,
            int,
            float,
            Decimal,
            bool,
            bytes,
            RecordValue,
            GeneratedValue,
            ComputedValue,
            ValidatedValue,
            Evidence,
            Assessment,
            Supported,
            PolicyDecision,
            ClaimValue,
            CheckedTerm,
            ProofSyntax,
            RawProofTerm,
            DependentPair,
            Ok,
            Err,
            list,
            tuple,
            dict,
        ),
    )
