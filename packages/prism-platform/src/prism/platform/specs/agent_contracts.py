# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed coordination contracts shared by all PRISM agent surfaces."""

from __future__ import annotations

# Platform-only capability schemas.
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from prism.platform.specs.semantic_types import SemanticTypeRef
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from prism.platform.specs.critic_specs import CriticSpec
    from prism.platform.specs.environment_agent_specs import EnvironmentAgentSpec
    from prism.platform.specs.skill_specs import SkillSpec

PortTransport = Literal[
    "inline-json", "artifact-ref-list", "document-link", "state-ref", "sidecar"
]
PortCardinality = Literal["one", "many", "optional"]
InvocationMode = Literal[
    "manual",
    "planner-routed",
    "task-hook",
    "task-threshold",
    "macro-task-threshold",
    "scenario-evaluation",
]
ExecutionModel = Literal["single-step", "workflow", "maintenance", "judge"]


class AgentPortSpec(BaseModel):
    """One typed input or output exposed by an agent surface."""

    model_config = ConfigDict(extra="forbid")

    port_id: str
    payload_kind: str
    transport: PortTransport
    description: str
    required: bool = True
    cardinality: PortCardinality = "one"
    path_hint: str | None = None
    json_schema: dict[str, Any] = Field(default_factory=dict)
    semantic_type: SemanticTypeRef | None = None


class AgentInvocationSpec(BaseModel):
    """How an agent is activated inside the repository lifecycle."""

    model_config = ConfigDict(extra="forbid")

    mode: InvocationMode
    invocation_condition: str
    primary_entrypoint: str | None = None
    execution_entrypoint: str | None = None
    trigger_event: str | None = None
    cadence: str | None = None
    threshold: int | None = None
    preconditions: list[str] = Field(default_factory=list)
    not_applicable_when: list[str] = Field(default_factory=list)


class AgentCoordinationSpec(BaseModel):
    """How an agent composes with peers and where it belongs in the lifecycle."""

    model_config = ConfigDict(extra="forbid")

    organization_group: str
    lifecycle_stage: str
    role: str
    execution_model: ExecutionModel
    companion_agent_ids: list[str] = Field(default_factory=list)
    allowed_upstream_agent_kinds: list[str] = Field(default_factory=list)
    allowed_downstream_agent_kinds: list[str] = Field(default_factory=list)
    coordination_notes: str = ""


class CapabilityCoordinationSpec(BaseModel):
    """Composition metadata for a skill capability, without agent identity."""

    model_config = ConfigDict(extra="forbid")

    organization_group: str
    lifecycle_stage: str
    role: str
    execution_model: ExecutionModel
    companion_capability_ids: list[str] = Field(default_factory=list)
    allowed_upstream_capability_kinds: list[str] = Field(default_factory=list)
    allowed_downstream_capability_kinds: list[str] = Field(default_factory=list)
    coordination_notes: str = ""


class ReasoningLogContractSpec(BaseModel):
    """Normalized reasoning-log sidecar contract for all agents."""

    model_config = ConfigDict(extra="forbid")

    format: str = "json+markdown"
    self_contained: bool = True
    default_root: str
    required_sections: list[str] = Field(default_factory=list)


class AgentContractSpec(BaseModel):
    """Full typed contract for one agent surface."""

    model_config = ConfigDict(extra="forbid")

    invocation: AgentInvocationSpec
    inputs: list[AgentPortSpec] = Field(default_factory=list)
    outputs: list[AgentPortSpec] = Field(default_factory=list)
    coordination: AgentCoordinationSpec
    reasoning_log: ReasoningLogContractSpec


class CapabilityContractSpec(BaseModel):
    """Full typed callable contract exported by a skill definition."""

    model_config = ConfigDict(extra="forbid")

    invocation: AgentInvocationSpec
    inputs: list[AgentPortSpec] = Field(default_factory=list)
    outputs: list[AgentPortSpec] = Field(default_factory=list)
    coordination: CapabilityCoordinationSpec
    reasoning_log: ReasoningLogContractSpec


