# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Optional semantic and effect typing for flexible PRISM skill composition."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SemanticFacetScalar = str | bool | int | float
SemanticFacetValue = (
    SemanticFacetScalar | list[str] | list[bool] | list[int] | list[float] | None
)
SkillGenerationMode = Literal["static", "template", "generated"]
MergeStrategy = Literal[
    "latest-wins", "append-evidence", "bundle-for-critic", "synthesize-children"
]
MutationScope = Literal["branch-local", "run-wide"]


class SemanticTypeRef(BaseModel):
    """Open semantic type reference for ports, bindings, and persisted artifacts."""

    model_config = ConfigDict(extra="forbid")

    type_id: str
    parent_type_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    facets: dict[str, SemanticFacetValue] = Field(default_factory=dict)

    def all_type_ids(self) -> set[str]:
        """Return the declared semantic type ids, including aliases and parents."""
        return {self.type_id, *self.parent_type_ids, *self.aliases}


class SkillEffectSpec(BaseModel):
    """Operational effect traits exposed to planners and orchestrators."""

    model_config = ConfigDict(extra="forbid")

    produces_analysis: bool = True
    opens_debts: bool = False
    synthesizes_children: bool = False
    parallel_safe: bool = True
    requires_ordering: bool = False
    merge_strategy: MergeStrategy = "latest-wins"
    mutation_scope: MutationScope = "branch-local"
    coordination_tags: list[str] = Field(default_factory=list)


class SkillTypeSpec(BaseModel):
    """Optional semantic typing envelope for a skill."""

    model_config = ConfigDict(extra="forbid")

    family: str = "analysis"
    subject_type: SemanticTypeRef | None = None
    input_types: dict[str, SemanticTypeRef] = Field(default_factory=dict)
    output_types: dict[str, SemanticTypeRef] = Field(default_factory=dict)
    effects: SkillEffectSpec = Field(default_factory=SkillEffectSpec)
    generation_mode: SkillGenerationMode = "static"
    template_id: str | None = None
    extensible: bool = True


class PortCompatibilityIssue(BaseModel):
    """One explicit composition mismatch between an upstream and downstream port."""

    model_config = ConfigDict(extra="forbid")

    upstream_port_id: str
    downstream_port_id: str
    reason: str


class SkillCompositionReport(BaseModel):
    """Compatibility report for composing one skill's outputs into another skill's inputs."""

    model_config = ConfigDict(extra="forbid")

    upstream_skill_id: str
    downstream_skill_id: str
    compatible: bool = True
    notes: list[str] = Field(default_factory=list)
    issues: list[PortCompatibilityIssue] = Field(default_factory=list)


def semantic_type_compatible(
    provided: SemanticTypeRef | None, expected: SemanticTypeRef | None
) -> bool:
    """Return whether two semantic types are compatible.

    The check is intentionally permissive: missing type metadata does not block
    composition, and facets only fail when both sides declare contradictory values.
    """

    if provided is None or expected is None:
        return True
    provided_ids = provided.all_type_ids()
    if expected.type_id not in provided_ids and not set(expected.aliases).intersection(
        provided_ids
    ):
        return False
    for key, expected_value in expected.facets.items():
        if key not in provided.facets:
            continue
        if not _facet_value_compatible(provided.facets[key], expected_value):
            return False
    return True


def _facet_value_compatible(
    provided: SemanticFacetValue, expected: SemanticFacetValue
) -> bool:
    if expected is None or provided is None:
        return True
    if isinstance(expected, list):
        if isinstance(provided, list):
            return set(expected).issubset(set(provided))
        return provided in expected
    if isinstance(provided, list):
        return expected in provided
    return provided == expected
