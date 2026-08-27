# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed artifacts for document-level meta-reasoning learning.

These models define the first stable interchange surface for the
`meta-reasoning-learning` tactic. The intent is deliberately narrower than
domain reasoning itself: given example documents and a target task, the tactic
should describe the document layout, show how existing skills cover that layout,
name uncovered capabilities, and package the result as a tactic implementation
plan.
"""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Literal

from prism.platform.specs.semantic_types import SemanticTypeRef
from pydantic import BaseModel, ConfigDict, Field, model_validator

AuthoringMode = Literal["recommend-only", "draft-bundles", "write-bundles"]
CoverageRole = Literal["primary", "supporting", "routing", "control", "candidate"]
CoverageStatus = Literal["strong", "usable", "weak", "missing"]
GapSeverity = Literal["low", "medium", "high", "blocker"]
ProbeKind = Literal["deterministic", "generative", "manual"]
TacticCompositionKind = Literal[
    "sequence",
    "branch",
    "loop",
    "refinement",
    "judge",
    "delegation",
    "aggregation",
    "contradiction-resolution",
]

DocumentSegmentRole = Literal[
    "document-header",
    "procedural-posture",
    "case-facts",
    "legal-definition",
    "legal-citation",
    "legal-standard",
    "precedent",
    "party-argument",
    "opposing-view",
    "convergent-reasoning",
    "defeater",
    "court-reasoning",
    "remedy",
    "political-claim",
    "policy-recommendation",
    "evidence-summary",
    "unknown",
    "other",
]

ReasoningSurface = Literal[
    "definition",
    "citation",
    "fact",
    "precedent-authority",
    "testimony",
    "opposition",
    "convergence",
    "defeater",
    "judgment-context",
    "value-judgment",
    "causal-claim",
    "practical-reasoning",
    "uncertainty",
    "other",
]


class SourceSpanSpec(BaseModel):
    """Stable location reference for a segment inside one source document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    section_id: str | None = None
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    label: str = ""

    @model_validator(mode="after")
    def _end_after_start(self) -> "SourceSpanSpec":
        if (
            self.start_char is not None
            and self.end_char is not None
            and self.end_char < self.start_char
        ):
            raise ValueError("end_char must be greater than or equal to start_char")
        return self


class DocumentSectionSpec(BaseModel):
    """Optional pre-existing layout unit supplied by a document parser or user."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str = ""
    text: str
    order_index: int = Field(default=0, ge=0)
    source_span: SourceSpanSpec | None = None


class SourceDocumentSpec(BaseModel):
    """One source document available to the meta-learning tactic."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    text: str
    source_label: str = ""
    title: str = ""
    sections: list[DocumentSectionSpec] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class DocumentSegmentSpec(BaseModel):
    """A reasoning-sized unit with a provisional role and evidence surfaces."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str
    text: str
    source_span: SourceSpanSpec
    role: DocumentSegmentRole = "unknown"
    role_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    surfaces: list[ReasoningSurface] = Field(default_factory=list)
    role_rationale: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReasoningLayoutSpec(BaseModel):
    """Document-level map that later services use for batch skill matching."""

    model_config = ConfigDict(extra="forbid")

    layout_id: str
    documents: list[SourceDocumentSpec]
    segments: list[DocumentSegmentSpec]
    role_taxonomy_version: str = "0.1.0"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _segments_reference_known_documents(self) -> "ReasoningLayoutSpec":
        document_ids = {document.document_id for document in self.documents}
        unknown = sorted(
            {
                segment.source_span.document_id
                for segment in self.segments
                if segment.source_span.document_id not in document_ids
            }
        )
        if unknown:
            raise ValueError(
                f"segments reference unknown document ids: {', '.join(unknown)}"
            )
        return self

    def segments_by_role(self, role: DocumentSegmentRole) -> list[DocumentSegmentSpec]:
        """Return all segments currently assigned to a role."""
        return [segment for segment in self.segments if segment.role == role]


class SkillCoverageMatchSpec(BaseModel):
    """One ranked existing-skill match for a document segment."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str
    skill_id: str
    skill_name: str = ""
    selection_role: str = "analysis"
    coverage_role: CoverageRole = "supporting"
    coverage_status: CoverageStatus = "usable"
    score: float = Field(default=0.0, ge=0.0)
    rank: int = Field(default=1, ge=1)
    invocation_condition: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    strong_phrase_hits: list[str] = Field(default_factory=list)
    evidence_channels: int = Field(default=0, ge=0)
    reasons: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SegmentSkillCoverageSpec(BaseModel):
    """Coverage judgment for one segment after batch skill matching."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str
    primary_skill_id: str | None = None
    matches: list[SkillCoverageMatchSpec] = Field(default_factory=list)
    coverage_status: CoverageStatus = "missing"
    coverage_notes: list[str] = Field(default_factory=list)
    missing_capability_hints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _primary_skill_is_matched_when_present(self) -> "SegmentSkillCoverageSpec":
        if self.primary_skill_id is None:
            return self
        if not any(match.skill_id == self.primary_skill_id for match in self.matches):
            raise ValueError(
                "primary_skill_id must identify one of the segment's matches"
            )
        return self


class SkillCoverageMapSpec(BaseModel):
    """Document-wide skill coverage map grounded in existing Prism skills."""

    model_config = ConfigDict(extra="forbid")

    coverage_id: str
    layout_id: str
    segment_coverages: list[SegmentSkillCoverageSpec]
    aggregate_skill_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def uncovered_segment_ids(self) -> list[str]:
        """Return segment ids whose current coverage remains weak or absent."""
        return [
            coverage.segment_id
            for coverage in self.segment_coverages
            if coverage.coverage_status in {"weak", "missing"}
        ]


class SkillGapSpec(BaseModel):
    """Missing capability inferred from weak coverage or unserved document roles."""

    model_config = ConfigDict(extra="forbid")

    gap_id: str
    segment_ids: list[str] = Field(default_factory=list)
    role: DocumentSegmentRole = "unknown"
    missing_capability: str
    rationale: str
    severity: GapSeverity = "medium"
    evidence: list[str] = Field(default_factory=list)
    recommended_inference_type: str | None = None
    recommended_skill_id: str | None = None
    recommended_skill_name: str | None = None


class AuthoredSkillCandidateSpec(BaseModel):
    """Provisional skill authoring target created from one or more gaps."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_id: str
    name: str
    description: str
    inference_type: str
    source_gap_ids: list[str] = Field(default_factory=list)
    objective_kind: str
    critic_id: str | None = None
    tactic_id: str | None = None
    authoring_mode: AuthoringMode = "recommend-only"
    contract_expectations: list[str] = Field(default_factory=list)
    provenance_notes: list[str] = Field(default_factory=list)
    output_semantic_type: SemanticTypeRef | None = None