def critic_agent_id(critic_id: str) -> str:
    """Return the manifest agent id for a critic spec."""
    return f"{critic_id}-agent"


def resolve_skill_capability_contract(skill: SkillSpec) -> CapabilityContractSpec:
    """Return the typed callable/port contract exported by a skill."""
    if skill.capability_contract is not None:
        return skill.capability_contract

    return CapabilityContractSpec(
        invocation=AgentInvocationSpec(
            mode="planner-routed",
            invocation_condition=skill.planner.invocation_condition
            or skill.description,
            primary_entrypoint="plan-fragment",
            execution_entrypoint="analyze-fragment",
            cadence="on demand",
            preconditions=list(skill.planner.use_cases),
            not_applicable_when=list(skill.planner.not_applicable_when),
        ),
        inputs=[
            AgentPortSpec(
                port_id="objective_context",
                payload_kind="objective-payload",
                transport="inline-json",
                description="Objective payload that frames the specialist analysis and carries the fragment, thesis, or question under evaluation.",
                json_schema=_objective_payload_schema(),
                semantic_type=_skill_objective_context_type(skill),
            ),
            AgentPortSpec(
                port_id="input_artifacts",
                payload_kind="artifact-payload-list",
                transport="artifact-ref-list",
                description="Primary upstream artifacts passed into the task envelope for direct analysis or transformation.",
                required=False,
                cardinality="many",
                json_schema=_artifact_list_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.collection.primary-input",
                    parent_type_ids=["artifact.collection", "artifact"],
                    facets={"selection_role": skill.planner.selection_role},
                ),
            ),
            AgentPortSpec(
                port_id="context_artifacts",
                payload_kind="artifact-context-list",
                transport="artifact-ref-list",
                description="Additional context artifacts available to the specialist when the current task depends on prior decomposition or nearby evidence.",
                required=False,
                cardinality="many",
                json_schema=_artifact_list_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.collection.context",
                    parent_type_ids=["artifact.collection", "artifact"],
                    facets={"selection_role": skill.planner.selection_role},
                ),
            ),
        ],
        outputs=[
            AgentPortSpec(
                port_id="analysis_artifact",
                payload_kind="structured-analysis-payload",
                transport="inline-json",
                description="Structured analytical payload emitted as the accepted result artifact for the current objective.",
                json_schema=skill.output_schema,
                semantic_type=_skill_analysis_output_type(skill),
            ),
            AgentPortSpec(
                port_id="scheme_instances",
                payload_kind="scheme-instance-list",
                transport="inline-json",
                description="Optional instantiated argumentation schemes derived from the structured output.",
                required=False,
                cardinality="many",
                json_schema=_scheme_instance_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.scheme-instances",
                    parent_type_ids=["artifact.collection", "artifact"],
                    facets={"selection_role": skill.planner.selection_role},
                ),
            ),
            AgentPortSpec(
                port_id="reasoning_log",
                payload_kind="reasoning-log",
                transport="sidecar",
                description="Self-contained reasoning log suitable for downstream inspection by external agents and IDE tooling.",
                path_hint="run_dir/agent_reasoning_logs",
                json_schema=_reasoning_log_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.reasoning-log",
                    parent_type_ids=["artifact.sidecar", "artifact"],
                    facets={"skill_id": skill.spec_id},
                ),
            ),
        ],
        coordination=CapabilityCoordinationSpec(
            organization_group="inference",
            lifecycle_stage="execution",
            role=skill.planner.selection_role,
            execution_model="single-step",
            companion_capability_ids=list(skill.planner.companion_skill_ids),
            allowed_upstream_capability_kinds=["skill", "critic"],
            allowed_downstream_capability_kinds=["skill", "critic"],
            coordination_notes=(
                "The planner selects this skill from natural-language routing cues; the contract makes its typed handoff explicit."
            ),
        ),
        reasoning_log=ReasoningLogContractSpec(
            default_root="run_dir/agent_reasoning_logs",
            required_sections=[
                "invocation",
                "input_summary",
                "reasoning_steps",
                "outputs",
                "open_questions",
                "remaining_uncertainty",
                "metadata_snapshot",
            ],
        ),
    )


