# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed overlays for the epistemic contract of one skill.

This module sits on top of the existing PRISM skill spec rather than replacing it.
`SkillSpec` already has `input_schema`, `output_schema`, free-form `contract`,
planner metadata, a typed agent contract, and semantic typing. The profile below
adds the missing "what is this skill allowed to claim and how should it behave"
surface in a validator-friendly form.

The design is intentionally additive:

- existing module-owned capability YAML stays valid
- new skills can opt into stronger structure immediately
- old skills can still be viewed through a derived default profile
"""

from __future__ import annotations

# Platform-only capability schemas.
from typing import TYPE_CHECKING, Literal

from prism.platform.specs.agent_contracts import resolve_skill_capability_contract
from prism.platform.specs.semantic_types import SemanticTypeRef
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from prism.platform.specs.skill_specs import SkillSpec


ConfidenceRepresentation = Literal["scalar", "interval", "ordinal", "band"]
ProvenanceEmitMode = Literal["none", "artifact", "per-claim", "per-field"]
SkillCheckKind = Literal[
    "schema",
    "critic",
    "deterministic-test",
    "generative-eval",
    "runtime-check",
    "judge",
]
SkillDependencyKind = Literal[
    "skill",
    "critic",
    "aggregator",
    "parser",
    "reference-kb",
    "backend",
    "environment-agent",
    "workflow",
    "artifact",
    "tool",
]


class SkillInputEvidenceSpec(BaseModel):
    """One typed evidence channel that the skill is allowed to read.

    This is deliberately port-centric so it composes cleanly with the existing
    `AgentContractSpec.inputs` model instead of inventing a second I/O layer.
    """

    model_config = ConfigDict(extra="forbid")

    port_id: str
    semantic_types: list[SemanticTypeRef] = Field(default_factory=list)
    evidence_role: str = "primary"
    required: bool = True
    description: str = ""


class SkillOutputContractSpec(BaseModel):
    """The primary structured output surface expected from the skill."""

    model_config = ConfigDict(extra="forbid")

    port_id: str = "analysis_artifact"
    schema_ref: str | None = None
    required_fields: list[str] = Field(default_factory=list)
    description: str = ""


class SkillClaimPolicySpec(BaseModel):
    """Which claim families the skill may and may not emit."""

    model_config = ConfigDict(extra="forbid")

    admissible_claim_types: list[str] = Field(default_factory=list)
    prohibited_claim_types: list[str] = Field(default_factory=list)
    claim_justification_required: bool = True


class SkillConfidencePolicySpec(BaseModel):
    """How confidence should be expressed and bounded by evidence quality."""

    model_config = ConfigDict(extra="forbid")

    required: bool = True
    representation: ConfidenceRepresentation = "scalar"
    scale: str = "0-1"
    confidence_field: str = "confidence"
    require_uncertainty_explanation: bool = True
    max_confidence_without_corroboration: float | None = None
    allow_absent_when_deterministic: bool = False


class SkillProvenancePolicySpec(BaseModel):
    """What provenance the skill should emit alongside its conclusions."""

    model_config = ConfigDict(extra="forbid")

    emit_mode: ProvenanceEmitMode = "artifact"
    required_fields: list[str] = Field(default_factory=list)
    preserve_input_refs: bool = True
    citation_field: str | None = None
    evidence_field: str | None = None


class SkillCheckSpec(BaseModel):
    """A validator or evaluator attached to the skill contract profile."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    kind: SkillCheckKind = "schema"
    applies_to: list[str] = Field(default_factory=list)
    required: bool = True
    notes: str = ""


class SkillDependencySpec(BaseModel):
    """A typed upstream or downstream dependency edge for one skill."""

    model_config = ConfigDict(extra="forbid")

    ref_id: str
    kind: SkillDependencyKind = "skill"
    required: bool = True
    rationale: str = ""


class SkillContractProfileSpec(BaseModel):
    """First-class contract overlay for epistemic behavior and validation.

    The existing `SkillSpec.contract` field remains useful as a prose-friendly
    authoring surface. This profile is the machine-facing normalization of the
    same intent.
    """

    model_config = ConfigDict(extra="forbid")

    input_evidence_types: list[SkillInputEvidenceSpec] = Field(default_factory=list)
    output_contract: SkillOutputContractSpec | None = None
    preconditions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    claim_policy: SkillClaimPolicySpec = Field(default_factory=SkillClaimPolicySpec)
    confidence_policy: SkillConfidencePolicySpec = Field(
        default_factory=SkillConfidencePolicySpec
    )
    provenance_policy: SkillProvenancePolicySpec = Field(
        default_factory=SkillProvenancePolicySpec
    )
    validators: list[SkillCheckSpec] = Field(default_factory=list)
    evaluators: list[SkillCheckSpec] = Field(default_factory=list)
    upstream_dependencies: list[SkillDependencySpec] = Field(default_factory=list)
    downstream_dependencies: list[SkillDependencySpec] = Field(default_factory=list)


