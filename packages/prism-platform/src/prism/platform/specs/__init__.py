# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Specification models and loaders.

The package keeps most models in focused modules so capability loading can import
only the surfaces it needs. Meta-reasoning learning specs are exported here as a
convenience for tests and future services that assemble document-level tactic
plans.
"""

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

__all__ = [
    "AuthoredSkillCandidateSpec",
    "CompiledTacticPlanSpec",
    "DocumentSegmentSpec",
    "MetaReasoningLearningPlanSpec",
    "MetaReasoningLearningRequestSpec",
    "ReasoningLayoutSpec",
    "SegmentSkillCoverageSpec",
    "SkillCoverageMapSpec",
    "SkillCoverageMatchSpec",
    "SkillGapSpec",
    "SourceDocumentSpec",
    "SourceSpanSpec",
    "TacticPlanStepSpec",
    "ValidationProbeSpec",
]