def resolve_environment_agent_contract(
    agent: EnvironmentAgentSpec,
) -> AgentContractSpec:
    """Return the explicit or normalized typed contract for a maintenance agent."""
    if agent.agent_contract is not None:
        return agent.agent_contract

    invocation_modes: dict[str, InvocationMode] = {
        "task_completed": "task-hook",
        "task_threshold": "task-threshold",
        "macro_task_threshold": "macro-task-threshold",
    }
    invocation_mode = invocation_modes.get(agent.trigger_event, "task-hook")
    inputs = _environment_input_ports(agent)
    outputs = _environment_output_ports(agent)
    outputs.append(
        AgentPortSpec(
            port_id="reasoning_log",
            payload_kind="reasoning-log",
            transport="sidecar",
            description="Self-contained reasoning log describing the maintenance scan, findings, and actions.",
            path_hint="state/environment/reasoning_logs",
            json_schema=_reasoning_log_schema(),
            semantic_type=SemanticTypeRef(
                type_id="artifact.reasoning-log",
                parent_type_ids=["artifact.sidecar", "artifact"],
                facets={
                    "agent_id": agent.agent_id,
                    "organization_group": "maintenance",
                },
            ),
        )
    )
    return AgentContractSpec(
        invocation=AgentInvocationSpec(
            mode=invocation_mode,
            invocation_condition=agent.invocation_condition,
            primary_entrypoint="maintenance-sweep",
            execution_entrypoint="maintenance-sweep",
            trigger_event=agent.trigger_event,
            cadence=agent.cadence,
            threshold=agent.threshold,
            preconditions=list(agent.responsibilities),
        ),
        inputs=inputs,
        outputs=outputs,
        coordination=AgentCoordinationSpec(
            organization_group="maintenance",
            lifecycle_stage=(
                "post-task-maintenance"
                if agent.trigger_event != "macro_task_threshold"
                else "post-run-maintenance"
            ),
            role=_environment_role(agent.agent_id),
            execution_model="maintenance",
            allowed_upstream_agent_kinds=[
                "critic",
                "solver-success-critic",
                "environment-maintenance",
            ],
            allowed_downstream_agent_kinds=["environment-maintenance"],
            coordination_notes=(
                "Maintenance agents consume repository state and durable ledgers rather than prompt-local context. "
                "Their primary outputs are repository documents that survive the immediate solver run."
            ),
        ),
        reasoning_log=ReasoningLogContractSpec(
            default_root="state/environment/reasoning_logs",
            required_sections=[
                "invocation",
                "input_summary",
                "reasoning_steps",
                "outputs",
                "links",
                "metadata_snapshot",
            ],
        ),
    )


