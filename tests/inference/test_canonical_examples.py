# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

import pytest
from prism.language import InMemoryModuleLoader, check, compile, elaborate, parse_source
from prism.language.core import (
    ASSURANCE_TYPES,
    PROVENANCE_TYPES,
    ComputedValue,
    CoreType,
    GeneratedValue,
    Ok,
    ValidatedValue,
)
from prism.language.effects import (
    CallExpression,
    EffectContractError,
    EffectRequest,
    EffectResult,
    ExecutableProgram,
    FunctionDefinition,
    Try,
    ValueBinding,
)
from prism.runtime import FakeEffectHandler, run
from prism.runtime.engine import _Engine
from prism.sdk.workspace import WorkspaceModuleLoader

ROOT = Path(__file__).resolve().parents[2]


def _compile(path: Path):
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    program = parse_source(path.read_text(encoding="utf-8"), path=str(path))
    return compile(elaborate(check(program, module_loader=loader)))


def _fake_handler() -> FakeEffectHandler:
    return FakeEffectHandler()


def test_strict_inference_carries_a_kernel_proof_across_its_relation() -> None:
    executable = _compile(ROOT / "examples/language/strict_inference/main.prism")

    output = run(executable, handler=FakeEffectHandler())

    assert output.status == "accepted"
    assert output.result == Ok(7)
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.name == "ApprovesRelease"
    assert relation.metadata["certificate_type"] == (
        "Proof[SameVersion(deployed, approved)]"
    )


def test_refinement_loop_materializes_abductive_deductive_refinement() -> None:
    path = ROOT / "examples/language/refinement_loop/reasoning.prism"
    source = path.read_text(encoding="utf-8")
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    checked = check(
        parse_source(source, path=str(path)),
        module_loader=loader,
    )

    methods = checked.reasoning_methods["LunarLandingRefinement"]
    assert tuple(methods) == ("candidate", "finding", "source", "safe_plan")
    candidate_result = methods["candidate"].result
    assert candidate_result is not None
    assert candidate_result.render() == (
        "Validated[value: Computed[PlanHypothesis], PlanWellFormed(value)]"
    )
    finding_result = methods["finding"].result
    assert finding_result is not None
    assert finding_result.name == "LandingAssessment"
    source_result = methods["source"].result
    assert source_result is not None
    assert source_result.render() == (
        "AbductionInput[Validated[value: MissionConstraints, "
        "MissionAccepted(value)], Evidence[PlanHypothesis]]"
    )
    safe_plan_result = methods["safe_plan"].result
    assert safe_plan_result is not None
    assert safe_plan_result.render() == (
        "Validated[value:Computed[PlanHypothesis], SafeUnderModel(value)]"
    )
    assert checked.callable_contracts[
        "SupportTrajectoryHypothesis"
    ].result.render() == (
        "Supported[PlausiblyExplainsFeedback(source.background.value, target.value, "
        "source.observation.value)]"
    )
    assert "until = finding.accepted" in source
    assert "candidate: Abductive[" in source
    assert "finding: Deductive[" in source
    assert "DeductionInput(context = candidate)" in source
    assert "safe_plan: Deductive[" in source

    materialization_path = (
        ROOT / "examples/language/refinement_loop/materialization.prism"
    )
    materialization_source = materialization_path.read_text(encoding="utf-8")
    materialization = check(
        parse_source(
            materialization_source,
            path=str(materialization_path),
        ),
        module_loader=loader,
    )
    configured = materialization.globals["lunar_landing_refinement"].type
    assert tuple(name for name, _ in configured.parameters) == ("source",)
    configured_result = configured.result
    assert configured_result is not None
    assert configured_result.name == "Workflow"
    assert configured_result.arguments[0].name == "Validated"
    assert "candidate = materialize_abductive_plan" in materialization_source
    assert "candidate_by = support_trajectory_hypothesis" in materialization_source
    assert "finding = check_trajectory" in materialization_source
    assert "safe_plan = validate_safe_plan" in materialization_source
    assert "source = prepare_refinement" in materialization_source


