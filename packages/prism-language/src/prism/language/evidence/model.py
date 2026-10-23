# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Evidence, provenance, and material support values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    method: str
    observed_at: str | None = None
    transformations: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    integrity: str = "Unchecked"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Evidence:
    value: Any
    provenance: tuple[Provenance, ...]


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    disposition: str
    explanation: str

    def __post_init__(self):
        if self.disposition not in {"accepted", "rejected", "inconclusive"}:
            raise ValueError("unknown policy disposition")


@dataclass(frozen=True, slots=True)
class Assessment:
    proposition: str
    evidence: Evidence
    policy: str
    decision: PolicyDecision
    policy_identity: str
    policy_hash: str
    claim: Any
    evidence_reference: str

    @property
    def disposition(self) -> str:
        return self.decision.disposition

    @property
    def explanation(self) -> str:
        return self.decision.explanation


@dataclass(frozen=True, slots=True)
class Supported:
    assessment: Assessment

    def __post_init__(self):
        if self.assessment.decision.disposition != "accepted":
            raise ValueError("Supported requires an accepted assessment")

    @property
    def proposition(self) -> str:
        return self.assessment.proposition

    @property
    def evidence(self) -> Evidence:
        return self.assessment.evidence

    @property
    def policy(self) -> str:
        return self.assessment.policy

    @property
    def explanation(self) -> str:
        return self.assessment.decision.explanation

    @property
    def status(self) -> str:
        return "accepted"
