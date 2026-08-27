# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Untrusted proof-generation interchange structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from prism.language.kernel import Context, Environment, Term


@dataclass(frozen=True, slots=True)
class ProofSyntax:
    source: str
    producer: str = "unknown"
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RawProofTerm:
    term: Term
    expected_type: Term
    source: str | None = None
    producer: str = "surface-elaborator"


@dataclass(frozen=True, slots=True)
class TacticInput:
    goal: Term
    context: Context
    environment: Environment


@dataclass(frozen=True, slots=True)
class TacticOutput:
    term: Term | None
    proof_source: str | None = None
    diagnostics: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifiedConstruction:
    target: str
    value: Any
    proof: Term
    proposition: Term