def test_refinement_loop_keeps_materialization_declarative() -> None:
    path = ROOT / "examples/language/refinement_loop/materialization.prism"
    source = path.read_text(encoding="utf-8")
    executable = _compile(path)
    entry = _compile(ROOT / "examples/language/refinement_loop/main.prism")

    assert executable.entry_callable is None
    assert entry.entry_callable == "main"
    main = next(
        declaration
        for declaration in entry.declarations
        if isinstance(declaration, FunctionDefinition) and declaration.name == "main"
    )
    assert tuple(name for name, _ in main.parameters) == (
        "model_access",
        "disclosure",
    )

    class RecordingFakeHandler:
        def __init__(self) -> None:
            self.fake = FakeEffectHandler()
            self.requests: list[EffectRequest] = []

        def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
            return self.fake.handles(symbol, effects)

        def execute(self, request: EffectRequest) -> EffectResult:
            self.requests.append(request)
            return self.fake.execute(request)

    handler = RecordingFakeHandler()
    output = run(entry, handler=handler)
    assert output.status == "accepted"
    assert len(handler.requests) == 5
    first_prompt = json.loads(handler.requests[0].arguments[0])
    second_prompt = json.loads(handler.requests[1].arguments[0])
    first_task = first_prompt["arguments"]["task"]["fields"]
    second_task = second_prompt["arguments"]["task"]["fields"]
    assert first_task["feedback"]["fields"]["active"] is False
    assert second_task["feedback"]["fields"]["active"] is True
    assert len(second_task["feedback"]["fields"]["constraints"]) == 11
    assert "coast" in second_task["proposed_plan"]["fields"]
    assert "terminal" in second_task["proposed_plan"]["fields"]
    assert len(second_prompt["skills"]) == 1
    assert (
        "Treat the proposed burn controls as immutable"
        in second_prompt["skills"][0]["instructions"]
    )
    assert not any(event.kind == "kernel-check-accepted" for event in output.trace)
    support_events = [
        event
        for event in output.trace
        if event.kind == "material-policy"
        and event.name == "lunar-trajectory-abduction-v1"
    ]
    assert len(support_events) == 5
    assert all(event.status == "accepted" for event in support_events)
    assert all(
        event.metadata["requirements"] == 11 and event.metadata["failed"] == ()
        for event in support_events
    )
    final_validation = next(
        event
        for event in output.trace
        if event.kind == "validation" and event.name == "lunar-lander-simulator-v1"
    )
    assert final_validation.assurance == "Validated"
    assert final_validation.status == "accepted"
    assert final_validation.metadata["specification"].startswith("SafeUnderModel(")
    validated_plan = output.result.value
    assert isinstance(validated_plan, ValidatedValue)
    assert isinstance(validated_plan.value, ComputedValue)
    assert validated_plan.value.value.fields["terminal"].fields["angle_degrees"] == 0.0
    computations = [
        event for event in output.trace if event.kind == "deterministic-computation"
    ]
    assert (
        sum(event.name == "lunar-plan-control-assembly-v1" for event in computations)
        == 5
    )
    assert (
        sum(event.name == "lunar-constraint-checker-v1" for event in computations) == 5
    )
    assert all(
        event.assurance is None and event.provenance == "Computed"
        for event in computations
    )
    assert any(event.provenance == "Generated" for event in output.trace)
    assert any(event.provenance == "Evidence" for event in output.trace)
    agent_events = [event for event in output.trace if event.kind == "agent-invoked"]
    assert len(agent_events) == 5
    assert all(
        event.metadata["skills"] == ("lunar-refinement-narrator",)
        for event in agent_events
    )
    assert all(event.assurance not in PROVENANCE_TYPES for event in output.trace)
    assert all(event.provenance not in ASSURANCE_TYPES for event in output.trace)
    finding_nodes = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and event.name == "finding"
    ]
    assert len(finding_nodes) == 5
    assert [node.metadata["result"].fields["accepted"] for node in finding_nodes] == [
        False,
        False,
        False,
        False,
        True,
    ]
    first_finding = finding_nodes[0].metadata["result"]
    checks = first_finding.fields["checks"].value.fields
    trajectory = first_finding.fields["trajectory"].value.fields
    counterexample = first_finding.fields["counterexample"]
    constraint_results = {
        item.fields["constraint"]: item.fields
        for item in counterexample.fields["constraints"]
    }
    assert counterexample.fields["active"] is True
    assert {
        name: result["satisfied"] for name, result in constraint_results.items()
    } == {
        "landing-zone": checks["inside_landing_zone"],
        "horizontal-speed": checks["horizontal_speed_safe"],
        "vertical-speed": checks["vertical_speed_safe"],
        "touchdown-altitude": checks["touchdown_altitude_safe"],
        "attitude": checks["attitude_safe"],
        "fuel-reserve": checks["fuel_reserve_safe"],
        "preterminal-clearance": trajectory["preterminal_clearance_lower_bound"] > 0.0,
        "terminal-entry-descent": trajectory["terminal_entry_vy_upper_bound"] < 0.0,
        "touchdown-descent": trajectory["touchdown_vy"] < 0.0,
        "engine-limit": checks["engine_limit_safe"],
        "fuel-nonnegative": checks["fuel_nonnegative"],
    }
    assert {
        name: result["observed_value"] for name, result in constraint_results.items()
    } == {
        "landing-zone": trajectory["touchdown_x"],
        "horizontal-speed": trajectory["touchdown_vx"],
        "vertical-speed": trajectory["touchdown_vy"],
        "touchdown-altitude": trajectory["touchdown_altitude"],
        "attitude": trajectory["touchdown_angle"],
        "fuel-reserve": trajectory["fuel_remaining"],
        "preterminal-clearance": trajectory["preterminal_clearance_lower_bound"],
        "terminal-entry-descent": trajectory["terminal_entry_vy_upper_bound"],
        "touchdown-descent": trajectory["touchdown_vy"],
        "engine-limit": trajectory["peak_thrust_upper_bound"],
        "fuel-nonnegative": trajectory["fuel_remaining"],
    }
    assert any(not result["satisfied"] for result in constraint_results.values())
    source_nodes = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and event.name == "source"
    ]
    candidate_nodes = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and event.name == "candidate"
    ]
    assert len(source_nodes) == len(candidate_nodes) == 5
    for candidate_node, source_node in zip(
        candidate_nodes[1:], source_nodes[:-1], strict=True
    ):
        candidate_plan = candidate_node.metadata["result"].value.value.value
        refinement_request = source_node.metadata["result"].fields["observation"].value
        for burn_name in ("coast", "braking", "descent", "terminal"):
            assert (
                refinement_request.fields[burn_name] == candidate_plan.fields[burn_name]
            )
    next_feedback = (
        source_nodes[0]
        .metadata["result"]
        .fields["observation"]
        .value.fields["simulator_feedback"]
    )
    assert next_feedback == counterexample
    reasoning_steps = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and "method_type" in event.metadata
    ]
    assert [event.name for event in reasoning_steps] == (
        ["candidate", "finding", "source"] * 5 + ["safe_plan"]
    )
    assert all(
        event.metadata["reasoning"].endswith(".LunarLandingRefinement")
        and "result" in event.metadata
        for event in reasoning_steps
    )
    assert "examples.language.refinement_loop.materialization" in entry.module_hashes
    assert {
        "examples.language.refinement_loop.lunar_refinement_skill",
        "examples.language.refinement_loop.optimization",
        "examples.language.refinement_loop.simulation",
        "examples.language.refinement_loop.reasoning",
        "examples.language.refinement_loop.types",
    } <= executable.module_hashes.keys()
    assert "\ndef " not in source
    assert "\nworkflow " not in source
    assert "\nagent " not in source
    simulation_source = (
        ROOT / "examples/language/refinement_loop/simulation.prism"
    ).read_text(encoding="utf-8")
    reasoning_source = (
        ROOT / "examples/language/refinement_loop/reasoning.prism"
    ).read_text(encoding="utf-8")
    refinement_source = (
        ROOT / "examples/language/refinement_loop/refinement.prism"
    ).read_text(encoding="utf-8")
    assert "repeat refinement_policy(10" in reasoning_source
    assert "repeat refinement_policy" not in simulation_source
    assert (
        "source.observation |~[policy] PlausiblyExplainsFeedback(" in refinement_source
    )
    assert "deterministic simulator counterexample attached" in refinement_source
    assert "advance_state" in simulation_source
    assert "preterminal_clearance_lower_bound" in simulation_source
    assert "refinement_narrator(request)" in refinement_source
    assert "Skills[ExplainRefinement]" in refinement_source
    assert "optimized = refine_plan(prior_candidate)" in refinement_source


