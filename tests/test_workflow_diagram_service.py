# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.platform.workflow.diagram.service import WorkflowDiagramService


def test_workflow_diagram_service_tracks_dependencies_for_parallel_joins(
    tmp_path: Path,
) -> None:
    diagram_path = tmp_path / "parallel_join.yaml"
    diagram_path.write_text(
        """
version: 1
name: parallel-join
entrypoint: start
sequence: |
  start ---> (left | right)
  [left,right]=>merge
nodes:
  start:
    tool: local.start
  left:
    tool: local.left
  right:
    tool: local.right
  merge:
    tool: local.merge
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(project_root=tmp_path)
    spec = service.load_diagram(diagram_path)

    dependencies = service.dependencies(spec)
    order = service.execution_order(spec)

    assert dependencies["start"] == set()
    assert dependencies["left"] == {"start"}
    assert dependencies["right"] == {"start"}
    assert dependencies["merge"] == {"left", "right"}
    assert order[0] == "start"
    assert order[-1] == "merge"


def test_workflow_diagram_service_executes_two_step_tool_chain(tmp_path: Path) -> None:
    diagram_path = tmp_path / "two_step.yaml"
    diagram_path.write_text(
        """
version: 1
name: two-step
entrypoint: first
sequence: |
  first ---> second
nodes:
  first:
    tool: local.first
    inputs:
      seed: ${flow.input.seed}
  second:
    tool: local.second
    inputs:
      previous: ${nodes.first.output.value}
      suffix: ${flow.input.suffix}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(
        project_root=tmp_path,
        tool_registry={
            "local.first": lambda inputs: {
                "output": {"value": f"{inputs['seed']}-alpha"}
            },
            "local.second": lambda inputs: {
                "output": {"value": f"{inputs['previous']}-{inputs['suffix']}"},
                "notes": ["Combined the previous node output with the flow suffix."],
            },
        },
    )

    result = service.execute(
        diagram_path=diagram_path,
        flow_inputs={"seed": "scenario10", "suffix": "beta"},
    )

    assert result.name == "two-step"
    assert result.terminal_node_ids == ["second"]
    assert result.final_output["value"] == "scenario10-alpha-beta"
    assert result.node_results[1].resolved_inputs["previous"] == "scenario10-alpha"
    assert "Combined the previous node output" in result.node_results[1].notes[-1]


def test_workflow_diagram_service_executes_agent_chain_with_node_expressions(
    tmp_path: Path,
) -> None:
    diagram_path = tmp_path / "agent_chain.yaml"
    diagram_path.write_text(
        """
version: 1
name: agent-chain
entrypoint: first
sequence: |
  first ---> second
nodes:
  first:
    agent: local.first
    inputs:
      fragment: ${flow.input.fragment}
  second:
    agent: local.second
    inputs:
      prior: ${nodes.first.output.summary}
      fragment: ${flow.input.fragment}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(project_root=tmp_path)
    result = service.execute(
        diagram_path=diagram_path,
        flow_inputs={"fragment": "expert testimony about the new intake protocol"},
        agent_executor=lambda agent_id, inputs: {
            "output": {
                "summary": f"{agent_id}:{inputs.get('fragment') or inputs.get('prior')}",
                "executed_skill_ids": [agent_id],
            }
        },
    )

    assert result.terminal_node_ids == ["second"]
    assert result.node_results[0].node_kind == "agent:local.first"
    assert (
        result.node_results[1].resolved_inputs["prior"]
        == "local.first:expert testimony about the new intake protocol"
    )
    assert result.final_output["executed_skill_ids"] == ["local.second"]


def test_workflow_diagram_service_resolves_declared_exports(tmp_path: Path) -> None:
    diagram_path = tmp_path / "exporting_chain.yaml"
    diagram_path.write_text(
        """
version: 1
name: exporting-chain
entrypoint: first
interface:
  exports:
    final_claim:
      kind: claim
      from: nodes.second.output.claim
    final_packet:
      kind: result
      from: nodes.second.output
sequence: |
  first ---> second
nodes:
  first:
    tool: local.first
    inputs:
      fragment: ${flow.input.fragment}
  second:
    tool: local.second
    inputs:
      prior: ${nodes.first.output.summary}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(
        project_root=tmp_path,
        tool_registry={
            "local.first": lambda inputs: {
                "output": {
                    "summary": f"first:{inputs['fragment']}",
                }
            },
            "local.second": lambda inputs: {
                "output": {
                    "claim": f"Claim from {inputs['prior']}",
                    "summary": "second-stage packet",
                    "answer": "second-stage packet",
                }
            },
        },
    )

    result = service.execute(
        diagram_path=diagram_path,
        flow_inputs={"fragment": "HER2 de-escalation evidence"},
    )

    assert result.exports["final_claim"].kind == "claim"
    assert (
        result.exports["final_claim"].value
        == "Claim from first:HER2 de-escalation evidence"
    )
    assert result.exports["final_packet"].kind == "result"
    assert result.exports["final_packet"].value["summary"] == "second-stage packet"


def test_workflow_diagram_service_accepts_typed_composition_policies(
    tmp_path: Path,
) -> None:
    diagram_path = tmp_path / "typed_composition.yaml"
    diagram_path.write_text(
        """
version: 1
name: typed-composition
entrypoint: planner
sequence: |
  planner ---> router
  router ---> (draft_a | draft_b)
  [draft_a,draft_b]=>merge
  merge ---> judge ---> resolver
nodes:
  planner:
    agent: local.planner
    composition:
      kind: delegation
      delegate_to: [draft_a, draft_b]
  router:
    tool: local.router
    composition:
      kind: branch
      branch_targets: [draft_a, draft_b]
  draft_a:
    tool: local.draft_a
  draft_b:
    tool: local.draft_b
  merge:
    tool: local.merge
    composition:
      kind: aggregation
      aggregation_sources: [draft_a, draft_b]
      aggregation_mode: append-evidence
  judge:
    agent: local.judge
    composition:
      kind: judge
      judge_role: quality-gate
  resolver:
    tool: local.resolve
    composition:
      kind: contradiction-resolution
      aggregation_sources: [draft_a, draft_b]
      contradiction_resolution: merge-with-uncertainty
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(
        project_root=tmp_path,
        tool_registry={
            "local.router": lambda inputs: {"output": {"route": "parallel"}},
            "local.draft_a": lambda inputs: {"output": {"summary": "draft-a"}},
            "local.draft_b": lambda inputs: {"output": {"summary": "draft-b"}},
            "local.merge": lambda inputs: {"output": {"summary": "merged"}},
            "local.resolve": lambda inputs: {"output": {"summary": "resolved"}},
        },
    )
    spec = service.load_diagram(diagram_path)

    result = service.execute(
        diagram_path=diagram_path,
        flow_inputs={},
        agent_executor=lambda agent_id, inputs: {"output": {"summary": agent_id}},
    )

    assert spec.nodes["planner"].composition is not None
    assert spec.nodes["planner"].composition.kind == "delegation"
    assert spec.nodes["router"].composition is not None
    assert spec.nodes["router"].composition.kind == "branch"
    assert spec.nodes["merge"].composition is not None
    assert spec.nodes["merge"].composition.kind == "aggregation"
    assert spec.nodes["judge"].composition is not None
    assert spec.nodes["judge"].composition.kind == "judge"
    assert spec.nodes["resolver"].composition is not None
    assert spec.nodes["resolver"].composition.kind == "contradiction-resolution"
    assert [node.node_id for node in result.node_results][:2] == ["planner", "router"]
    planner_result = next(
        node for node in result.node_results if node.node_id == "planner"
    )
    assert planner_result.output["delegated_targets"] == ["draft_a", "draft_b"]
    router_result = next(
        node for node in result.node_results if node.node_id == "router"
    )
    assert router_result.output["selected_targets"] == ["draft_a", "draft_b"]
    merge_result = next(node for node in result.node_results if node.node_id == "merge")
    assert merge_result.composition_kind == "aggregation"
    assert merge_result.output["aggregated_inputs"]["source_node_ids"] == [
        "draft_a",
        "draft_b",
    ]
    judge_result = next(node for node in result.node_results if node.node_id == "judge")
    assert judge_result.output["judge_packet"]["candidate_count"] == 1
    resolver_result = next(
        node for node in result.node_results if node.node_id == "resolver"
    )
    assert (
        resolver_result.output["contradiction_packet"]["resolution_mode"]
        == "merge-with-uncertainty"
    )


def test_workflow_diagram_service_executes_policy_only_branch_and_resolution_nodes(
    tmp_path: Path,
) -> None:
    diagram_path = tmp_path / "policy_only.yaml"
    diagram_path.write_text(
        """
version: 1
name: policy-only
entrypoint: router
sequence: |
  router ---> (left | right)
  [left,right]=>merge
  merge ---> judge ---> resolver
nodes:
  router:
    composition:
      kind: branch
      branch_targets: [left, right]
      condition: route_left
    inputs:
      route_left: ${flow.input.route_left}
  left:
    tool: local.left
  right:
    tool: local.right
  merge:
    composition:
      kind: aggregation
      aggregation_sources: [left, right]
      aggregation_mode: synthesize-children
  judge:
    composition:
      kind: judge
      judge_role: quality-gate
  resolver:
    composition:
      kind: contradiction-resolution
      aggregation_sources: [left, right]
      contradiction_resolution: merge-with-uncertainty
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = WorkflowDiagramService(
        project_root=tmp_path,
        tool_registry={
            "local.left": lambda inputs: {
                "output": {"summary": "left-candidate", "confidence": 0.9}
            },
            "local.right": lambda inputs: {
                "output": {"summary": "right-candidate", "confidence": 0.4}
            },
        },
    )

    result = service.execute(
        diagram_path=diagram_path,
        flow_inputs={"route_left": True},
    )

    router = next(node for node in result.node_results if node.node_id == "router")
    right = next(node for node in result.node_results if node.node_id == "right")
    merge = next(node for node in result.node_results if node.node_id == "merge")
    judge = next(node for node in result.node_results if node.node_id == "judge")
    resolver = next(node for node in result.node_results if node.node_id == "resolver")

    assert router.node_kind == "composition:branch"
    assert router.output["selected_targets"] == ["left"]
    assert right.skipped is True
    assert merge.node_kind == "composition:aggregation"
    assert merge.output["source_node_ids"] == ["left"]
    assert judge.output["selected_source"] == "merge"
    assert resolver.output["resolution_mode"] == "merge-with-uncertainty"
    assert result.final_output["resolution_mode"] == "merge-with-uncertainty"


def test_workflow_diagram_service_runs_refinement_loops_locally(tmp_path: Path) -> None:
    diagram_path = tmp_path / "refinement_loop.yaml"
    diagram_path.write_text(
        """
version: 1
name: refinement-loop
entrypoint: refine
sequence: |
  refine
nodes:
  refine:
    tool: local.refine
    composition:
      kind: refinement
      max_iterations: 3
      iteration_input: prior_output
      exit_when: accepted
""".strip()
        + "\n",
        encoding="utf-8",
    )

    attempts = {"count": 0}

    def refine(inputs):
        attempts["count"] += 1
        return {
            "output": {
                "accepted": attempts["count"] >= 2,
                "iteration": attempts["count"],
                "prior_seen": "prior_output" in inputs,
            }
        }

    service = WorkflowDiagramService(
        project_root=tmp_path, tool_registry={"local.refine": refine}
    )
    result = service.execute(diagram_path=diagram_path, flow_inputs={})

    node = result.node_results[0]
    assert node.composition_kind == "refinement"
    assert node.iteration_count == 2
    assert node.output["accepted"] is True
    assert node.output["iteration"] == 2
    assert node.output["prior_seen"] is True
