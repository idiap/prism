# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed diagram specifications and execution results."""

from __future__ import annotations

from typing import Any, Literal

from prism.platform.specs.aggregator_specs import ContradictionResolutionMode
from prism.platform.specs.semantic_types import MergeStrategy
from pydantic import BaseModel, ConfigDict, Field

WorkflowCompositionKind = Literal[
    "sequence",
    "branch",
    "loop",
    "refinement",
    "judge",
    "delegation",
    "aggregation",
    "contradiction-resolution",
]


class WorkflowCompositionPolicySpec(BaseModel):
    """Typed composition metadata attached to one rover workflow node.

    The existing rover `sequence` block remains the canonical graph shape. This
    policy layer explains *why* the node participates in that graph in a certain
    way: branching, refinement, judging, delegation, evidence aggregation, or
    contradiction handling.
    """

    model_config = ConfigDict(extra="forbid")

    kind: WorkflowCompositionKind
    condition: str | None = None
    branch_targets: list[str] = Field(default_factory=list)
    max_iterations: int = 1
    exit_when: str | None = None
    iteration_input: str | None = None
    delegate_to: list[str] = Field(default_factory=list)
    aggregation_sources: list[str] = Field(default_factory=list)
    aggregation_mode: MergeStrategy | Literal["arbitrate"] | None = None
    contradiction_resolution: ContradictionResolutionMode | None = None
    judge_role: str | None = None
    notes: list[str] = Field(default_factory=list)


class WorkflowDiagramNodeSpec(BaseModel):
    """One node declared in a diagrammatic workflow file."""

    model_config = ConfigDict(extra="allow")

    label: str | None = None
    agent: str | None = None
    tool: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    composition: WorkflowCompositionPolicySpec | None = None
    notes: list[str] = Field(default_factory=list)


class WorkflowDiagramExportSpec(BaseModel):
    """One declared export in a workflow interface contract."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    kind: str
    from_expression: str = Field(alias="from")
    label: str | None = None
    notes: list[str] = Field(default_factory=list)


class WorkflowDiagramInterfaceSpec(BaseModel):
    """Declared interface contract for a workflow diagram."""

    model_config = ConfigDict(extra="allow")

    modes: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    exports: dict[str, WorkflowDiagramExportSpec] = Field(default_factory=dict)


class WorkflowDiagramSpec(BaseModel):
    """A rover-style workflow diagram as used by PRISM."""

    model_config = ConfigDict(extra="allow")

    version: int | str = 1
    name: str
    entrypoint: str
    sequence: str
    nodes: dict[str, WorkflowDiagramNodeSpec] = Field(default_factory=dict)
    interface: WorkflowDiagramInterfaceSpec | None = None


class WorkflowDiagramNodeExecution(BaseModel):
    """One executed node inside a workflow diagram run."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_kind: str
    label: str
    composition_kind: str | None = None
    iteration_count: int = 1
    skipped: bool = False
    dependencies: list[str] = Field(default_factory=list)
    resolved_inputs: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class WorkflowDiagramRunResult(BaseModel):
    """Result bundle from executing one diagrammatic workflow."""

    model_config = ConfigDict(extra="forbid")

    name: str
    diagram_path: str
    entrypoint: str
    terminal_node_ids: list[str] = Field(default_factory=list)
    final_output: dict[str, Any] = Field(default_factory=dict)
    node_results: list[WorkflowDiagramNodeExecution] = Field(default_factory=list)
    exports: dict[str, "WorkflowDiagramResolvedExport"] = Field(default_factory=dict)


class WorkflowDiagramResolvedExport(BaseModel):
    """One resolved export surfaced from a workflow run."""

    model_config = ConfigDict(extra="forbid")

    export_name: str
    kind: str
    source_expression: str
    value: Any = None
    label: str | None = None
    notes: list[str] = Field(default_factory=list)


class _NormalizedNodeResult(BaseModel):
    """Internal normalized node result used by the workflow executor."""

    model_config = ConfigDict(extra="forbid")

    output: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