def test_def_main_takes_priority_over_internal_workflows() -> None:
    source = """def prepare(value: String) -> String:
    return value

workflow internal(value: String) -> String:
    [result: prepare]

def main() -> String:
    return solve internal("def main")
"""
    executable = compile(elaborate(check(parse_source(source))))

    assert executable.entry_callable == "main"
    output = run(executable, handler=FakeEffectHandler())

    assert output.result == "def main"
    calls = [
        (event.kind, event.name)
        for event in output.trace
        if event.kind.endswith("-call")
    ]
    assert calls == [
        ("function-call", "main"),
        ("workflow-call", "internal"),
        ("function-call", "prepare"),
    ]


def test_generated_proof_for_neighboring_native_goal_fails_closed() -> None:
    source = """
def FalseEquality() -> Prop:
    return 0 == 1
def main() -> Result[Proof[FalseEquality()], ProofError]:
    term = try elaborate_proof[FalseEquality()]("rfl")
    proof = try kernel.check(term)
    return Ok(proof)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
    )

    assert output.status == "rejected"
    rejected = next(
        event for event in output.trace if event.kind == "kernel-check-rejected"
    )
    assert rejected.metadata["term_hash"]
    assert rejected.metadata["type_hash"]
    assert rejected.metadata["environment_hash"]
    assert rejected.metadata["module_hash"]


def test_generated_proof_ir_carries_the_checked_goal_term_without_rendering() -> None:
    source = """
