# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema models for skill specs and planner metadata."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from prism.platform.specs.agent_contracts import CapabilityContractSpec
from prism.platform.specs.semantic_types import SkillTypeSpec
from prism.platform.specs.skill_contract_profiles import SkillContractProfileSpec
from prism.platform.specs.tactic_bindings import TacticBehaviorSpec
from pydantic import BaseModel, ConfigDict, Field


class SkillPlannerSpec(BaseModel):
    """Planner-facing routing metadata attached to a skill spec."""

    model_config = ConfigDict(extra="forbid")

    invocation_condition: str = ""
    use_cases: list[str] = Field(default_factory=list)
    not_applicable_when: list[str] = Field(default_factory=list)
    selection_role: str = "analysis"
    selection_priority: int = 50
    companion_skill_ids: list[str] = Field(default_factory=list)


class SkillSpec(BaseModel):
    """Declarative spec describing one executable reasoning skill."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    version: str
    name: str
    description: str
    objective_kinds: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    contract: dict[str, Any] = Field(default_factory=dict)
    package_id: str | None = None
    package_name: str | None = None
    package_version: str | None = None
    package_tags: list[str] = Field(default_factory=list)
    semantic_folder: str | None = None
    parser_spec_id: str | None = None
    critic_spec_ids: list[str] = Field(default_factory=list)
    budget_policy: dict[str, Any] = Field(default_factory=dict)
    executor_kind: str = "mock"
    prompt: dict[str, Any] = Field(default_factory=dict)
    planner: SkillPlannerSpec = Field(default_factory=SkillPlannerSpec)
    tactic: TacticBehaviorSpec = Field(default_factory=TacticBehaviorSpec)
    capability_contract: CapabilityContractSpec | None = None
    skill_type: SkillTypeSpec | None = None
    skill_contract_profile: SkillContractProfileSpec | None = None