def resolve_skill_contract_profile(skill: SkillSpec) -> SkillContractProfileSpec:
    """Return the explicit or derived skill contract profile.

    The derived profile is intentionally conservative. It never guesses more than
    the current capability index already states, but it does translate the current skill
    surfaces into a single object that downstream tools can inspect uniformly.
    """

    if skill.skill_contract_profile is not None:
        return skill.skill_contract_profile

    contract = resolve_skill_capability_contract(skill)
    primary_output = next(
        (port for port in contract.outputs if port.port_id == "analysis_artifact"),
        next(
            (port for port in contract.outputs if port.payload_kind != "reasoning-log"),
            None,
        ),
    )
    required_fields = list(skill.output_schema.get("required", []))
    assumptions = (
        list(skill.prompt.get("assumptions", []))
        if isinstance(skill.prompt, dict)
        else []
    )

    input_evidence_types = [
        SkillInputEvidenceSpec(
            port_id=port.port_id,
            semantic_types=(
                [port.semantic_type] if port.semantic_type is not None else []
            ),
            evidence_role=_default_evidence_role(port.port_id),
            required=port.required,
            description=port.description,
        )
        for port in contract.inputs
        if port.payload_kind != "reasoning-log"
    ]

    validators = [
        SkillCheckSpec(
            check_id=critic_id,
            kind="critic",
            applies_to=["analysis_artifact"],
            required=True,
            notes="Derived from `critic_spec_ids` on the skill spec.",
        )
        for critic_id in skill.critic_spec_ids
    ]

    return SkillContractProfileSpec(
        input_evidence_types=input_evidence_types,
        output_contract=SkillOutputContractSpec(
            port_id=(
                primary_output.port_id
                if primary_output is not None
                else "analysis_artifact"
            ),
            required_fields=required_fields,
            description=(
                primary_output.description
                if primary_output is not None
                else "Primary structured output emitted by the skill."
            ),
        ),
        preconditions=list(contract.invocation.preconditions),
        assumptions=assumptions,
        claim_policy=SkillClaimPolicySpec(
            admissible_claim_types=_default_claim_types(
                skill=skill, required_fields=required_fields
            ),
        ),
        confidence_policy=SkillConfidencePolicySpec(
            required="confidence" in required_fields,
            allow_absent_when_deterministic=False,
        ),
        provenance_policy=SkillProvenancePolicySpec(
            emit_mode="artifact",
            required_fields=_default_provenance_fields(required_fields),
            evidence_field="evidence" if "evidence" in required_fields else None,
        ),
        validators=validators,
    )


def _default_evidence_role(port_id: str) -> str:
    if port_id == "objective_context":
        return "objective"
    if port_id == "context_artifacts":
        return "context"
    return "primary"


def _default_claim_types(*, skill: SkillSpec, required_fields: list[str]) -> list[str]:
    claim_types = [
        "summary",
        "claim",
        "counter-claim",
        "assumption",
        "critical-question",
    ]
    material_type = str(skill.contract.get("material_inference_type") or "").strip()
    if material_type:
        claim_types.append(material_type)
    if "answer" in required_fields:
        claim_types.append("bounded-answer")
    if "unknowns" in required_fields:
        claim_types.append("uncertainty-report")
    if "evidence" in required_fields:
        claim_types.append("evidence-backed-claim")
    if "equational_certificate" in required_fields:
        claim_types.append("symbolic-equivalence-certificate")
    if "equational_step_proposals" in required_fields:
        claim_types.append("equational-step-proposal")
    if "informal_derivation" in required_fields:
        claim_types.append("informal-equational-derivation")
    return sorted(set(claim_types))


def _default_provenance_fields(required_fields: list[str]) -> list[str]:
    fields: list[str] = []
    for field_name in ["claims", "counter_claims", "evidence"]:
        if field_name in required_fields:
            fields.append(field_name)
    return fields