def TrueEquality() -> Prop:
    return 0 == 0
def main() -> Result[Proof[TrueEquality()], ProofError]:
    term = try elaborate_proof[TrueEquality()]("rfl")
    proof = try kernel.check(term)
    return Ok(proof)
"""
    executable = compile(elaborate(check(parse_source(source))))
    main = next(
        declaration
        for declaration in executable.declarations
        if isinstance(declaration, FunctionDefinition) and declaration.name == "main"
    )
    binding = next(
        statement
        for statement in main.body
        if isinstance(statement, ValueBinding) and statement.name == "term"
    )

    assert isinstance(binding.expression, Try)
    assert isinstance(binding.expression.value, CallExpression)
    assert binding.expression.value.expected_term is not None

    output = run(executable, handler=FakeEffectHandler())
    assert output.status == "accepted"


def test_deterministic_validation_rejects_a_failed_requirement() -> None:
    program = parse_source("""
type Draft:
    consistent: Bool
type DraftError:
    | ModelFailure
    | ValidationError
def DraftConsistent(draft: Generated[Draft]) -> Prop
def make_draft(
    model: Model,
    model_access: ModelGenerate,
) -> Result[Generated[Draft], ModelFailure] ! {AI.Generate}:
    return generate[Draft](Draft(consistent = False), model, model_access)
def validate_draft(draft: Generated[Draft]) -> Result[
    Validated[value: Generated[Draft], DraftConsistent(value)],
    ValidationError,
]:
    return validate[DraftConsistent(draft)](
        draft,
        validator = "draft-consistency-v1",
        require = [draft.value.consistent],
    )
workflow validation(
    model: Model,
    model_access: ModelGenerate,
) -> Validated[value: Generated[Draft], DraftConsistent(value)]
    fails DraftError
    ! {AI.Generate}:
    sequence:
        [draft: make_draft]
        [accepted: validate_draft]
    return accepted
def main(
    model: Model,
    model_access: ModelGenerate,
) -> Result[
    Validated[value: Generated[Draft], DraftConsistent(value)],
    DraftError,
] ! {AI.Generate}:
    return solve validation(model, model_access)
""")
    executable = compile(elaborate(check(program)))
    output = run(executable, handler=_fake_handler())

    assert output.status == "rejected"
    assert output.result.error == "deterministic validation failed requirements 1"
    validation = next(event for event in output.trace if event.kind == "validation")
    assert validation.status == "rejected"
    assert validation.metadata == {
        "specification": "DraftConsistent(draft)",
        "requirements": 1,
        "failed": (1,),
    }


def test_validation_accepts_plain_values_without_fabricating_generation() -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""
type Configuration:
    enabled: Bool
def ConfigurationEnabled(configuration: Configuration) -> Prop
def main() -> Result[
    Validated[value: Configuration, ConfigurationEnabled(value)],
    ValidationError,
]:
    configuration = Configuration(enabled = True)
    return validate[ConfigurationEnabled(configuration)](
        configuration,
        validator = "configuration-v1",
        require = [configuration.enabled],
    )
""")
            )
        )
    )

    output = run(executable, handler=_fake_handler())

    assert output.status == "accepted"
    assert isinstance(output.result.value, ValidatedValue)
    assert output.result.value.value.fields["enabled"] is True
    assert not any(event.kind == "effect" for event in output.trace)


def test_validation_preserves_evidence_provenance() -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""
type Configuration:
    enabled: Bool
def ObservedConfigurationEnabled(configuration: Evidence[Configuration]) -> Prop
def main() -> Result[
    Validated[
        value: Evidence[Configuration],
        ObservedConfigurationEnabled(value),
    ],
    ValidationError,
]:
    configuration = Configuration(enabled = True)
    evidence = observe(configuration, source = "fixture", method = "measurement")
    return validate[ObservedConfigurationEnabled(evidence)](
        evidence,
        validator = "observed-configuration-v1",
        require = [evidence.value.enabled],
    )
