# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from prism.platform.domain.agent_logs import AgentReasoningLog, AgentReasoningLogLink


def test_agent_reasoning_log_renders_self_contained_markdown() -> None:
    log = AgentReasoningLog(
        log_id="log_1",
        agent_id="agent_1",
        agent_name="Example Agent",
        agent_kind="inference",
        created_at="2026-03-19T12:00:00+00:00",
        invocation_reason="Assess the fragment.",
        input_summary="Short summary.",
        reasoning_steps=["Step 1", "Step 2"],
        outputs_summary=["Produced result."],
        links=[AgentReasoningLogLink(label="Artifact", href="artifacts/result.md")],
        metadata={"confidence": 0.6},
    )

    markdown = log.to_markdown()

    assert "# Example Agent" in markdown
    assert "## Reasoning Steps" in markdown
    assert "[Artifact](artifacts/result.md)" in markdown
    assert '"confidence": 0.6' in markdown