def resolve_critic_agent_contract(critic: CriticSpec) -> AgentContractSpec:
    """Return the explicit or normalized typed contract for a critic agent."""
    if critic.agent_contract is not None:
        return critic.agent_contract

    solver_success = "solver-success-evaluation" in critic.target_kinds
    if solver_success:
        inputs = [
            AgentPortSpec(
                port_id="scenario_bundle",
                payload_kind="solver-success-bundle",
                transport="inline-json",
                description="Scenario-level bundle combining plan selection, executed specialist traces, observed patterns, debt traces, and critic checks.",
                json_schema=_scenario_bundle_schema(
                    required_fields=critic.rules.get("required_bundle_fields", [])
                ),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.evaluation.scenario-bundle",
                    parent_type_ids=["artifact.evaluation", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            )
        ]
        outputs = [
            AgentPortSpec(
                port_id="critic_verdict",
                payload_kind="solver-success-verdict",
                transport="inline-json",
                description="Structured verdict for the scenario-level success criterion judged by this critic.",
                json_schema=critic.decision_schema,
                semantic_type=SemanticTypeRef(
                    type_id="artifact.evaluation.verdict",
                    parent_type_ids=["artifact.evaluation", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
            AgentPortSpec(
                port_id="reasoning_log",
                payload_kind="reasoning-log",
                transport="sidecar",
                description="Self-contained reasoning log describing the success judgment and supporting evidence.",
                path_hint="scenario_output/reasoning_logs",
                json_schema=_reasoning_log_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.reasoning-log",
                    parent_type_ids=["artifact.sidecar", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
        ]
        invocation = AgentInvocationSpec(
            mode="scenario-evaluation",
            invocation_condition=critic.description,
            primary_entrypoint="run-scenario-suite",
            execution_entrypoint="run-scenario-suite",
            cadence="on scenario evaluation",
            preconditions=(
                [str(critic.rules.get("assessment", "")).strip()]
                if critic.rules.get("assessment")
                else []
            ),
        )
        coordination = AgentCoordinationSpec(
            organization_group="evaluation",
            lifecycle_stage="scenario-evaluation",
            role="judge",
            execution_model="judge",
            allowed_upstream_agent_kinds=[],
            allowed_downstream_agent_kinds=["environment-maintenance"],
            coordination_notes=(
                "Solver-success critics judge whole coordinated runs rather than single steps. "
                "They should consume a scenario bundle only after execution traces are frozen."
            ),
        )
        reasoning_log = ReasoningLogContractSpec(
            default_root="scenario_output/reasoning_logs",
            required_sections=[
                "invocation",
                "input_summary",
                "reasoning_steps",
                "outputs",
                "metadata_snapshot",
            ],
        )
        return AgentContractSpec(
            invocation=invocation,
            inputs=inputs,
            outputs=outputs,
            coordination=coordination,
            reasoning_log=reasoning_log,
        )

    return AgentContractSpec(
        invocation=AgentInvocationSpec(
            mode="task-hook",
            invocation_condition=critic.description,
            execution_entrypoint="solve",
            cadence="after skill output is produced",
            preconditions=(
                [str(critic.rules.get("assessment", "")).strip()]
                if critic.rules.get("assessment")
                else []
            ),
        ),
        inputs=[
            AgentPortSpec(
                port_id="analysis_artifact",
                payload_kind="structured-analysis-payload",
                transport="inline-json",
                description="Structured skill output under critique.",
                json_schema={"type": "object"},
                semantic_type=SemanticTypeRef(
                    type_id="artifact.analysis",
                    parent_type_ids=["artifact.structured", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
            AgentPortSpec(
                port_id="diagnostics",
                payload_kind="diagnostic-list",
                transport="inline-json",
                description="Diagnostic signals assembled before the critic decision is formed.",
                required=False,
                cardinality="many",
                json_schema={"type": "array", "items": {"type": "object"}},
                semantic_type=SemanticTypeRef(
                    type_id="artifact.diagnostic-list",
                    parent_type_ids=["artifact.collection", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
        ],
        outputs=[
            AgentPortSpec(
                port_id="critic_decision",
                payload_kind="critic-decision",
                transport="inline-json",
                description="Structured critic decision that may accept, reject, request revision, or open debts.",
                json_schema=critic.decision_schema,
                semantic_type=SemanticTypeRef(
                    type_id="artifact.critic-decision",
                    parent_type_ids=["artifact.evaluation", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
            AgentPortSpec(
                port_id="reasoning_log",
                payload_kind="reasoning-log",
                transport="sidecar",
                description="Self-contained reasoning log explaining the critique outcome.",
                path_hint="run_dir/agent_reasoning_logs",
                json_schema=_reasoning_log_schema(),
                semantic_type=SemanticTypeRef(
                    type_id="artifact.reasoning-log",
                    parent_type_ids=["artifact.sidecar", "artifact"],
                    facets={"critic_id": critic.spec_id},
                ),
            ),
        ],
        coordination=AgentCoordinationSpec(
            organization_group="evaluation",
            lifecycle_stage="artifact-critique",
            role="judge",
            execution_model="judge",
            allowed_upstream_agent_kinds=[],
            allowed_downstream_agent_kinds=["environment-maintenance"],
            coordination_notes=(
                "Artifact critics are downstream judges over a single specialist output. "
                "They can reopen work, so they belong on the boundary between execution and repair."
            ),
        ),
        reasoning_log=ReasoningLogContractSpec(
            default_root="run_dir/agent_reasoning_logs",
            required_sections=[
                "invocation",
                "input_summary",
                "reasoning_steps",
                "outputs",
                "metadata_snapshot",
            ],
        ),
    )


def _objective_payload_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "fragment_text": {"type": "string"},
            "thesis": {"type": "string"},
            "question": {"type": "string"},
            "analysis_type": {"type": "string"},
        },
        "additionalProperties": True,
    }


def _artifact_list_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "payload": {"type": "object"},
                "origin": {"type": "object"},
            },
            "required": ["kind", "payload"],
        },
    }


def _scheme_instance_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "scheme_id": {"type": "string"},
                "conclusion": {"type": "string"},
                "premise_texts": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def _reasoning_log_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "agent_id": {"type": "string"},
            "agent_kind": {"type": "string"},
            "input_summary": {"type": "string"},
            "reasoning_steps": {"type": "array", "items": {"type": "string"}},
            "outputs_summary": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "agent_id",
            "agent_kind",
            "input_summary",
            "reasoning_steps",
            "outputs_summary",
        ],
    }


def _scenario_bundle_schema(*, required_fields: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required_fields),
        "properties": {
            "primary_skill_id": {"type": "string"},
            "supporting_skill_ids": {"type": "array", "items": {"type": "string"}},
            "execution_order": {"type": "array", "items": {"type": "string"}},
            "observed_patterns": {"type": "array", "items": {"type": "string"}},
            "expected_patterns": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    }


def _environment_input_ports(agent: EnvironmentAgentSpec) -> list[AgentPortSpec]:
    shared_ports = [
        AgentPortSpec(
            port_id="maintenance_state",
            payload_kind="maintenance-state",
            transport="inline-json",
            description="Persistent maintenance counters and checkpoints used to schedule periodic repository audits.",
            json_schema={
                "type": "object",
                "properties": {
                    "completed_task_count": {"type": "integer"},
                    "completed_macro_task_count": {"type": "integer"},
                },
                "required": ["completed_task_count", "completed_macro_task_count"],
            },
        ),
        AgentPortSpec(
            port_id="todo_ledger",
            payload_kind="todo-ledger",
            transport="document-link",
            description="Durable TODO ledger that maintenance agents extend, close, or remediate.",
            required=False,
            path_hint="TODO.md",
            json_schema=_document_link_schema(format_hint="markdown-checklist"),
        ),
    ]
    if agent.agent_id == "limitation-todo-capture":
        return [
            AgentPortSpec(
                port_id="task_execution_result",
                payload_kind="task-execution-result",
                transport="inline-json",
                description="Completed task result including the produced artifact, summary, unknowns, and suggested next steps.",
                json_schema={
                    "type": "object",
                    "properties": {
                        "task": {"type": "object"},
                        "artifact": {"type": "object"},
                        "backend_metadata": {"type": "object"},
                    },
                    "required": ["task", "artifact"],
                },
            ),
            AgentPortSpec(
                port_id="solver_state",
                payload_kind="solver-state",
                transport="inline-json",
                description="Current run state used to inspect active debts and connect TODOs back to the originating run.",
                json_schema={
                    "type": "object",
                    "properties": {"run_id": {"type": "string"}},
                },
            ),
            *shared_ports,
        ]

    repository_snapshot = AgentPortSpec(
        port_id="repository_snapshot",
        payload_kind="repository-snapshot",
        transport="state-ref",
        description="Repository-wide file snapshot used for heuristic audits and deterministic remediation.",
        path_hint="project_root",
        json_schema={
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "tracked_files": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["root"],
        },
    )
    if agent.agent_id == "todo-remediation":
        return [shared_ports[1], repository_snapshot, shared_ports[0]]
    return [repository_snapshot, *shared_ports]


def _environment_output_ports(agent: EnvironmentAgentSpec) -> list[AgentPortSpec]:
    ports: list[AgentPortSpec] = []
    for raw in agent.outputs:
        label, href = _parse_markdown_link(raw)
        payload_kind = _payload_kind_for_output(label=label, href=href)
        ports.append(
            AgentPortSpec(
                port_id=_slug(label or Path(href).stem or "output"),
                payload_kind=payload_kind,
                transport="document-link",
                description=f"Durable maintenance artifact written by `{agent.agent_id}`.",
                path_hint=href or None,
                json_schema=_document_link_schema(
                    format_hint=_format_hint_for_output(href=href)
                ),
            )
        )
    return ports


def _environment_role(agent_id: str) -> str:
    if "capture" in agent_id:
        return "capture"
    if "remediation" in agent_id:
        return "remediate"
    return "audit"


def _document_link_schema(*, format_hint: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "href": {"type": "string"},
            "format": {"type": "string", "default": format_hint},
        },
        "required": ["href"],
    }


def _parse_markdown_link(text: str) -> tuple[str, str]:
    match = re.match(r"^\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)$", text.strip())
    if not match:
        return text.strip(), text.strip()
    return match.group("label").strip(), match.group("href").strip()


def _payload_kind_for_output(*, label: str, href: str) -> str:
    lowered = f"{label} {href}".lower()
    if "todo" in lowered:
        return "todo-ledger"
    if "concept" in lowered and href.lower().endswith(".pdf"):
        return "concept-paper"
    if "report" in lowered or href.lower().endswith(".md"):
        return "maintenance-report"
    return "document"


def _format_hint_for_output(*, href: str) -> str:
    lowered = href.lower()
    if lowered.endswith(".pdf"):
        return "pdf"
    if lowered.endswith(".json"):
        return "json"
    return "markdown"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


def _skill_objective_context_type(skill: SkillSpec) -> SemanticTypeRef:
    material_inference_type = str(
        skill.contract.get("material_inference_type", "")
    ).strip()
    facets: dict[str, Any] = {
        "selection_role": skill.planner.selection_role,
        "objective_kinds": list(skill.objective_kinds),
    }
    if material_inference_type:
        facets["material_inference_type"] = material_inference_type
    return SemanticTypeRef(
        type_id="objective.context",
        parent_type_ids=["objective"],
        facets=facets,
    )


def _skill_analysis_output_type(skill: SkillSpec) -> SemanticTypeRef:
    if (
        skill.skill_type is not None
        and "analysis_artifact" in skill.skill_type.output_types
    ):
        return skill.skill_type.output_types["analysis_artifact"]
    material_inference_type = _slug(
        str(skill.contract.get("material_inference_type", "")).strip()
        or skill.planner.selection_role
    )
    facets: dict[str, Any] = {
        "skill_id": skill.spec_id,
        "selection_role": skill.planner.selection_role,
    }
    scheme_family = str(
        skill.contract.get("scheme_family", skill.prompt.get("scheme_family", ""))
    ).strip()
    if scheme_family:
        facets["scheme_family"] = scheme_family
    if skill.contract.get("material_inference_type"):
        facets["material_inference_type"] = str(
            skill.contract["material_inference_type"]
        )
    return SemanticTypeRef(
        type_id=f"artifact.analysis.{material_inference_type}",
        parent_type_ids=["artifact.analysis", "artifact.structured", "artifact"],
        facets=facets,
    )
