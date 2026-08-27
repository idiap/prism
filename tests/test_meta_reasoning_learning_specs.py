# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

import pytest
from prism.platform.specs.meta_reasoning_learning_specs import (
    AuthoredSkillCandidateSpec,
    CompiledTacticPlanSpec,
    DocumentSegmentSpec,
    MetaReasoningLearningPlanSpec,
    MetaReasoningLearningRequestSpec,
    ReasoningLayoutSpec,
    SegmentSkillCoverageSpec,
    SkillCoverageMapSpec,
    SkillCoverageMatchSpec,
    SkillGapSpec,
    SourceDocumentSpec,
    SourceSpanSpec,
    TacticPlanStepSpec,
    ValidationProbeSpec,
)
from prism.platform.specs.semantic_types import SemanticTypeRef
from prism.platform.specs.tactic_bindings import CapabilityTacticBinding
from pydantic import ValidationError


def _echr_document() -> SourceDocumentSpec:
    return SourceDocumentSpec(
        document_id="echr-demo",
        title="Synthetic ECHR-style argument",
        source_label="local-fixture",
        text=(
            "Relevant law: Article 8 protects private life subject to lawful and proportionate limits.\n"
            "Precedent: In a similar surveillance case, the Court required concrete safeguards.\n"
            "The applicant argues the measure was disproportionate; the Government says the safeguards were adequate."
        ),
    )


def _echr_layout() -> ReasoningLayoutSpec:
    document = _echr_document()
    return ReasoningLayoutSpec(
        layout_id="layout-echr-demo",
        documents=[document],
        segments=[
            DocumentSegmentSpec(
                segment_id="seg-law",
                text="Article 8 protects private life subject to lawful and proportionate limits.",
                source_span=SourceSpanSpec(
                    document_id=document.document_id, start_char=14, end_char=92
                ),
                role="legal-definition",
                role_confidence=0.82,
                surfaces=["definition", "judgment-context"],
                role_rationale=["Names a legal norm and its limiting condition."],
            ),
            DocumentSegmentSpec(
                segment_id="seg-precedent",
                text="In a similar surveillance case, the Court required concrete safeguards.",
                source_span=SourceSpanSpec(
                    document_id=document.document_id, start_char=104, end_char=171
                ),
                role="precedent",
                role_confidence=0.78,
                surfaces=["precedent-authority"],
                role_rationale=[
                    "Uses a prior case as authority for the present reasoning task."
                ],
            ),
            DocumentSegmentSpec(
                segment_id="seg-opposition",
                text=(
                    "The applicant argues the measure was disproportionate; "
                    "the Government says the safeguards were adequate."
                ),
                source_span=SourceSpanSpec(
                    document_id=document.document_id, start_char=172
                ),
                role="opposing-view",
                role_confidence=0.87,
                surfaces=["opposition", "defeater"],
                role_rationale=["Contrasts the parties' positions."],
            ),
        ],
        notes=["Synthetic fixture used to test artifact shape, not legal correctness."],
    )


def test_reasoning_layout_models_echr_style_document_roles() -> None:
    layout = _echr_layout()

    assert [segment.segment_id for segment in layout.segments_by_role("precedent")] == [
        "seg-precedent"
    ]
    assert layout.segments[0].surfaces == ["definition", "judgment-context"]

    payload = layout.model_dump()
    assert (
        ReasoningLayoutSpec.model_validate(payload).segments[2].role == "opposing-view"
    )