""")
            )
        )
    )

    output = run(executable, handler=_fake_handler())

    validated = output.result.value
    assert isinstance(validated, ValidatedValue)
    assert validated.value.value.fields["enabled"] is True
    assert validated.value.provenance[0].source == "fixture"


def test_deterministic_computation_records_provenance_not_assurance() -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""
type Candidate:
    safe: Bool
def main() -> Computed[Candidate]:
    candidate = Candidate(safe = True)
    return compute(candidate, procedure = "fixture-computation-v1")
""")
            )
        )
    )

    output = run(executable, handler=_fake_handler())

    computed = output.result
    assert isinstance(computed, ComputedValue)
    assert computed.procedure == "fixture-computation-v1"
    event = next(
        event for event in output.trace if event.kind == "deterministic-computation"
    )
    assert event.assurance is None
    assert event.provenance == "Computed"
    assert not any(event.kind == "kernel-check-accepted" for event in output.trace)


def test_material_policy_rejects_a_failed_admission_requirement() -> None:
    program = parse_source("""
type Packet:
    admissible: Bool
type PolicyError:
    | ValidationError
def Accepted(packet: Packet) -> Prop:
    return claim("accepted")
packet = Packet(admissible = False)
evidence = observe(packet, source = "test", method = "fixture")
policy: MaterialPolicy[Packet, Accepted(packet), PolicyError] = material_policy("admission-v1", require = [packet.admissible])
def assess_packet() -> Result[Supported[Accepted(packet)], PolicyError]:
    return evidence |~[policy] Accepted(packet)
workflow assessment() -> Supported[Accepted(packet)] fails PolicyError:
    [result: assess_packet]
def main() -> Result[Supported[Accepted(packet)], PolicyError]:
    return solve assessment()
""")
    executable = compile(elaborate(check(program)))
    output = run(executable, handler=_fake_handler())

    assert output.status == "rejected"
    supported = output.result.value
    assert supported.status == "rejected"
    policy_event = next(
        event for event in output.trace if event.kind == "material-policy"
    )
    assert policy_event.metadata["requirements"] == 1
    assert policy_event.metadata["failed"] == (1,)


def test_tool_effect_cannot_introduce_generated_even_with_the_runtime_wrapper() -> None:
    generated = CoreType("Generated", (CoreType("String"),))
    result_type = CoreType("Result", (generated, CoreType("ToolError")))
    request = EffectRequest(
        "call:forged",
        "deterministic.tool",
        (),
        {},
        result_type,
        ("Tool.Call",),
    )
    result = EffectResult(
        Ok(GeneratedValue("forged", "deterministic.tool")),
        result_type,
    )
    engine = object.__new__(_Engine)
    engine.program = ExecutableProgram(None, "test", (), None)

    with pytest.raises(
        EffectContractError,
        match="cannot introduce protected type `Generated`",
    ):
        engine._validate_effect_result(request, result)


def test_generate_effect_cannot_introduce_nested_protected_value() -> None:
    nested = CoreType("Generated", (CoreType("String"),))
    generated = CoreType("Generated", (nested,))
    result_type = CoreType("Result", (generated, CoreType("ModelFailure")))
    request = EffectRequest(
        "call:nested",
        "generate",
        (),
        {},
        result_type,
        ("AI.Generate",),
    )
    result = EffectResult(
        Ok(GeneratedValue(GeneratedValue("nested", "model"), "model")),
        result_type,
    )
    engine = object.__new__(_Engine)
    engine.program = ExecutableProgram(None, "test", (), None)

    with pytest.raises(
        EffectContractError,
        match="cannot introduce protected type `Generated`",
    ):
        engine._validate_effect_result(request, result)


def test_module_aliases_resolve_and_execute_typed_exports() -> None:
    loader = InMemoryModuleLoader(
        {
            "sample.values": """
type Packet:
    value: String
type Envelope[Value]:
    packet: Value
def wrap[Value](packet: Value) -> Envelope[Value]:
    return Envelope(packet = packet)
def echo(packet: Packet) -> String:
    return helper(packet.value)
def helper(value: String) -> String:
    return value
"""
        }
    )
    program = parse_source("""
import sample.values as sample
def main() -> String:
    packet: sample.Packet = sample.Packet(value = "module alias")
    envelope: sample.Envelope[sample.Packet] = sample.wrap[sample.Packet](packet)
    return sample.echo(envelope.packet)
""")
    executable = compile(elaborate(check(program, module_loader=loader)))
    output = run(executable, handler=_fake_handler())
    assert output.status == "accepted"
    assert output.result == "module alias"
