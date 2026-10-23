# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Deterministic values shared by language clients and the runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from prism.language.kernel import CheckedTerm

from .types import CoreType


@dataclass(frozen=True, slots=True)
class TypedValue:
    type: CoreType
    value: Any


@dataclass(frozen=True, slots=True)
class RecordValue:
    type_name: str
    fields: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Ok:
    value: Any


@dataclass(frozen=True, slots=True)
class Err:
    error: Any


@dataclass(frozen=True, slots=True)
class GeneratedValue:
    value: Any
    producer: str


@dataclass(frozen=True, slots=True)
class ComputedValue:
    value: Any
    procedure: str


@dataclass(frozen=True, slots=True)
class ValidatedValue:
    value: Any
    validator: str
    specification: str
    result: bool
    validator_hash: str
    claim: Any = None


@dataclass(frozen=True, slots=True)
class DependentPair:
    value: Any
    proof: CheckedTerm

    @property
    def proposition_hash(self) -> str:
        return self.proof.type_hash

    @property
    def proof_hash(self) -> str:
        return self.proof.term_hash

    @property
    def environment_hash(self) -> str:
        return self.proof.environment_hash

    @property
    def axioms(self) -> frozenset[str]:
        return self.proof.axioms


@dataclass(frozen=True, slots=True)
class ExecutionValue:
    result: Any
    trace: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RefinementPolicyValue:
    max_attempts: int


@dataclass(frozen=True, slots=True)
class RefinementFeedbackValue:
    attempt: int
    max_attempts: int
    error: Any
    message: str


@dataclass(frozen=True, slots=True)
class RefinementAttemptValue:
    attempt: int
    candidate: Any
    feedback: RefinementFeedbackValue | None = None
    critique: Any = None


@dataclass(frozen=True, slots=True)
class RefinementFailureValue:
    stage: str
    attempt: int
    max_attempts: int
    exhausted: bool
    message: str
    error: Any
    last_candidate_digest: str
    last_feedback_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionActivity:
    identity: str
    kind: str
    operation: str
    inputs: tuple[str, ...]
    implementation_hash: str | None = None
    effect_record: str | None = None
    source: str | None = None
    source_hash: str | None = None
    synthetic: bool = False


@dataclass(frozen=True, slots=True)
class ValueReference:
    identity: str
    activity: str
    children: tuple[tuple[str, str], ...] = ()
    artifact: str | None = None
    dependencies: tuple[str, ...] = ()
    entries: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProvenanceGraph:
    activities: tuple[ProductionActivity, ...]
    values: tuple[ValueReference, ...]
    result: str | None