class TacticPlanStepSpec(BaseModel):
    """One executable or provisional step in the compiled reasoning tactic."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    label: str
    composition_kind: TacticCompositionKind = "sequence"
    skill_id: str | None = None
    candidate_skill_id: str | None = None
    consumes: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    validation_gates: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CompiledTacticPlanSpec(BaseModel):
    """Ordered tactic graph assembled from matched and candidate skills."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    target_task: str
    entry_step_id: str
    steps: list[TacticPlanStepSpec]
    aggregation_strategy: str = "append-evidence"
    contradiction_strategy: str = "merge-with-uncertainty"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _references_known_steps(self) -> "CompiledTacticPlanSpec":
        step_ids = {step.step_id for step in self.steps}
        if self.entry_step_id not in step_ids:
            raise ValueError("entry_step_id must identify one of the tactic steps")
        missing_dependencies = sorted(
            {
                dependency
                for step in self.steps
                for dependency in step.depends_on
                if dependency not in step_ids
            }
        )
        if missing_dependencies:
            raise ValueError(
                f"step dependencies reference unknown step ids: {', '.join(missing_dependencies)}"
            )
        return self

    def ordered_step_ids(self) -> list[str]:
        """Return the declared step order without trying to topologically sort it."""
        return [step.step_id for step in self.steps]


class ValidationProbeSpec(BaseModel):
    """A deterministic, generative, or manual probe for the learned tactic."""

    model_config = ConfigDict(extra="forbid")

    probe_id: str
    kind: ProbeKind
    description: str
    input_refs: list[str] = Field(default_factory=list)
    expected_observations: list[str] = Field(default_factory=list)
    failure_to_regression: str = ""
    severity: GapSeverity = "medium"


class MetaReasoningLearningRequestSpec(BaseModel):
    """User-facing request for learning a task-specific reasoning tactic."""

    model_config = ConfigDict(extra="forbid")

    target_task: str
    documents: list[SourceDocumentSpec]
    domain_hint: str = ""
    seed_skill_ids: list[str] = Field(default_factory=list)
    authoring_mode: AuthoringMode = "recommend-only"
    constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _requires_documents(self) -> "MetaReasoningLearningRequestSpec":
        if not self.documents:
            raise ValueError("at least one document is required")
        return self


class MetaReasoningLearningPlanSpec(BaseModel):
    """Complete S1 artifact bundle produced by the future learning service."""

    model_config = ConfigDict(extra="forbid")

    request: MetaReasoningLearningRequestSpec
    reasoning_layout: ReasoningLayoutSpec
    skill_coverage_map: SkillCoverageMapSpec
    skill_gap_report: list[SkillGapSpec] = Field(default_factory=list)
    authored_skill_candidates: list[AuthoredSkillCandidateSpec] = Field(
        default_factory=list
    )
    compiled_tactic_plan: CompiledTacticPlanSpec
    validation_plan: list[ValidationProbeSpec] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cross_reference_artifacts(self) -> "MetaReasoningLearningPlanSpec":
        document_ids = {document.document_id for document in self.request.documents}
        layout_document_ids = {
            document.document_id for document in self.reasoning_layout.documents
        }
        if layout_document_ids - document_ids:
            unknown = ", ".join(sorted(layout_document_ids - document_ids))
            raise ValueError(
                f"reasoning_layout includes documents not present in request: {unknown}"
            )

        segment_ids = {segment.segment_id for segment in self.reasoning_layout.segments}
        coverage_segment_ids = {
            coverage.segment_id
            for coverage in self.skill_coverage_map.segment_coverages
        }
        if coverage_segment_ids - segment_ids:
            unknown = ", ".join(sorted(coverage_segment_ids - segment_ids))
            raise ValueError(
                f"skill_coverage_map references unknown segments: {unknown}"
            )

        gap_ids = {gap.gap_id for gap in self.skill_gap_report}
        candidate_gap_ids = {
            gap_id
            for candidate in self.authored_skill_candidates
            for gap_id in candidate.source_gap_ids
        }
        if candidate_gap_ids - gap_ids:
            unknown = ", ".join(sorted(candidate_gap_ids - gap_ids))
            raise ValueError(
                f"authored_skill_candidates reference unknown gaps: {unknown}"
            )
        return self
