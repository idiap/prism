# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Versioned typed runtime output and trace models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Diagnostic:
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    kind: str
    name: str
    status: str = "accepted"
    assurance: str | None = None
    provenance: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


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
    trace_version: str = "10"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
