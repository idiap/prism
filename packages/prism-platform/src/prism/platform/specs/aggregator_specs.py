# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema models for aggregation, arbitration, and contradiction handling.

Aggregation policy is represented with typed fields so the registry can validate
how evidence is merged, how contradictions are handled, and when a judge is
expected to arbitrate.
"""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any, Literal

from prism.platform.specs.semantic_types import MergeStrategy, SemanticTypeRef
from pydantic import BaseModel, ConfigDict, Field

ContradictionResolutionMode = Literal[
    "preserve-all",
    "prefer-judge",
    "merge-with-uncertainty",
    "latest-wins",
    "fail-fast",
]


class AggregatorInputSpec(BaseModel):
    """One upstream source consumed by an aggregator surface."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    role: str = "candidate"
    required: bool = True
    semantic_type: SemanticTypeRef | None = None
    description: str = ""


class AggregatorJudgePolicySpec(BaseModel):
    """Optional judge or critic handoff used during arbitration-heavy merges."""

    model_config = ConfigDict(extra="forbid")

    judge_ids: list[str] = Field(default_factory=list)
    quorum: int | None = None
    escalation_condition: str = ""


class AggregationPolicySpec(BaseModel):
    """Typed policy controlling how an aggregator combines multiple inputs."""

    model_config = ConfigDict(extra="forbid")

    mode: MergeStrategy | Literal["arbitrate"] = "append-evidence"
    combine_fields: list[str] = Field(default_factory=list)
    confidence_field: str | None = None
    contradiction_resolution: ContradictionResolutionMode = "preserve-all"
    emit_conflicts_field: str | None = None
    judge_policy: AggregatorJudgePolicySpec | None = None
    notes: list[str] = Field(default_factory=list)


class AggregatorSpec(BaseModel):
    """Declarative spec describing one aggregation surface."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    version: str
    name: str
    description: str = ""
    inputs: list[AggregatorInputSpec] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    policy: AggregationPolicySpec = Field(default_factory=AggregationPolicySpec)
