# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Versioned typed runtime output and trace models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Mapping

from prism.language.core import ProvenanceGraph

TRACE_VERSION = "11"


def require_supported_trace(payload: Mapping[str, Any]) -> None:
    version = payload.get("trace_version")
    if version != TRACE_VERSION:
        raise ValueError(
            f"unsupported trace version {version!r}; expected {TRACE_VERSION!r}. "
            "Run the program again to produce a supported trace."
        )


@dataclass(frozen=True, slots=True)
class Diagnostic:
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ObservedValue:
    path: tuple[str, ...]
    reference: str | None
    producer: str
    assurance: Literal["unchecked", "supported", "validated", "proved"]
    claim_disposition: str = "not_applicable"
    assumptions: tuple[str, ...] = ()
    claim: Any = None
    certificate: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class OccurrenceOutcome:
    execution: Literal["running", "completed", "failed"] = "running"
    contract: Literal["pending", "satisfied", "rejected"] = "pending"
    observed: tuple[ObservedValue, ...] = ()


@dataclass(frozen=True, slots=True)
class TraceEvent:
    kind: str
    name: str
    status: str = "accepted"
    assurance: str | None = None
    provenance: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    outcome: OccurrenceOutcome | None = None


@dataclass(slots=True)
class RunOutput:
    path: str | None
    source_hash: str
    status: str
    result: Any
    trace: list[TraceEvent]
    diagnostics: list[Diagnostic] = field(default_factory=list)
    effect_records: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_version: str = TRACE_VERSION
    provenance: ProvenanceGraph | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
