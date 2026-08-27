# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.platform.specs.aggregator_specs import AggregatorSpec
from prism.platform.specs.critic_specs import CriticSpec
from prism.platform.specs.environment_agent_specs import EnvironmentAgentSpec
from prism.platform.specs.loaders import iter_yaml_files, load_yaml
from prism.platform.specs.meta_reasoning_learning_specs import (
    MetaReasoningLearningRequestSpec,
    SourceDocumentSpec,
)
from prism.platform.specs.parser_specs import ParserSpec
from prism.platform.specs.reference_kb_specs import (
    ReferenceKBCheckSpec,
    ReferenceKBResourceSpec,
    ReferenceKBSpec,
)
from prism.platform.specs.scheme_specs import SchemeSpec
from prism.platform.specs.tactic_bindings import CapabilityTacticBinding


def test_loader_helpers_and_spec_models_smoke(tmp_path: Path) -> None:
    yaml_path = tmp_path / "sample.yaml"
    yaml_path.write_text("name: sample\nvalue: 1\n", encoding="utf-8")

    assert list(iter_yaml_files(tmp_path)) == [yaml_path]
    assert load_yaml(yaml_path) == {"name": "sample", "value": 1}

    aggregator = AggregatorSpec(spec_id="agg", version="1.0.0", name="Aggregator")
    parser = ParserSpec.model_validate(
        {
            "spec_id": "parser",
            "version": "1.0.0",
            "name": "Parser",
            "schema": {"type": "object"},
        }
    )
    critic = CriticSpec(
        spec_id="critic", version="1.0.0", name="Critic", description="desc"
    )
    environment = EnvironmentAgentSpec(
        agent_id="agent",
        version="1.0.0",
        name="Agent",
        description="desc",
        invocation_condition="when needed",
        trigger_event="task_completed",
        cadence="on-demand",
    )
    scheme = SchemeSpec(scheme_id="scheme", version="1.0.0", name="Scheme")
    tactic = CapabilityTacticBinding(version="1.0.0", name="Tactic", skills=["skill"])
    meta_request = MetaReasoningLearningRequestSpec(
        target_task="Build an ECHR-style reasoning tactic",
        documents=[
            SourceDocumentSpec(
                document_id="doc", text="A short legal argument fixture."
            )
        ],
    )
    reference_kb = ReferenceKBSpec(
        kb_id="mathlib4",
        version="1.0.0",
        name="Mathlib",
        description="desc",
        kb_kind="theorem-library",
        source_project="Mathlib",
        local_root=".lake/packages/mathlib/Mathlib",
        semantic_folder="autoformalization/reference-kbs",
        resources=[
            ReferenceKBResourceSpec(
                resource_id="source",
                kind="source-tree",
                path_hint=".lake/packages/mathlib/Mathlib",
                description="desc",
            )
        ],
        availability_checks=[
            ReferenceKBCheckSpec(
                check_id="exists",
                kind="path-exists",
                target=".lake/packages/mathlib/Mathlib",
                description="desc",
            )
        ],
    )

    assert aggregator.spec_id == "agg"
    assert aggregator.policy.mode == "append-evidence"
    assert parser.schema_definition == {"type": "object"}
    assert critic.target_kinds == []
    assert environment.outputs == []
    assert scheme.critical_question_templates == []
    assert tactic.skills == ["skill"]
    assert tactic.preconditions == []
    assert meta_request.authoring_mode == "recommend-only"
    assert reference_kb.resources[0].kind == "source-tree"
