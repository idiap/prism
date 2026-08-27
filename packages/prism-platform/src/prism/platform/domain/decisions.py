# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform decision and diagnostic models."""

from __future__ import annotations

from typing import Any

from prism.platform.domain.debts import DebtRecord
from prism.platform.domain.enums import DecisionKind
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Diagnostic(BaseModel):
    """A critic-local assessment of a target artifact."""

    model_config = ConfigDict(extra="forbid")

    judge_id: str
    verdict: str
    localizations: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    notes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, value: float) -> float:
        """Ensure diagnostic confidence is expressed on the normalized 0-1 scale."""
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return value


class CriticDecision(BaseModel):
    """A persisted decision about acceptance, repair, replanning, or deferral."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    kind: DecisionKind
    target_ref: str | None = None
    frontier_id: str | None = None
    patch: dict[str, Any] | None = None
    reason: dict[str, Any] = Field(default_factory=dict)
    opened_debts: list[DebtRecord] = Field(default_factory=list)