def test_meta_reasoning_learning_plan_round_trips_coverage_gaps_and_candidates() -> (
    None
):
    layout = _echr_layout()
    coverage = SkillCoverageMapSpec(
        coverage_id="coverage-echr-demo",
        layout_id=layout.layout_id,
        segment_coverages=[
            SegmentSkillCoverageSpec(
                segment_id="seg-law",
                coverage_status="weak",
                missing_capability_hints=["legal definition and standard analysis"],
            ),
            SegmentSkillCoverageSpec(
                segment_id="seg-precedent",
                primary_skill_id="precedent-analyzer",
                coverage_status="strong",
                matches=[
                    SkillCoverageMatchSpec(
                        segment_id="seg-precedent",
                        skill_id="precedent-analyzer",
                        skill_name="Precedent Analyzer",
                        coverage_role="primary",
                        coverage_status="strong",
                        score=4.2,
                        rank=1,
                        strong_phrase_hits=["similar case"],
                        evidence_channels=3,
                        reasons=["recognition markers", "skill description"],
                    )
                ],
            ),
            SegmentSkillCoverageSpec(
                segment_id="seg-opposition",
                primary_skill_id="argument-from-opposites-analyzer",
                coverage_status="usable",
                matches=[
                    SkillCoverageMatchSpec(
                        segment_id="seg-opposition",
                        skill_id="argument-from-opposites-analyzer",
                        skill_name="Argument from Opposites Analyzer",
                        coverage_role="primary",
                        score=2.1,
                        rank=1,
                    )
                ],
            ),
        ],
        aggregate_skill_ids=["precedent-analyzer", "argument-from-opposites-analyzer"],
    )
    gap = SkillGapSpec(
        gap_id="gap-legal-definition",
        segment_ids=["seg-law"],
        role="legal-definition",
        missing_capability="Analyze legal definitions and doctrinal standards without deciding legal merits.",
        rationale="The generic definition profile does not capture legal-source and doctrinal-standard boundaries.",
        severity="high",
        recommended_inference_type="definition-explication",
        recommended_skill_id="legal-definition-and-standard-analyzer",
        recommended_skill_name="Legal Definition and Standard Analyzer",
    )
    candidate = AuthoredSkillCandidateSpec(
        candidate_id="candidate-legal-definition",
        skill_id="legal-definition-and-standard-analyzer",
        name="Legal Definition and Standard Analyzer",
        description="Clarify legal terms, standards, and boundary conditions while preserving source uncertainty.",
        inference_type="definition-explication",
        source_gap_ids=[gap.gap_id],
        objective_kind="analyze-legal-definition-and-standard-analyzer",
        critic_id="legal-definition-and-standard-analyzer-guard",
        tactic_id="legal-definition-and-standard-analyzer-tactic",
        contract_expectations=[
            "preserve legal-source provenance",
            "avoid final legal merits claims",
        ],
        provenance_notes=["Motivated by seg-law in the ECHR-style fixture."],
        output_semantic_type=SemanticTypeRef(
            type_id="artifact.analysis.legal-definition",
            parent_type_ids=["artifact.analysis", "artifact"],
            facets={"document_role": "legal-definition"},
        ),
    )
    tactic_plan = CompiledTacticPlanSpec(
        plan_id="plan-echr-demo",
        target_task="Build an ECHR-style case reasoner",
        entry_step_id="layout",
        steps=[
            TacticPlanStepSpec(
                step_id="layout",
                label="Parse document reasoning layout",
                produces=["reasoning_layout"],
            ),
            TacticPlanStepSpec(
                step_id="match",
                label="Batch match existing skills",
                skill_id="existing-skill-batch-matcher",
                consumes=["reasoning_layout"],
                produces=["skill_coverage_map"],
                depends_on=["layout"],
            ),
            TacticPlanStepSpec(
                step_id="gap",
                label="Abduce missing skill coverage",
                skill_id="skill-gap-abducer",
                consumes=["skill_coverage_map"],
                produces=["skill_gap_report"],
                depends_on=["match"],
            ),
        ],
    )
    request = MetaReasoningLearningRequestSpec(
        target_task=tactic_plan.target_task,
        documents=layout.documents,
        domain_hint="legal_argumentation",
    )
    plan = MetaReasoningLearningPlanSpec(
        request=request,
        reasoning_layout=layout,
        skill_coverage_map=coverage,
        skill_gap_report=[gap],
        authored_skill_candidates=[candidate],
        compiled_tactic_plan=tactic_plan,
        validation_plan=[
            ValidationProbeSpec(
                probe_id="probe-no-legal-merits",
                kind="manual",
                description="Inspect that the plan does not claim to verify ECHR legal correctness.",
                expected_observations=[
                    "legal-source verification remains out of scope"
                ],
                failure_to_regression="Add a fixture assertion for legal-overclaim wording.",
            )
        ],
        uncertainty_notes=[
            "Legal authority checking is deferred until a reference KB exists."
        ],
    )

    assert coverage.uncovered_segment_ids() == ["seg-law"]
    assert plan.compiled_tactic_plan.ordered_step_ids() == ["layout", "match", "gap"]
    assert MetaReasoningLearningPlanSpec.model_validate(
        plan.model_dump()
    ).authored_skill_candidates[0].authoring_mode == ("recommend-only")


def test_meta_reasoning_learning_specs_reject_dangling_references() -> None:
    with pytest.raises(ValidationError, match="unknown document ids"):
        ReasoningLayoutSpec(
            layout_id="bad-layout",
            documents=[_echr_document()],
            segments=[
                DocumentSegmentSpec(
                    segment_id="seg-missing-doc",
                    text="A segment with a stale source reference.",
                    source_span=SourceSpanSpec(document_id="missing-doc"),
                )
            ],
        )

    with pytest.raises(ValidationError, match="unknown step ids"):
        CompiledTacticPlanSpec(
            plan_id="bad-plan",
            target_task="Bad dependency",
            entry_step_id="first",
            steps=[
                TacticPlanStepSpec(
                    step_id="first", label="First", depends_on=["missing"]
                )
            ],
        )


def test_tactic_spec_is_skill_backed() -> None:
    tactic = CapabilityTacticBinding(
        version="0.1.0",
        name="Meta Reasoning Learning Tactic",
        skills=["meta-reasoning-learning"],
    )

    assert tactic.skills == ["meta-reasoning-learning"]
    assert tactic.expansion_rule == {}
    assert tactic.stopping_rule == {}
