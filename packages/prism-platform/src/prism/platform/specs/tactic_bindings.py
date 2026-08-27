# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema models for skill-backed tactic registry entries."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TacticBehaviorSpec(BaseModel):
    """Optional tactic behavior metadata owned by a skill or Prism tactic."""

    model_config = ConfigDict(extra="forbid")

    preconditions: list[str] = Field(default_factory=list)
    expansion_rule: dict[str, Any] = Field(default_factory=dict)
    stopping_rule: dict[str, Any] = Field(default_factory=dict)


class CapabilityTacticBinding(BaseModel):
    """Registry-facing tactic surface derived from one or more skills."""

    model_config = ConfigDict(extra="forbid")

    version: str
    name: str
    skills: list[str] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    expansion_rule: dict[str, Any] = Field(default_factory=dict)
    stopping_rule: dict[str, Any] = Field(default_factory=dict)
