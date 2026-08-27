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
class Supported:
    proposition: str
    evidence: Evidence
    policy: str
    status: str = "accepted"
    explanation: str = ""


def map_evidence(evidence: Evidence, value: Any, transformation: str) -> Evidence:
    return Evidence(
        value,
        tuple(
            Provenance(
                item.source,
                item.method,
                item.observed_at,
                (*item.transformations, transformation),
                item.assumptions,
                item.integrity,
                item.metadata,
            )
            for item in evidence.provenance
        ),
    )


def combine_evidence(*packets: Evidence, value: Any, transformation: str) -> Evidence:
    provenance = tuple(item for packet in packets for item in packet.provenance)
    return map_evidence(Evidence(value, provenance), value, transformation)
