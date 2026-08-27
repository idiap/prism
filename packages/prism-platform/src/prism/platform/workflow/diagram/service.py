# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform execution support for diagrammatic workflow files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
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


class WorkflowDiagramService:
    """Load, validate, and execute PRISM-local diagrammatic workflow files."""

    _EXPR_RE = re.compile(r"\$\{([^}]+)\}")

    def __init__(
        self,
        *,
        project_root: Path,
        tool_registry: (
            dict[
                str, Callable[[dict[str, Any]], dict[str, Any] | _NormalizedNodeResult]
            ]
            | None
        ) = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.tool_registry = dict(tool_registry or {})

    def load_diagram(self, path: Path) -> WorkflowDiagramSpec:
        """Load and validate one workflow diagram file."""
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Workflow diagram `{path}` must decode to a mapping.")
        spec = WorkflowDiagramSpec.model_validate(payload)
        self._validate_composition_policies(spec)
        return spec

    def execution_order(self, spec: WorkflowDiagramSpec) -> list[str]:
        """Return a deterministic topological execution order for the diagram."""
        dependencies = self.dependencies(spec)
        remaining = {
            node_id: set(required) for node_id, required in dependencies.items()
        }
        resolved: set[str] = set()
        ordered: list[str] = []

        while remaining:
            ready = sorted(
                node_id
                for node_id, required in remaining.items()
                if required.issubset(resolved)
            )
            if not ready:
                blocked = ", ".join(sorted(remaining))
                raise ValueError(
                    f"Workflow diagram `{spec.name}` has unresolved or cyclic dependencies: {blocked}"
                )
            for node_id in ready:
                ordered.append(node_id)
                resolved.add(node_id)
                remaining.pop(node_id, None)
        return ordered

    def dependencies(self, spec: WorkflowDiagramSpec) -> dict[str, set[str]]:
        """Compile the rover-style `sequence` block into dependency sets."""
        dependencies: dict[str, set[str]] = {}
        declared_nodes = set(spec.nodes)
        current_sources: list[str] = []

        def ensure_node(node_id: str) -> None:
            dependencies.setdefault(node_id, set())

        def register_target(target_text: str) -> list[str]:
            target_text = target_text.strip()
            if target_text.startswith("else=>"):
                target_text = target_text.removeprefix("else=>").strip()
            if " ? when:" in target_text:
                target_text = target_text.split(" ? when:", maxsplit=1)[0].strip()
            if target_text.startswith("(") and target_text.endswith(")"):
                targets = [
                    item.strip()
                    for item in target_text[1:-1].split("|")
                    if item.strip()
                ]
                for node_id in targets:
                    ensure_node(node_id)
                    dependencies[node_id].update(current_sources)
                return targets
            ensure_node(target_text)
            dependencies[target_text].update(current_sources)
            return [target_text]

        for raw_line in spec.sequence.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("[") and "]=>" in line:
                match = re.match(r"^\[(?P<sources>[^\]]+)\]=>\s*(?P<target>.+)$", line)
                if not match:
                    raise ValueError(
                        f"Invalid workflow join line in `{spec.name}`: {raw_line}"
                    )
                join_sources = [
                    item.strip()
                    for item in match.group("sources").split(",")
                    if item.strip()
                ]
                target = match.group("target").strip()
                ensure_node(target)
                dependencies[target].update(join_sources)
                current_sources = [target]
                continue
            if "--->" in line and not line.startswith("--->"):
                segments = [
                    segment.strip() for segment in line.split("--->") if segment.strip()
                ]
                current_sources = [segments[0]]
                ensure_node(segments[0])
                for segment in segments[1:]:
                    current_sources = register_target(segment)
                continue
            if line.startswith("--->"):
                if not current_sources:
                    raise ValueError(
                        f"Workflow arrow in `{spec.name}` has no current source: {raw_line}"
                    )
                current_sources = register_target(line.removeprefix("--->").strip())
                continue
            current_sources = [line]
            ensure_node(line)

        dependencies.setdefault(spec.entrypoint, set())
        unknown_nodes = [
            node_id
            for node_id in dependencies
            if declared_nodes and node_id not in declared_nodes
        ]
        if unknown_nodes:
            missing = ", ".join(sorted(unknown_nodes))
            raise ValueError(
                f"Workflow diagram `{spec.name}` references undeclared node(s): {missing}"
            )
        for node_id in declared_nodes:
            dependencies.setdefault(node_id, set())
        return dependencies

    def execute(
        self,
        *,
        diagram_path: Path,
        flow_inputs: dict[str, Any],
        agent_executor: (
            Callable[[str, dict[str, Any]], dict[str, Any] | _NormalizedNodeResult]
            | None
        ) = None,
        tool_executor: (
            Callable[[str, dict[str, Any]], dict[str, Any] | _NormalizedNodeResult]
            | None
        ) = None,
    ) -> WorkflowDiagramRunResult:
        """Execute a diagrammatic workflow with PRISM-provided node executors."""
        spec = self.load_diagram(diagram_path)
        dependencies = self.dependencies(spec)
        outgoing = self._outgoing_edges(dependencies)
        order = self.execution_order(spec)
        node_results: dict[str, WorkflowDiagramNodeExecution] = {}

        def run_tool(tool_name: str, inputs: dict[str, Any]) -> _NormalizedNodeResult:
            if tool_executor is not None:
                return self._normalize_result(tool_executor(tool_name, inputs))
            registered_executor = self.tool_registry.get(tool_name)
            if registered_executor is None:
                raise ValueError(
                    f"No workflow tool executor registered for `{tool_name}`."
                )
            return self._normalize_result(registered_executor(inputs))

        def run_agent(agent_id: str, inputs: dict[str, Any]) -> _NormalizedNodeResult:
            if agent_executor is None:
                raise ValueError(
                    f"No workflow agent executor registered for `{agent_id}`."
                )
            return self._normalize_result(agent_executor(agent_id, inputs))

        for node_id in order:
            node_spec = spec.nodes[node_id]
            base_inputs = self._resolve_value(
                node_spec.inputs,
                flow_inputs=flow_inputs,
                node_results=node_results,
            )
            skip_reason = self._skip_reason(
                node_id=node_id,
                spec=spec,
                dependencies=dependencies,
                node_results=node_results,
            )
            if skip_reason is not None:
                node_results[node_id] = WorkflowDiagramNodeExecution(
                    node_id=node_id,
                    node_kind="skipped",
                    label=node_spec.label or node_id,
                    composition_kind=(
                        node_spec.composition.kind
                        if node_spec.composition is not None
                        else None
                    ),
                    iteration_count=0,
                    skipped=True,
                    dependencies=sorted(dependencies.get(node_id, set())),
                    resolved_inputs=base_inputs,
                    output={"skipped": True, "skip_reason": skip_reason},
                    notes=[*node_spec.notes, skip_reason],
                )
                continue
            upstream_results = {
                source_id: node_results[source_id]
                for source_id in sorted(dependencies.get(node_id, set()))
                if source_id in node_results
            }
            resolved_inputs, normalized, node_kind, iteration_count = (
                self._execute_node(
                    node_id=node_id,
                    node_spec=node_spec,
                    resolved_inputs=base_inputs,
                    upstream_results=upstream_results,
                    downstream_nodes=sorted(outgoing.get(node_id, set())),
                    run_tool=run_tool,
                    run_agent=run_agent,
                )
            )
            node_results[node_id] = WorkflowDiagramNodeExecution(
                node_id=node_id,
                node_kind=node_kind,
                label=node_spec.label or node_id,
                composition_kind=(
                    node_spec.composition.kind
                    if node_spec.composition is not None
                    else None
                ),
                iteration_count=iteration_count,
                skipped=False,
                dependencies=sorted(dependencies.get(node_id, set())),
                resolved_inputs=resolved_inputs,
                output=normalized.output,
                notes=[
                    *node_spec.notes,
                    *(
                        node_spec.composition.notes
                        if node_spec.composition is not None
                        else []
                    ),
                    *normalized.notes,
                ],
            )

        terminal_nodes = sorted(
            node_id
            for node_id in order
            if all(
                node_id not in requirements
                for candidate, requirements in dependencies.items()
                if candidate != node_id
            )
        )
        active_terminal_nodes = [
            node_id for node_id in terminal_nodes if not node_results[node_id].skipped
        ]
        final_output = (
            node_results[(active_terminal_nodes or terminal_nodes)[-1]].output
            if terminal_nodes
            else {}
        )
        resolved_exports = self._resolve_declared_exports(
            spec=spec,
            flow_inputs=flow_inputs,
            node_results=node_results,
        )
        return WorkflowDiagramRunResult(
            name=spec.name,
            diagram_path=str(diagram_path),
            entrypoint=spec.entrypoint,
            terminal_node_ids=terminal_nodes,
            final_output=final_output,
            node_results=[node_results[node_id] for node_id in order],
            exports=resolved_exports,
        )

    def _execute_node(
        self,
        *,
        node_id: str,
        node_spec: WorkflowDiagramNodeSpec,
        resolved_inputs: dict[str, Any],
        upstream_results: dict[str, WorkflowDiagramNodeExecution],
        downstream_nodes: list[str],
        run_tool: Callable[[str, dict[str, Any]], _NormalizedNodeResult],
        run_agent: Callable[[str, dict[str, Any]], _NormalizedNodeResult],
    ) -> tuple[dict[str, Any], _NormalizedNodeResult, str, int]:
        """Execute one workflow node, including lightweight refinement loops.

        Rover remains DAG-based. Loop and refinement stay local to a node, while
        the other composition kinds now also change runtime behavior through
        policy inputs, activation control, or policy-only synthesis nodes.
        """

        def invoke(node_inputs: dict[str, Any]) -> tuple[_NormalizedNodeResult, str]:
            if node_spec.tool:
                return run_tool(node_spec.tool, node_inputs), f"tool:{node_spec.tool}"
            if node_spec.agent:
                return (
                    run_agent(node_spec.agent, node_inputs),
                    f"agent:{node_spec.agent}",
                )
            raise ValueError(
                "Workflow node must declare `tool` or `agent`, or use a policy-only composition node."
            )

        policy = node_spec.composition
        policy_inputs = self._policy_runtime_inputs(
            node_id=node_id,
            policy=policy,
            resolved_inputs=resolved_inputs,
            upstream_results=upstream_results,
            downstream_nodes=downstream_nodes,
        )
        effective_inputs = {
            **resolved_inputs,
            **{
                key: value
                for key, value in policy_inputs.items()
                if key not in resolved_inputs
            },
        }

        if policy is None:
            normalized, node_kind = invoke(effective_inputs)
            return effective_inputs, normalized, node_kind, 1

        if policy.kind in {
            "branch",
            "delegation",
            "aggregation",
            "judge",
            "contradiction-resolution",
        } and not (node_spec.tool or node_spec.agent):
            normalized = self._execute_policy_only_node(
                node_id=node_id,
                policy=policy,
                policy_inputs=policy_inputs,
            )
            return effective_inputs, normalized, f"composition:{policy.kind}", 1

        if policy.kind not in {"loop", "refinement"}:
            normalized, node_kind = invoke(effective_inputs)
            normalized = self._merge_policy_output(
                policy=policy, normalized=normalized, policy_inputs=policy_inputs
            )
            return effective_inputs, normalized, node_kind, 1

        if policy.max_iterations < 2:
            raise ValueError(
                f"Workflow node `{node_spec.label or '<unnamed>'}` declares `{policy.kind}` composition "
                "but does not allow at least two iterations."
            )

        current_inputs = dict(effective_inputs)
        normalized: _NormalizedNodeResult | None = None
        node_kind = ""
        notes: list[str] = []
        for iteration in range(1, policy.max_iterations + 1):
            if iteration > 1 and policy.iteration_input:
                current_inputs[policy.iteration_input] = (
                    normalized.output if normalized is not None else {}
                )
            normalized, node_kind = invoke(current_inputs)
            notes.append(f"Completed {policy.kind} iteration {iteration}.")
            if policy.exit_when and self._resolve_iteration_exit(
                policy.exit_when, normalized.output
            ):
                notes.append(
                    f"Exited {policy.kind} loop because `{policy.exit_when}` became truthy."
                )
                normalized = self._merge_policy_output(
                    policy=policy,
                    normalized=_NormalizedNodeResult(
                        output=normalized.output, notes=[*normalized.notes, *notes]
                    ),
                    policy_inputs=policy_inputs,
                )
                return current_inputs, normalized, node_kind, iteration
        if normalized is None:
            raise RuntimeError(
                f"Workflow node `{node_spec.label or '<unnamed>'}` completed no "
                "iterations."
            )
        normalized = self._merge_policy_output(
            policy=policy,
            normalized=_NormalizedNodeResult(
                output=normalized.output, notes=[*normalized.notes, *notes]
            ),
            policy_inputs=policy_inputs,
        )
        return current_inputs, normalized, node_kind, policy.max_iterations

    def _resolve_declared_exports(
        self,
        *,
        spec: WorkflowDiagramSpec,
        flow_inputs: dict[str, Any],
        node_results: dict[str, WorkflowDiagramNodeExecution],
    ) -> dict[str, WorkflowDiagramResolvedExport]:
        exports = spec.interface.exports if spec.interface is not None else {}
        resolved: dict[str, WorkflowDiagramResolvedExport] = {}
        for export_name, export_spec in exports.items():
            expression = export_spec.from_expression.strip()
            if expression.startswith("${") and expression.endswith("}"):
                expression = expression[2:-1].strip()
            value = self._resolve_expression(
                expression,
                flow_inputs=flow_inputs,
                node_results=node_results,
            )
            if value is None:
                raise ValueError(
                    f"Workflow export `{export_name}` in `{spec.name}` did not resolve a value from `{export_spec.from_expression}`."
                )
            resolved[export_name] = WorkflowDiagramResolvedExport(
                export_name=export_name,
                kind=export_spec.kind,
                source_expression=expression,
                value=value,
                label=export_spec.label,
                notes=list(export_spec.notes),
            )
        return resolved

    def _normalize_result(
        self, result: dict[str, Any] | _NormalizedNodeResult
    ) -> _NormalizedNodeResult:
        if isinstance(result, _NormalizedNodeResult):
            return result
        if not isinstance(result, dict):
            raise ValueError("Workflow node executors must return a mapping result.")
        notes = result.get("notes", [])
        output = result.get("output", result)
        if not isinstance(output, dict):
            output = {"value": output}
        return _NormalizedNodeResult(
            output=output,
            notes=list(notes) if isinstance(notes, list) else [str(notes)],
        )

    def _resolve_value(
        self,
        value: Any,
        *,
        flow_inputs: dict[str, Any],
        node_results: dict[str, WorkflowDiagramNodeExecution],
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: self._resolve_value(
                    item, flow_inputs=flow_inputs, node_results=node_results
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve_value(
                    item, flow_inputs=flow_inputs, node_results=node_results
                )
                for item in value
            ]
        if not isinstance(value, str):
            return value
        match = re.fullmatch(self._EXPR_RE, value.strip())
        if match:
            return self._resolve_expression(
                match.group(1), flow_inputs=flow_inputs, node_results=node_results
            )

        def replace_expr(found: re.Match[str]) -> str:
            resolved = self._resolve_expression(
                found.group(1), flow_inputs=flow_inputs, node_results=node_results
            )
            if isinstance(resolved, (dict, list)):
                return yaml.safe_dump(resolved, sort_keys=False).strip()
            return "" if resolved is None else str(resolved)

        return self._EXPR_RE.sub(replace_expr, value)

    def _resolve_expression(
        self,
        expression: str,
        *,
        flow_inputs: dict[str, Any],
        node_results: dict[str, WorkflowDiagramNodeExecution],
    ) -> Any:
        parts = [part for part in expression.split(".") if part]
        if not parts:
            return None
        if parts[:2] == ["flow", "input"]:
            return self._walk(flow_inputs, parts[2:])
        if parts and parts[0] == "nodes" and len(parts) >= 3:
            node_id = parts[1]
            node = node_results.get(node_id)
            if node is None:
                raise ValueError(
                    f"Workflow expression references unresolved node `{node_id}`."
                )
            if parts[2] == "output":
                return self._walk(node.output, parts[3:])
            if parts[2] == "inputs":
                return self._walk(node.resolved_inputs, parts[3:])
            return self._walk(node.model_dump(mode="json"), parts[2:])
        raise ValueError(f"Unsupported workflow expression `${{{expression}}}`.")

    def _walk(self, value: Any, parts: list[str]) -> Any:
        current = value
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                continue
            if isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else None
                continue
            return None
        return current

    def _validate_composition_policies(self, spec: WorkflowDiagramSpec) -> None:
        """Validate typed composition policies against the rover graph shape."""
        dependencies = self.dependencies(spec)
        outgoing = self._outgoing_edges(dependencies)
        for node_id, node_spec in spec.nodes.items():
            policy = node_spec.composition
            if policy is None:
                continue
            downstream = sorted(outgoing.get(node_id, set()))
            upstream = sorted(dependencies.get(node_id, set()))
            if policy.kind == "sequence":
                continue
            if policy.kind == "branch":
                branch_targets = policy.branch_targets or downstream
                self._ensure_known_nodes(
                    spec=spec,
                    node_id=node_id,
                    target_ids=branch_targets,
                    label="branch targets",
                )
                if len(branch_targets) < 2:
                    raise ValueError(
                        f"Workflow node `{node_id}` must branch to at least two targets."
                    )
                continue
            if policy.kind in {"loop", "refinement"}:
                if policy.max_iterations < 2:
                    raise ValueError(
                        f"Workflow node `{node_id}` must allow at least two iterations for `{policy.kind}`."
                    )
                continue
            if policy.kind == "delegation":
                delegate_to = policy.delegate_to or downstream
                self._ensure_known_nodes(
                    spec=spec,
                    node_id=node_id,
                    target_ids=delegate_to,
                    label="delegation targets",
                )
                if not delegate_to:
                    raise ValueError(
                        f"Workflow node `{node_id}` declares delegation without any delegate targets."
                    )
                continue
            if policy.kind in {"aggregation", "contradiction-resolution"}:
                sources = policy.aggregation_sources or upstream
                self._ensure_known_nodes(
                    spec=spec,
                    node_id=node_id,
                    target_ids=sources,
                    label="aggregation sources",
                )
                if len(sources) < 2:
                    raise ValueError(
                        f"Workflow node `{node_id}` requires at least two upstream sources for `{policy.kind}`."
                    )
                continue
            if policy.kind == "judge" and not upstream:
                raise ValueError(
                    f"Workflow node `{node_id}` cannot act as a judge without any upstream evidence."
                )

    def _outgoing_edges(self, dependencies: dict[str, set[str]]) -> dict[str, set[str]]:
        outgoing = {node_id: set() for node_id in dependencies}
        for target, sources in dependencies.items():
            for source in sources:
                outgoing.setdefault(source, set()).add(target)
        return outgoing

    def _ensure_known_nodes(
        self,
        *,
        spec: WorkflowDiagramSpec,
        node_id: str,
        target_ids: list[str],
        label: str,
    ) -> None:
        unknown = sorted(target for target in target_ids if target not in spec.nodes)
        if unknown:
            raise ValueError(
                f"Workflow node `{node_id}` references unknown {label}: {unknown}"
            )

    def _resolve_iteration_exit(self, expression: str, output: dict[str, Any]) -> bool:
        value = self._walk(output, [part for part in expression.split(".") if part])
        return bool(value)

    def _skip_reason(
        self,
        *,
        node_id: str,
        spec: WorkflowDiagramSpec,
        dependencies: dict[str, set[str]],
        node_results: dict[str, WorkflowDiagramNodeExecution],
    ) -> str | None:
        direct_sources = sorted(dependencies.get(node_id, set()))
        explicit_skip_reasons: list[str] = []
        for source_id in direct_sources:
            source_result = node_results.get(source_id)
            if source_result is None:
                continue
            if source_result.skipped:
                continue
            source_spec = spec.nodes[source_id]
            source_policy = source_spec.composition
            if source_policy is None:
                continue
            outgoing_targets = sorted(
                target
                for target, requirements in dependencies.items()
                if source_id in requirements
            )
            if source_policy.kind == "branch":
                branch_targets = source_policy.branch_targets or outgoing_targets
                if node_id in branch_targets:
                    selected_targets = source_result.output.get("selected_targets", [])
                    if (
                        isinstance(selected_targets, list)
                        and node_id not in selected_targets
                    ):
                        explicit_skip_reasons.append(
                            f"Skipped because branch node `{source_id}` routed away from `{node_id}`."
                        )
            if source_policy.kind == "delegation":
                delegate_targets = source_policy.delegate_to or outgoing_targets
                if node_id in delegate_targets:
                    delegated_targets = source_result.output.get(
                        "delegated_targets", []
                    )
                    if (
                        isinstance(delegated_targets, list)
                        and node_id not in delegated_targets
                    ):
                        explicit_skip_reasons.append(
                            f"Skipped because delegation node `{source_id}` did not activate `{node_id}`."
                        )
        if explicit_skip_reasons:
            return explicit_skip_reasons[0]
        if direct_sources and all(
            node_results.get(source_id) and node_results[source_id].skipped
            for source_id in direct_sources
        ):
            return "Skipped because every direct dependency was inactive."
        return None

    def _policy_runtime_inputs(
        self,
        *,
        node_id: str,
        policy: WorkflowCompositionPolicySpec | None,
        resolved_inputs: dict[str, Any],
        upstream_results: dict[str, WorkflowDiagramNodeExecution],
        downstream_nodes: list[str],
    ) -> dict[str, Any]:
        upstream_packets = [
            {
                "node_id": upstream.node_id,
                "label": upstream.label,
                "output": upstream.output,
                "notes": upstream.notes,
                "skipped": upstream.skipped,
            }
            for upstream in upstream_results.values()
            if not upstream.skipped
        ]
        if policy is None:
            return {"upstream_results": upstream_packets} if upstream_packets else {}

        if policy.kind == "branch":
            targets = policy.branch_targets or downstream_nodes
            selected_targets = self._selected_targets(
                targets=targets,
                condition=policy.condition,
                resolved_inputs=resolved_inputs,
                fallback="all",
            )
            return {
                "selected_targets": selected_targets,
                "skipped_targets": [
                    target for target in targets if target not in selected_targets
                ],
                "branch_taken": (
                    selected_targets[0] if len(selected_targets) == 1 else "all"
                ),
                "upstream_results": upstream_packets,
            }

        if policy.kind == "delegation":
            targets = policy.delegate_to or downstream_nodes
            delegated_targets = self._selected_targets(
                targets=targets,
                condition=policy.condition,
                resolved_inputs=resolved_inputs,
                fallback="all",
            )
            return {
                "delegated_targets": delegated_targets,
                "delegate_packets": [
                    {
                        "target": target,
                        "brief": f"Delegated from `{node_id}`.",
                    }
                    for target in delegated_targets
                ],
                "upstream_results": upstream_packets,
            }

        if policy.kind in {"aggregation", "judge", "contradiction-resolution"}:
            source_ids = policy.aggregation_sources or list(upstream_results)
            source_packets = [
                {
                    "node_id": source_id,
                    "label": upstream_results[source_id].label,
                    "output": upstream_results[source_id].output,
                }
                for source_id in source_ids
                if source_id in upstream_results
                and not upstream_results[source_id].skipped
            ]
            payload: dict[str, Any] = {
                "source_packets": source_packets,
                "upstream_results": upstream_packets,
            }
            if policy.kind == "aggregation":
                payload["aggregated_inputs"] = self._aggregate_sources(
                    source_packets=source_packets,
                    mode=policy.aggregation_mode or "append-evidence",
                )
            elif policy.kind == "judge":
                payload["judge_packet"] = self._judge_sources(
                    source_packets=source_packets,
                    judge_role=policy.judge_role,
                )
            else:
                payload["contradiction_packet"] = self._resolve_contradictions(
                    source_packets=source_packets,
                    mode=policy.contradiction_resolution or "preserve-all",
                )
            return payload

        return {"upstream_results": upstream_packets}

    def _execute_policy_only_node(
        self,
        *,
        node_id: str,
        policy: WorkflowCompositionPolicySpec,
        policy_inputs: dict[str, Any],
    ) -> _NormalizedNodeResult:
        if policy.kind == "branch":
            selected_targets = list(policy_inputs.get("selected_targets", []))
            skipped_targets = list(policy_inputs.get("skipped_targets", []))
            return _NormalizedNodeResult(
                output={
                    "summary": (
                        f"Branch node `{node_id}` selected {', '.join(selected_targets)}."
                        if selected_targets
                        else f"Branch node `{node_id}` selected no downstream targets."
                    ),
                    **policy_inputs,
                },
                notes=[
                    f"Evaluated branch policy for `{node_id}`.",
                    f"Skipped targets: {', '.join(skipped_targets) if skipped_targets else 'none'}.",
                ],
            )
        if policy.kind == "delegation":
            delegated_targets = list(policy_inputs.get("delegated_targets", []))
            return _NormalizedNodeResult(
                output={
                    "summary": f"Delegation node `{node_id}` activated {len(delegated_targets)} delegate target(s).",
                    **policy_inputs,
                },
                notes=[
                    f"Delegated to: {', '.join(delegated_targets) if delegated_targets else 'none'}."
                ],
            )
        if policy.kind == "aggregation":
            aggregated_inputs = dict(policy_inputs.get("aggregated_inputs", {}))
            return _NormalizedNodeResult(
                output={
                    "summary": aggregated_inputs.get("summary")
                    or f"Aggregated {len(aggregated_inputs.get('source_node_ids', []))} source node(s).",
                    **aggregated_inputs,
                },
                notes=[
                    "Synthesized aggregation output directly from upstream workflow results."
                ],
            )
        if policy.kind == "judge":
            judge_packet = dict(policy_inputs.get("judge_packet", {}))
            return _NormalizedNodeResult(
                output={
                    "summary": judge_packet.get("summary")
                    or f"Judge node `{node_id}` evaluated upstream evidence.",
                    **judge_packet,
                },
                notes=[
                    "Synthesized judge output directly from upstream workflow results."
                ],
            )
        contradiction_packet = dict(policy_inputs.get("contradiction_packet", {}))
        return _NormalizedNodeResult(
            output={
                "summary": contradiction_packet.get("summary")
                or f"Contradiction-resolution node `{node_id}` reconciled upstream evidence.",
                **contradiction_packet,
            },
            notes=[
                "Synthesized contradiction handling directly from upstream workflow results."
            ],
        )

    def _merge_policy_output(
        self,
        *,
        policy: WorkflowCompositionPolicySpec,
        normalized: _NormalizedNodeResult,
        policy_inputs: dict[str, Any],
    ) -> _NormalizedNodeResult:
        output = dict(normalized.output)
        if policy.kind == "branch":
            output.setdefault(
                "selected_targets", list(policy_inputs.get("selected_targets", []))
            )
            output.setdefault(
                "skipped_targets", list(policy_inputs.get("skipped_targets", []))
            )
            output.setdefault("branch_taken", policy_inputs.get("branch_taken"))
        elif policy.kind == "delegation":
            output.setdefault(
                "delegated_targets", list(policy_inputs.get("delegated_targets", []))
            )
            output.setdefault(
                "delegate_packets", list(policy_inputs.get("delegate_packets", []))
            )
        elif policy.kind == "aggregation":
            output.setdefault(
                "aggregated_inputs", policy_inputs.get("aggregated_inputs")
            )
        elif policy.kind == "judge":
            output.setdefault("judge_packet", policy_inputs.get("judge_packet"))
        elif policy.kind == "contradiction-resolution":
            output.setdefault(
                "contradiction_packet", policy_inputs.get("contradiction_packet")
            )
        return _NormalizedNodeResult(output=output, notes=list(normalized.notes))

    def _selected_targets(
        self,
        *,
        targets: list[str],
        condition: str | None,
        resolved_inputs: dict[str, Any],
        fallback: Literal["all", "last"] = "all",
    ) -> list[str]:
        if not targets:
            return []
        if not condition:
            return list(targets)
        is_truthy = self._evaluate_condition(
            condition=condition, resolved_inputs=resolved_inputs
        )
        if len(targets) == 1:
            return list(targets) if is_truthy else []
        if is_truthy:
            return [targets[0]]
        if fallback == "last":
            return [targets[-1]]
        return list(targets[1:]) or [targets[-1]]

    def _evaluate_condition(
        self, *, condition: str, resolved_inputs: dict[str, Any]
    ) -> bool:
        expression = condition.strip()
        negate = False
        if expression.startswith("not "):
            negate = True
            expression = expression[4:].strip()
        elif expression.startswith("!"):
            negate = True
            expression = expression[1:].strip()

        if "==" in expression:
            left, right = [part.strip() for part in expression.split("==", maxsplit=1)]
            left_value = (
                self._walk(resolved_inputs, [part for part in left.split(".") if part])
                if "." in left
                else resolved_inputs.get(left)
            )
            verdict = str(left_value) == right.strip("\"'")
            return not verdict if negate else verdict

        value = (
            self._walk(
                resolved_inputs, [part for part in expression.split(".") if part]
            )
            if "." in expression
            else resolved_inputs.get(expression)
        )
        verdict = bool(value)
        return not verdict if negate else verdict

    def _aggregate_sources(
        self,
        *,
        source_packets: list[dict[str, Any]],
        mode: MergeStrategy | Literal["arbitrate"],
    ) -> dict[str, Any]:
        source_node_ids = [packet["node_id"] for packet in source_packets]
        if mode == "latest-wins":
            latest_output = dict(source_packets[-1]["output"]) if source_packets else {}
            latest_output.setdefault("source_node_ids", source_node_ids)
            latest_output.setdefault(
                "summary",
                (
                    f"Latest-wins merge kept `{source_node_ids[-1]}`."
                    if source_node_ids
                    else "No sources were available."
                ),
            )
            return latest_output

        if mode in {"bundle-for-critic", "arbitrate"}:
            return {
                "summary": f"Bundled {len(source_packets)} candidate output(s) for downstream review.",
                "candidates": source_packets,
                "source_node_ids": source_node_ids,
                "arbitration_required": mode == "arbitrate",
            }

        if mode == "synthesize-children":
            summaries = [
                str(packet["output"].get("summary") or packet["node_id"]).strip()
                for packet in source_packets
            ]
            return {
                "summary": " | ".join(summary for summary in summaries if summary)
                or "No child summaries were available.",
                "children": {
                    packet["node_id"]: packet["output"] for packet in source_packets
                },
                "source_node_ids": source_node_ids,
            }

        aggregated: dict[str, Any] = {
            "summary": f"Aggregated {len(source_packets)} upstream source(s).",
            "source_node_ids": source_node_ids,
        }
        for list_key in ["evidence", "claims", "counter_claims", "notes"]:
            items: list[Any] = []
            for packet in source_packets:
                value = packet["output"].get(list_key)
                if isinstance(value, list):
                    items.extend(value)
            if items:
                aggregated[list_key] = items
        return aggregated

    def _judge_sources(
        self,
        *,
        source_packets: list[dict[str, Any]],
        judge_role: str | None,
    ) -> dict[str, Any]:
        if not source_packets:
            return {
                "summary": "Judge received no upstream evidence.",
                "selected_source": None,
                "candidate_count": 0,
                "judge_role": judge_role,
            }

        def score(packet: dict[str, Any]) -> float:
            output = packet.get("output", {})
            if isinstance(output.get("confidence"), (int, float)):
                return float(output["confidence"])
            if isinstance(output.get("score"), (int, float)):
                return float(output["score"])
            summary = str(output.get("summary") or "").strip()
            return float(len(summary))

        best = max(source_packets, key=score)
        return {
            "summary": f"Judge selected `{best['node_id']}` as the strongest upstream candidate.",
            "selected_source": best["node_id"],
            "selected_output": best["output"],
            "candidate_count": len(source_packets),
            "judge_role": judge_role,
        }

    def _resolve_contradictions(
        self,
        *,
        source_packets: list[dict[str, Any]],
        mode: ContradictionResolutionMode,
    ) -> dict[str, Any]:
        summaries = {
            packet["node_id"]: str(
                packet["output"].get("summary")
                or packet["output"].get("answer")
                or packet["output"]
            ).strip()
            for packet in source_packets
        }
        distinct_summaries = {summary for summary in summaries.values() if summary}
        conflicts = list(summaries) if len(distinct_summaries) > 1 else []

        if mode == "fail-fast" and conflicts:
            raise ValueError(
                f"Contradiction-resolution policy encountered conflicting sources: {', '.join(conflicts)}"
            )

        if mode == "latest-wins" and source_packets:
            latest_output = dict(source_packets[-1]["output"])
            latest_output.setdefault("resolution_mode", mode)
            latest_output.setdefault("conflicts", conflicts)
            latest_output.setdefault(
                "summary",
                f"Latest-wins contradiction handling kept `{source_packets[-1]['node_id']}`.",
            )
            return latest_output

        if mode == "prefer-judge" and source_packets:
            judged = self._judge_sources(
                source_packets=source_packets, judge_role="contradiction-resolution"
            )
            return {
                "summary": judged["summary"],
                "selected_source": judged["selected_source"],
                "selected_output": judged["selected_output"],
                "resolution_mode": mode,
                "conflicts": conflicts,
            }

        if mode == "merge-with-uncertainty":
            return {
                "summary": (
                    f"Merged {len(source_packets)} conflicting candidate(s) with explicit uncertainty."
                    if conflicts
                    else "Merged upstream evidence without detected contradiction."
                ),
                "resolution_mode": mode,
                "conflicts": conflicts,
                "candidates": source_packets,
                "uncertainty": (
                    []
                    if not conflicts
                    else ["Conflicting upstream summaries were preserved explicitly."]
                ),
            }

        return {
            "summary": (
                f"Preserved all {len(source_packets)} candidate output(s) because contradictions remained live."
                if conflicts
                else "Preserved upstream evidence without detected contradiction."
            ),
            "resolution_mode": mode,
            "conflicts": conflicts,
            "candidates": source_packets,
        }
