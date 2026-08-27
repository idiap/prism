# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema model for environment-maintenance agent specs."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from prism.platform.specs.agent_contracts import AgentContractSpec
from pydantic import BaseModel, ConfigDict, Field


class EnvironmentAgentSpec(BaseModel):
    """Declarative spec describing one maintenance agent surface."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    version: str
    name: str
    description: str
    invocation_condition: str
    trigger_event: str
    cadence: str
    threshold: int | None = None
    responsibilities: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    action_policy: dict[str, Any] = Field(default_factory=dict)
    agent_contract: AgentContractSpec | None = None
