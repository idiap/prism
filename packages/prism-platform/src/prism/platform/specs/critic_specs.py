# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema model for critic specifications."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from prism.platform.specs.agent_contracts import AgentContractSpec
from pydantic import BaseModel, ConfigDict, Field


class CriticSpec(BaseModel):
    """Declarative spec describing one critic and its rules."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    version: str
    name: str
    description: str
    target_kinds: list[str] = Field(default_factory=list)
    judge_ids: list[str] = Field(default_factory=list)
    decision_schema: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)
    agent_contract: AgentContractSpec | None = None
