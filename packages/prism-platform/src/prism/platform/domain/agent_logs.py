# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform reasoning-log models for inference and maintenance agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentReasoningLogLink(BaseModel):
    """A labeled link embedded in a reasoning log."""

    model_config = ConfigDict(extra="forbid")

    label: str
    href: str


class AgentReasoningLog(BaseModel):
    """A self-contained execution trace for any PRISM agent surface."""

    model_config = ConfigDict(extra="forbid")

    log_id: str
    agent_id: str
    agent_name: str
    agent_kind: str
    created_at: str
    status: str = "completed"
    run_id: str | None = None
    task_id: str | None = None
    target_ref: str | None = None
    invocation_reason: str
    input_summary: str
    context_items: list[str] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)
    outputs_summary: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    links: list[AgentReasoningLogLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render the reasoning log as a standalone Markdown report."""
        lines = [
            f"# {self.agent_name}",
            "",
            "## Identity",
            f"- Agent id: `{self.agent_id}`",
            f"- Agent kind: `{self.agent_kind}`",
            f"- Log id: `{self.log_id}`",
            f"- Created at: `{self.created_at}`",
            f"- Status: `{self.status}`",
        ]
        if self.run_id:
            lines.append(f"- Run id: `{self.run_id}`")
        if self.task_id:
            lines.append(f"- Task id: `{self.task_id}`")
        if self.target_ref:
            lines.append(f"- Target ref: `{self.target_ref}`")
        lines.extend(
            [
                "",
                "## Invocation",
                self.invocation_reason,
                "",
                "## Input Summary",
                self.input_summary,
                "",
                "## Context",
            ]
        )
        lines.extend(f"- {item}" for item in self.context_items or ["none"])
        lines.extend(["", "## Reasoning Steps"])
        lines.extend(f"- {item}" for item in self.reasoning_steps or ["none"])
        lines.extend(["", "## Outputs"])
        lines.extend(f"- {item}" for item in self.outputs_summary or ["none"])
        lines.extend(["", "## Open Questions"])
        lines.extend(f"- {item}" for item in self.open_questions or ["none"])
        lines.extend(["", "## Remaining Uncertainty"])
        lines.extend(f"- {item}" for item in self.uncertainty or ["none"])
        lines.extend(["", "## Links"])
        if self.links:
            lines.extend(f"- [{link.label}]({link.href})" for link in self.links)
        else:
            lines.append("- none")
        lines.extend(
            ["", "## Metadata Snapshot", "```json", self._metadata_json(), "```"]
        )
        return "\n".join(lines) + "\n"

    def _metadata_json(self) -> str:
        import json

        return json.dumps(self.metadata, indent=2, ensure_ascii=True)
