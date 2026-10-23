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
    RecordValue,
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
    assert relation.outcome is not None
    observed = relation.outcome.observed[0]
    assert observed.claim is not None and observed.certificate is not None
    assert (
        observed.certificate["proof_hash"] == relation.metadata["certificate"].term_hash
    )
    assert (
        observed.certificate["proposition_hash"]
        == relation.metadata["certificate"].type_hash
    )
    assert relation.metadata["certificate_type"] == (
        "Proof[SameVersion(target, approved)]"
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
        "Validated[value: Computed[PlanHypothesis], SafeUnderModel(value)]"
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
        event.metadata["disposition"] == "accepted" and event.metadata["policy_hash"]
        for event in support_events
    )
    final_validation = next(
        event
        for event in output.trace
        if event.kind == "validation" and event.name.endswith("::safe_under_model")
    )
    assert final_validation.assurance == "Validated"
    assert final_validation.status == "accepted"
    assert final_validation.metadata["specification"].startswith(
        "types.SafeUnderModel("
    )
    validated_plan = output.result.value
    assert isinstance(validated_plan, ValidatedValue)
    assert isinstance(validated_plan.value, ComputedValue)
    assert validated_plan.value.value.fields["terminal"].fields["angle_degrees"] == 0.0
    narrative = _provenance_path(output, "value", "value", "value", "strategy")
    assert any(
        activity.kind == "generated"
        for activity in _provenance_activities(output, narrative)
    )
    plan = _provenance_path(output, "value", "value")
    assert any(
        activity.kind == "computed"
        and activity.operation.endswith("::build_plan_hypothesis")
        for activity in _provenance_activities(output, plan)
    )
    relations = [event for event in output.trace if event.kind == "reasoning-relation"]
    for relation in relations:
        assert relation.outcome is not None
        support = relation.outcome.observed[0]
        assert support.assurance == "supported"
        assert support.claim is not None and support.certificate is not None
        assert support.certificate["policy_hash"]
        assert support.certificate["evidence_reference"]
    safe_node = next(
        event
        for event in output.trace
        if event.kind == "workflow-node" and event.name == "safe_plan"
    )
    assert (
        safe_node.metadata["declared_contract"]["classification"]["state"]
        == "classified"
    )
    assert safe_node.outcome is not None
    accepted = next(
        observed
        for observed in safe_node.outcome.observed
        if observed.assurance == "validated"
    )
    assert accepted.claim is not None and accepted.certificate is not None
    assert accepted.certificate["validator_hash"] == validated_plan.validator_hash
    assert safe_node.outcome.contract == "satisfied"
    assert (
        next(
            observed
            for observed in safe_node.outcome.observed
            if observed.path == ("value",)
        ).assurance
        == "validated"
    )
    assert not any(
        observed.assurance == "proved" for observed in safe_node.outcome.observed
    )
    computations = [
        event
        for event in output.trace
        if event.kind == "deterministic-computation"
        and event.metadata.get("phase") != "assurance-recheck"
    ]
    assert (
        sum(event.name.endswith("::build_plan_hypothesis") for event in computations)
        == 5
    )
    assert (
        sum(event.name.endswith("::evaluate_constraints") for event in computations)
        == 6
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
    assert "transformation = revise_request" in refinement_source
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
def draft_check(draft: Generated[Draft]) -> Bool:
    return draft.value.consistent
draft_check_registered = validator[value: Generated[Draft], DraftConsistent(value)](draft_check)
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
        validator = draft_check_registered,
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
    assert output.result.error == "deterministic validator rejected the supplied value"
    validation = next(event for event in output.trace if event.kind == "validation")
    assert validation.status == "rejected"
    assert validation.metadata["specification"] == "DraftConsistent(draft)"
    assert validation.metadata["result"] is False
    assert len(validation.metadata["validator_hash"]) == 64


def test_validation_accepts_plain_values_without_fabricating_generation() -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""
type Configuration:
    enabled: Bool
def ConfigurationEnabled(configuration: Configuration) -> Prop
def configuration_check(configuration: Configuration) -> Bool:
    return configuration.enabled
configuration_check_registered = validator[value: Configuration, ConfigurationEnabled(value)](configuration_check)
def main() -> Result[
    Validated[value: Configuration, ConfigurationEnabled(value)],
    ValidationError,
]:
    configuration = Configuration(enabled = True)
    return validate[ConfigurationEnabled(configuration)](
        configuration,
        validator = configuration_check_registered,
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
def observation_check(configuration: Evidence[Configuration]) -> Bool:
    return configuration.value.enabled
observation_check_registered = validator[value: Evidence[Configuration], ObservedConfigurationEnabled(value)](observation_check)
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
        validator = observation_check_registered,
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
def copy_candidate(value: Candidate) -> Candidate:
    return value
def main() -> Computed[Candidate]:
    candidate = Candidate(safe = True)
    return compute(candidate, procedure = copy_candidate)
""")
            )
        )
    )

    output = run(executable, handler=_fake_handler())

    computed = output.result
    assert isinstance(computed, ComputedValue)
    assert computed.procedure == "Main::copy_candidate"
    event = next(
        event for event in output.trace if event.kind == "deterministic-computation"
    )
    assert event.assurance is None
    assert event.provenance == "Computed"
    assert not any(event.kind == "kernel-check-accepted" for event in output.trace)


def test_material_policy_rejection_remains_an_inspectable_assessment() -> None:
    program = parse_source("""
type Packet:
    admissible: Bool
def Accepted(packet: Packet) -> Prop
def assess(evidence: Evidence[Packet], packet: Packet) -> PolicyDecision:
    return accept_assessment("admissible") if evidence.value.admissible and evidence.value == packet else reject_assessment("not admissible")
packet = Packet(admissible = False)
evidence = observe(packet, source = "test", method = "fixture")
policy = material_policy[Packet, Accepted(packet), Never]("admission-v1", evaluator = assess)
def main() -> Result[Assessment[Accepted(packet)], Never]:
    return evidence |~[policy] Accepted(packet)
""")
    output = run(compile(elaborate(check(program))), handler=_fake_handler())
    assert output.status == "accepted"
    assessment = output.result.value
    assert assessment.disposition == "rejected"
    policy_event = next(
        event for event in output.trace if event.kind == "material-policy"
    )
    assert policy_event.metadata["disposition"] == "rejected"
    assert policy_event.assurance == "Unchecked"


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


@pytest.mark.parametrize("deployed", [7, 9])
def test_runtime_proof_goal_uses_the_shadowing_input(deployed: int) -> None:
    source = """deployed: Nat = 7
approved: Nat = 7
def SameVersion(left: Nat, right: Nat) -> Prop:
    return left == right
def main(deployed: Nat) -> Result[Verified[Nat, SameVersion(deployed, approved)], ProofError]:
    term = try elaborate_proof[SameVersion(deployed, approved)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(deployed, proof))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
        entry_arguments={"deployed": deployed},
    )
    assert output.status == ("accepted" if deployed == 7 else "rejected")
    if deployed == 7:
        assert isinstance(output.result, Ok)
        assert output.result.value.value == 7
        assert output.result.value.proof.environment_hash


@pytest.mark.parametrize("deployed", [7, 9])
def test_named_proof_syntax_resolves_runtime_locals(deployed: int) -> None:
    source = """deployed: Nat = 7
def Reflexive(value: Nat) -> Prop:
    return value == value
def main(deployed: Nat) -> Result[Verified[Nat, Reflexive(deployed)], ProofError]:
    alias = deployed
    term = try elaborate_proof[Reflexive(alias)]("Eq.rfl(Nat, deployed)")
    proof = try kernel.check(term)
    return Ok(verify(alias, proof))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=FakeEffectHandler(),
        entry_arguments={"deployed": deployed},
    )
    assert output.status == "accepted"
    assert isinstance(output.result, Ok)
    assert output.result.value.value == deployed


@pytest.mark.parametrize("deployed", [7, 9])
def test_imported_native_propositions_do_not_collide(deployed: int) -> None:
    modules = InMemoryModuleLoader(
        {
            "left": """def Approved(value: Nat) -> Prop:
    return value == 7
""",
            "right": """approved: Nat = 9
def Approved(value: Nat) -> Prop:
    return value == approved
""",
        }
    )
    source = """import left as first
import right as second
def main(deployed: Nat) -> Result[Verified[Nat, second.Approved(deployed)], ProofError]:
    term = try elaborate_proof[second.Approved(deployed)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(deployed, proof))
"""
    output = run(
        compile(elaborate(check(parse_source(source), module_loader=modules))),
        handler=FakeEffectHandler(),
        entry_arguments={"deployed": deployed},
    )
    assert output.status == ("accepted" if deployed == 9 else "rejected")


def test_imported_aliases_and_globals_bind_the_exact_proof_goal() -> None:
    modules = InMemoryModuleLoader(
        {
            "versions": """type Version = Nat
approved: Version = 7
def Same(left: Version, right: Version) -> Prop:
    return left == right
"""
        }
    )
    source = """from versions import approved as reference, Same as Agrees
def main(deployed: Nat) -> Result[Verified[Nat, Agrees(deployed, reference)], ProofError]:
    alias = deployed
    term = try elaborate_proof[Agrees(alias, reference)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(alias, proof))
"""
    executable = compile(elaborate(check(parse_source(source), module_loader=modules)))
    for value in (7, 9):
        output = run(
            executable, handler=FakeEffectHandler(), entry_arguments={"deployed": value}
        )
        assert output.status == ("accepted" if value == 7 else "rejected")


@pytest.mark.parametrize("value_type", ["Int", "String"])
def test_unsupported_runtime_proof_values_receive_a_diagnostic(value_type: str) -> None:
    from prism.language.developer import PrismTypeError

    source = f"""def Holds(value: {value_type}) -> Prop
def main(value: {value_type}) -> Result[Proof[Holds(value)], ProofError]:
    term = try elaborate_proof[Holds(value)]("rfl")
    return kernel.check(term)
"""
    with pytest.raises(PrismTypeError, match="not representable"):
        check(parse_source(source))


@pytest.mark.parametrize("replacement", [9, "7"])
def test_verify_checks_the_actual_paired_runtime_value(replacement: object) -> None:
    from dataclasses import replace

    from prism.language.effects import Literal, Return

    executable = compile(
        elaborate(
            check(
                parse_source("""approved: Nat = 7
def Same(left: Nat, right: Nat) -> Prop:
    return left == right
def main(value: Nat) -> Result[Verified[Nat, Same(value, approved)], ProofError]:
    term = try elaborate_proof[Same(value, approved)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(value, proof))
""")
            )
        )
    )
    main = next(
        item
        for item in executable.declarations
        if isinstance(item, FunctionDefinition) and item.name == "main"
    )
    returned = main.body[-1]
    assert isinstance(returned, Return)
    success = returned.expression
    verification = success.arguments[0].value
    verification = replace(
        verification,
        arguments=(
            replace(verification.arguments[0], value=Literal(replacement)),
            verification.arguments[1],
        ),
    )
    returned = replace(
        returned,
        expression=replace(
            success, arguments=(replace(success.arguments[0], value=verification),)
        ),
    )
    changed = replace(main, body=(*main.body[:-1], returned))
    executable = replace(
        executable,
        declarations=tuple(
            changed if item is main else item for item in executable.declarations
        ),
    )
    with pytest.raises(ValueError, match="different instantiated|not representable"):
        run(executable, handler=FakeEffectHandler(), entry_arguments={"value": 7})


def test_runtime_proof_identities_are_reproducible_and_value_specific() -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""def Reflexive(value: Nat) -> Prop:
    return value == value
def main(value: Nat) -> Result[Verified[Nat, Reflexive(value)], ProofError]:
    term = try elaborate_proof[Reflexive(value)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(value, proof))
""")
            )
        )
    )
    outputs = [
        run(executable, handler=FakeEffectHandler(), entry_arguments={"value": value})
        for value in (7, 7, 9)
    ]
    assert all(output.status == "accepted" for output in outputs)
    proofs = [output.result.value.proof for output in outputs]
    assert proofs[0] == proofs[1]
    assert proofs[0].type_hash != proofs[2].type_hash
    assert proofs[0].term_hash != proofs[2].term_hash
    assert proofs[0].environment_hash == proofs[2].environment_hash
    assert proofs[0].axioms == proofs[2].axioms == frozenset()


@pytest.mark.parametrize("value", [False, True])
def test_runtime_boolean_proof_values_keep_their_native_type(value: bool) -> None:
    executable = compile(
        elaborate(
            check(
                parse_source("""def Reflexive(value: Bool) -> Prop:
    return value == value
def main(value: Bool) -> Result[Verified[Bool, Reflexive(value)], ProofError]:
    term = try elaborate_proof[Reflexive(value)]("Eq.rfl(Bool, value)")
    proof = try kernel.check(term)
    return Ok(verify(value, proof))
""")
            )
        )
    )
    output = run(
        executable, handler=FakeEffectHandler(), entry_arguments={"value": value}
    )
    assert output.status == "accepted"
    assert output.result.value.value is value


@pytest.mark.parametrize("value, accepted", [(-1, False), (3, True)])
def test_registered_validator_checks_the_supplied_value(value, accepted):
    source = f"""
def Positive(value: Int) -> Prop
def positive_check(value: Int) -> Bool:
    return value > 0
positive = validator[value: Int, Positive(value)](positive_check)
def main() -> Result[Validated[value: Int, Positive(value)], ValidationError]:
    candidate = {value}
    return validate[Positive(candidate)](candidate, validator = positive)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == ("accepted" if accepted else "rejected")
    event = next(item for item in output.trace if item.kind == "validation")
    assert event.metadata["result"] is accepted
    assert len(event.metadata["validator_hash"]) == 64
    if accepted:
        assert output.result.value.value == value
        assert output.result.value.result is True


@pytest.mark.parametrize(
    "replacement",
    [
        "validate[Other(candidate)](candidate, validator = positive)",
        "validate[Positive(neighbor)](candidate, validator = positive)",
        'validate[Positive(candidate)](candidate, validator = "label", require = [])',
        'validate[Positive(candidate)]("wrong", validator = positive)',
    ],
)
def test_validation_rejects_unregistered_or_unrelated_checks(replacement):
    source = """
def Positive(value: Int) -> Prop
def Other(value: Int) -> Prop
def positive_check(value: Int) -> Bool:
    return value > 0
positive = validator[value: Int, Positive(value)](positive_check)
def main() -> Result[Validated[value: Int, Positive(value)], ValidationError]:
    candidate = 3
    neighbor = 4
    return VALIDATE
""".replace("VALIDATE", replacement)
    with pytest.raises(ValueError):
        check(parse_source(source))


@pytest.mark.parametrize(
    "result, effects, body",
    [
        ("Result[Bool, ValidationError]", "", "Ok(True)"),
        ("Int", "", "1"),
    ],
)
def test_validator_registration_requires_a_pure_boolean_function(result, effects, body):
    source = f"""
def Positive(value: Int) -> Prop
def invalid_check(value: Int) -> {result}{effects}:
    return {body}
registered = validator[value: Int, Positive(value)](invalid_check)
"""
    with pytest.raises(ValueError):
        check(parse_source(source))


def test_validator_keeps_actual_callable_identity_through_registration_function():
    source = """
def Positive(value: Int) -> Prop
def positive_check(value: Int) -> Bool:
    return value > 0
def register(check: (value: Int) -> Bool) -> Validator[item: Int, Positive(item)]:
    return validator[value: Int, Positive(value)](check)
def main() -> Result[Validated[value: Int, Positive(value)], ValidationError]:
    registered = register(positive_check)
    candidate = 3
    return validate[Positive(candidate)](candidate, validator = registered)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value.validator == "Main::positive_check"


def test_validator_annotation_cannot_generalize_a_fixed_claim():
    source = """
def Positive(value: Int) -> Prop
def positive_check(value: Int) -> Bool:
    return value > 0
fixed = 7
registered: Validator[value: Int, Positive(value)] = validator[item: Int, Positive(fixed)](positive_check)
"""
    with pytest.raises(ValueError):
        check(parse_source(source))


def test_successful_validation_retains_the_generated_input():
    source = """
type GeneratedValidationError:
    | ModelFailure
    | ValidationError
def Positive(value: Generated[Int]) -> Prop
def positive_check(value: Generated[Int]) -> Bool:
    return value.value > 0
registered = validator[value: Generated[Int], Positive(value)](positive_check)
def main(model: Model, access: ModelGenerate) -> Result[
    Validated[value: Generated[Int], Positive(value)], GeneratedValidationError
] ! {AI.Generate}:
    candidate = try generate[Int](3, model, access)
    return validate[Positive(candidate)](candidate, validator = registered)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == "accepted"
    validated = output.result.value
    assert isinstance(validated.value, GeneratedValue)
    assert validated.value.value == 3
    assert validated.value.producer
    assert not any(item.kind == "kernel-check-accepted" for item in output.trace)
    activities = _provenance_activities(
        output, _provenance_path(output, "value", "value")
    )
    assert any(activity.kind == "generated" for activity in activities)


def test_validator_content_identity_changes_with_implementation():
    template = """
def Positive(value: Int) -> Prop
def positive_check(value: Int) -> Bool:
    return CHECK
registered = validator[value: Int, Positive(value)](positive_check)
def main() -> Result[Validated[value: Int, Positive(value)], ValidationError]:
    candidate = 3
    return validate[Positive(candidate)](candidate, validator = registered)
"""
    values = []
    for expression in ("value > 0", "value >= 1", "value > 0"):
        source = template.replace("CHECK", expression)
        output = run(
            compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
        )
        values.append(output.result.value)
    assert values[0].validator == values[1].validator
    assert values[0].validator_hash != values[1].validator_hash
    assert values[0].validator_hash == values[2].validator_hash


@pytest.mark.parametrize("disposition", ["accepted", "rejected", "inconclusive"])
def test_policy_assessments_are_completed_without_implying_support(disposition):
    decision = {
        "accepted": "accept",
        "rejected": "reject",
        "inconclusive": "inconclusive",
    }[disposition]
    source = f"""
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return {decision}_assessment("examined the supplied evidence")
policy = material_policy[Int, Positive(3), Never]("display", evaluator = evaluate)
def main() -> Result[Assessment[Positive(3)], Never]:
    return observe(3) |~[policy] Positive(3)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == "accepted"
    assessment = output.result.value
    assert assessment.disposition == disposition
    assert assessment.evidence.value == 3
    assert assessment.policy_identity == "Main::evaluate"
    assert len(assessment.policy_hash) == 64
    assert assessment.evidence_reference.startswith("sha256:")


@pytest.mark.parametrize("label", ["admission", "medication-administration", "renamed"])
@pytest.mark.parametrize(
    "evidence_value, expected", [(3, "accepted"), (-1, "rejected"), (0, "inconclusive")]
)
def test_policy_evaluator_uses_evidence_not_its_display_name(
    label, evidence_value, expected
):
    source = f"""
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return inconclusive_assessment("missing observation") if evidence.value == 0 else (accept_assessment("matches") if evidence.value == value else reject_assessment("does not match"))
policy = material_policy[Int, Positive(3), Never]("{label}", evaluator = evaluate)
def main() -> Result[Assessment[Positive(3)], Never]:
    return observe({evidence_value}) |~[policy] Positive(3)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == "accepted"
    assert output.result.value.disposition == expected


@pytest.mark.parametrize(
    "decision, accepted", [("accept", True), ("reject", False), ("inconclusive", False)]
)
def test_only_accepted_assessments_can_introduce_support(decision, accepted):
    source = f"""
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return {decision}_assessment("evaluated")
policy = material_policy[Int, Positive(3), Never]("policy", evaluator = evaluate)
def main() -> Result[Supported[Positive(3)], SupportError]:
    assessment = try observe(3) |~[policy] Positive(3)
    return accept_support(assessment)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == ("accepted" if accepted else "rejected")
    if accepted:
        assert output.result.value.status == "accepted"
    else:
        assert output.result.error.disposition in {"rejected", "inconclusive"}


def test_policy_evaluator_failure_is_not_a_negative_assessment():
    source = """
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> Result[PolicyDecision, String]:
    return Err("evaluator unavailable")
policy = material_policy[Int, Positive(3), String]("policy", evaluator = evaluate)
def main() -> Result[Assessment[Positive(3)], String]:
    return observe(3) |~[policy] Positive(3)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.error == "evaluator unavailable"
    event = next(item for item in output.trace if item.kind == "material-policy")
    assert event.status == "failed"
    assert "disposition" not in event.metadata


@pytest.mark.parametrize(
    "operation",
    [
        'observe("wrong") |~[policy] Positive(3)',
        "observe(3) |~[policy] Positive(4)",
        "observe(3) |~[policy] Other(3)",
    ],
)
def test_material_policy_rejects_evidence_or_claim_type_mismatches(operation):
    source = f"""
def Positive(value: Int) -> Prop
def Other(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return accept_assessment("evaluated")
policy = material_policy[Int, Positive(3), Never]("policy", evaluator = evaluate)
def main() -> Result[Assessment[Positive(3)], Never]:
    return {operation}
"""
    with pytest.raises(ValueError, match="material"):
        check(parse_source(source))


def test_effectful_policy_preserves_effects_and_uses_captured_permission():
    source = """
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int, access: PythonCall) -> Result[PolicyDecision, PythonError] ! {Python.Call}:
    result = try python_call[Bool]("policy.check", evidence.value, access)
    return Ok(accept_assessment("external evaluator accepted") if result else reject_assessment("external evaluator rejected"))
def main(access: PythonCall) -> Result[Assessment[Positive(3)], PythonError] ! {Python.Call}:
    policy = material_policy[Int, Positive(3), PythonError]("policy", evaluator = evaluate, access = access)
    return observe(3) |~[policy] Positive(3)
"""
    checked = check(parse_source(source))
    assert checked.callable_contracts["main"].effects == ("Python.Call",)

    class Handler:
        def handles(self, symbol, effects):
            return True

        def execute(self, request):
            assert request.symbol == "policy.check"
            return EffectResult(Ok(True), request.result_type)

    output = run(compile(elaborate(checked)), handler=Handler())
    assert output.result.value.disposition == "accepted"
    assert any(item.kind == "effect" for item in output.trace)
    with pytest.raises(ValueError):
        check(
            parse_source(
                source.replace(
                    "PythonError] ! {Python.Call}:\n    policy",
                    "PythonError]:\n    policy",
                )
            )
        )


@pytest.mark.parametrize(
    "policy_call",
    [
        'material_policy[Int, Positive(3), Never]("empty")',
        'material_policy[Int, Positive(3), Never]("empty", require = [])',
    ],
)
def test_material_policy_requires_an_evaluator(policy_call):
    with pytest.raises(ValueError, match="evaluator"):
        check(
            parse_source(f"def Positive(value: Int) -> Prop\npolicy = {policy_call}\n")
        )


def test_assessment_cannot_satisfy_a_supported_consumer():
    source = """
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return reject_assessment("rejected")
policy = material_policy[Int, Positive(3), Never]("policy", evaluator = evaluate)
def main() -> Result[Supported[Positive(3)], Never]:
    return observe(3) |~[policy] Positive(3)
"""
    with pytest.raises(ValueError, match="Supported"):
        check(parse_source(source))


def test_policy_effects_cannot_be_erased_by_an_annotation():
    source = """
def Positive(value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int, access: PythonCall) -> PolicyDecision ! {Python.Call}:
    return accept_assessment("accepted")
def main(access: PythonCall) -> Int:
    policy: MaterialPolicy[Int, Positive(3), Never] = material_policy("policy", evaluator = evaluate, access = access)
    return 0
"""
    with pytest.raises(ValueError, match="MaterialPolicy"):
        check(parse_source(source))
    check(
        parse_source(
            source.replace(
                "policy: MaterialPolicy[Int, Positive(3), Never] =",
                "policy: MaterialPolicy[Int, Positive(3), Never] ! {Python.Call} =",
            )
        )
    )


def test_validator_registration_rejects_a_supported_effect():
    source = """
def Authorized(access: PythonCall) -> Prop
def check_access(access: PythonCall) -> Bool ! {Python.Call}:
    return True
registered = validator[value: PythonCall, Authorized(value)](check_access)
"""
    with pytest.raises(ValueError, match="pure infallible validator"):
        check(parse_source(source))


def test_policy_assessment_retains_claim_specialization():
    source = """
def Selected[Tag](value: Int) -> Prop
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return accept_assessment("matches")
policy = material_policy[Int, Selected[String](3), Never]("policy", evaluator = evaluate)
def main() -> Result[Assessment[Selected[String](3)], Never]:
    return observe(3) |~[policy] Selected[String](3)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value.claim.specialization == (CoreType("String"),)


def test_strict_example_rejects_a_materializer_returning_another_version():
    directory = ROOT / "examples/language/strict_inference"
    modules = {
        "examples.language.strict_inference.reasoning": (
            directory / "reasoning.prism"
        ).read_text(),
        "examples.language.strict_inference.materialization": (
            directory / "materialization.prism"
        )
        .read_text()
        .replace("return approved", "return 9"),
        "prism.reasoning.methods.deductive": (
            ROOT / "libs/prism/reasoning/methods/deductive.prism"
        ).read_text(),
    }
    program = parse_source((directory / "main.prism").read_text())
    executable = compile(
        elaborate(
            check(
                program,
                module_loader=InMemoryModuleLoader(
                    modules,
                    taxonomies=(
                        WorkspaceModuleLoader(project_root=ROOT).load_taxonomy(
                            "prism-workflow-component-taxonomy", "0.6.0"
                        ),
                    ),
                ),
            )
        )
    )
    output = run(executable, handler=_fake_handler())
    assert output.status == "rejected"
    relation = next(item for item in output.trace if item.kind == "reasoning-relation")
    assert relation.status == "rejected"
    assert relation.metadata["certificate_valid"] is False
    assert (
        any(item.kind == "kernel-check-rejected" for item in output.trace)
        or "proof" in str(output.result.error).lower()
    )


def test_transformations_invoke_the_declared_pure_callable():
    source = """
def increment(value: Int) -> Int:
    return value + 1
def add(left: Int, right: Int) -> Int:
    return left + right
def identity[A](value: A) -> A:
    return value
type Outputs:
    computed: Computed[Int]
    mapped: Evidence[Int]
    combined: Evidence[Int]
def main() -> Outputs:
    first = observe(2, source = "first")
    second = observe(5, source = "second")
    mapped = map_evidence(first, transformation = increment)
    combined = combine_evidence(first, second, transformation = add)
    return Outputs(
        computed = compute(9, procedure = identity),
        mapped = mapped,
        combined = combined,
    )
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    values = output.result.fields
    assert values["computed"].value == 9
    assert values["mapped"].value == 3
    assert values["combined"].value == 7
    assert [p.source for p in values["combined"].provenance] == ["first", "second"]
    assert values["mapped"].provenance[0].transformations == ("Main::increment",)
    combined_activities = _provenance_activities(
        output, _provenance_path(output, "combined", "value")
    )
    assert {
        activity.source
        for activity in combined_activities
        if activity.kind == "asserted"
    } == {"first", "second"}
    events = [
        event
        for event in output.trace
        if event.kind in {"deterministic-computation", "evidence-transformed"}
    ]
    assert len(events) == 3
    assert all(len(event.metadata["implementation_hash"]) == 64 for event in events)
    assert not any(event.kind == "kernel-check-accepted" for event in output.trace)


@pytest.mark.parametrize(
    "expression",
    [
        'compute(1, procedure = "label")',
        'map_evidence(observe(1), value = 99, transformation = "label")',
        'combine_evidence(observe(1), value = 99, transformation = "label")',
        "compute(1, procedure = fallible)",
        "compute(1, procedure = effectful)",
        "compute(True, procedure = increment)",
        "compute(1, 2, procedure = increment)",
    ],
)
def test_transformation_rejects_labels_failures_effects_and_wrong_arguments(expression):
    source = f"""
def increment(value: Int) -> Int:
    return value + 1
def fallible(value: Int) -> Result[Int, String]:
    return Ok(value)
def effectful(value: Int) -> Int ! {{Python.Call}}:
    return value
def main() -> Int:
    transformed = {expression}
    return 0
"""
    with pytest.raises(ValueError):
        check(parse_source(source))


def test_computation_preserves_dependent_transformation_requirements():
    source = """
approved: Nat = 7
def Positive(subject: Nat) -> Prop
def copy_proof(subject: Nat, proof: Proof[Positive(subject)]) -> Proof[Positive(subject)]:
    return proof
def transform(value: Nat, proof: Proof[Positive(value)]) -> Computed[Proof[Positive(value)]]:
    return compute(value, proof, procedure = copy_proof)
"""
    check(parse_source(source))
    with pytest.raises(ValueError, match="type-mismatch"):
        check(
            parse_source(
                source.replace(
                    "-> Computed[Proof[Positive(value)]]",
                    "-> Computed[Proof[Positive(approved)]]",
                )
            )
        )


def _provenance_activities(output, reference):
    graph = output.provenance
    assert graph is not None
    values = {value.identity: value for value in graph.values}
    activities = {activity.identity: activity for activity in graph.activities}
    found = {}
    visited = set()
    pending = [reference]
    while pending:
        identity = pending.pop()
        if identity in visited:
            continue
        visited.add(identity)
        value = values[identity]
        pending.extend(value.dependencies)
        activity = activities[value.activity]
        if activity.identity not in found:
            found[activity.identity] = activity
            pending.extend(activity.inputs)
    return tuple(found.values())


def _provenance_path(output, *path):
    graph = output.provenance
    assert graph is not None
    references = {value.identity: value for value in graph.values}
    reference = graph.result
    assert reference is not None
    for name in path:
        reference = dict(references[reference].children)[name]
    return reference


def test_generated_projection_keeps_ancestry_through_nested_computation():
    from prism.runtime.replay import EffectRecorder

    recorder = EffectRecorder()
    source = """
type Draft:
    count: Int
type Outputs:
    derived: Computed[Int]
    independent: Int
def increment(value: Int) -> Int:
    return value + 1
def nested(value: Int) -> Int:
    return increment(value)
def main(model: Model, access: ModelGenerate) -> Result[Outputs, ModelFailure] ! {AI.Generate}:
    draft = try generate[Draft](Draft(count = 9), model, access)
    projected = draft.value.count
    return Ok(Outputs(
        derived = compute(projected, procedure = nested),
        independent = 9,
    ))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        effect_recorder=recorder,
        handler=FakeEffectHandler(
            generated_outputs={"Draft": RecordValue("Draft", {"count": 9})}
        ),
    )
    assert output.result.value.fields["derived"].value == 10
    derived = _provenance_path(output, "value", "derived", "value")
    activities = _provenance_activities(output, derived)
    generated = [activity for activity in activities if activity.kind == "generated"]
    assert len(generated) == 1
    assert generated[0].effect_record in output.effect_records
    assert generated[0].synthetic is True
    computation = _provenance_activities(
        output, _provenance_path(output, "value", "derived")
    )
    assert any(
        activity.operation == "Main::nested" and activity.implementation_hash
        for activity in computation
    )
    independent = _provenance_path(output, "value", "independent")
    assert not any(
        activity.kind == "generated"
        for activity in _provenance_activities(output, independent)
    )
    assert output.result.value.fields["independent"] == 9

    graph = output.provenance
    assert graph is not None
    values = {reference.identity: reference for reference in graph.values}
    derived_artifact = values[derived].artifact
    independent_artifact = values[independent].artifact
    assert derived_artifact is not None and independent_artifact is not None
    assert recorder.store.get(derived_artifact) == 10
    assert recorder.store.get(independent_artifact) == 9
    assert values[derived].identity != values[independent].identity


def test_resource_acquisition_and_source_assertions_have_distinct_ancestry(tmp_path):
    from hashlib import sha256

    from prism.sdk.workspace import LocalResourceResolver

    (tmp_path / "measurement.txt").write_text("measured")
    source = """
resource: Resource[String] = embed("measurement.txt")
type Outputs:
    acquired: Evidence[String]
    asserted: Evidence[String]
def annotate(value: String) -> String:
    return value + "!"
def main(files: FileRead, clock: ClockRead) -> Result[Outputs, SourceError] ! {File.Read, Clock.Read}:
    acquired = try resource_evidence(resource, files, clock)
    asserted = observe("measured", source = "measurement.txt", method = "file read")
    return Ok(Outputs(
        acquired = map_evidence(acquired, transformation = annotate),
        asserted = asserted,
    ))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=_fake_handler(),
        resource_resolver=LocalResourceResolver(tmp_path),
    )
    assert output.result.value.fields["acquired"].value == "measured!"
    acquired = _provenance_activities(
        output, _provenance_path(output, "value", "acquired")
    )
    reads = [activity for activity in acquired if activity.kind == "acquired"]
    assert len(reads) == 1
    assert reads[0].source == "measurement.txt"
    assert reads[0].source_hash == sha256(b"measured").hexdigest()
    asserted = _provenance_activities(
        output, _provenance_path(output, "value", "asserted")
    )
    assert any(activity.kind == "asserted" for activity in asserted)
    assert not any(activity.kind == "acquired" for activity in asserted)


def test_repeated_occurrences_retain_generated_state_ancestry():
    source = """
type State:
    count: Int
    done: Bool
type Step = State -> State
reasoning Loop(state: State) -> State:
    repeat refinement_policy(3, until = state.done):
        [state: Step(state)]
    return state
def advance(state: State) -> State:
    count = state.count + 1
    return State(count = count, done = count >= 3)
configured = Loop(state = advance)
def main(model: Model, access: ModelGenerate) -> Result[State, ModelFailure] ! {AI.Generate}:
    generated = try generate[Int](1, model, access)
    initial = State(count = generated.value, done = False)
    result = solve Loop(initial) using configured(initial)
    return Ok(result)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value.fields["count"] == 3
    events = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and event.name == "state"
    ]
    assert len(events) == 2
    assert len({event.metadata["occurrence_instance_id"] for event in events}) == 2
    assert len({event.metadata["source_occurrence_id"] for event in events}) == 1
    assert len({event.metadata["invocation_id"] for event in events}) == 1
    assert all(
        event.metadata["run_id"] == output.metadata["run_id"] for event in events
    )
    references = [event.metadata["output_reference"] for event in events]
    assert len(set(references)) == 2
    assert all(
        any(
            activity.kind == "generated"
            for activity in _provenance_activities(output, reference)
        )
        for reference in references
    )
    assert any(
        activity.kind == "generated"
        for activity in _provenance_activities(
            output, _provenance_path(output, "value", "count")
        )
    )


def test_mixed_collection_projection_keeps_selected_element_origins():
    source = """
type Outputs:
    selected: Int
    independent: Int
def choose(values: List[Int], generated: Bool) -> Int:
    return values[0] if generated else values[1]
def main(model: Model, access: ModelGenerate) -> Result[Outputs, ModelFailure] ! {AI.Generate}:
    generated = try generate[Int](4, model, access)
    mixed = [generated.value, 4]
    return Ok(Outputs(selected = choose(mixed, True), independent = choose(mixed, False)))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value.fields == {"selected": 4, "independent": 4}
    selected = _provenance_activities(
        output, _provenance_path(output, "value", "selected")
    )
    independent = _provenance_activities(
        output, _provenance_path(output, "value", "independent")
    )
    assert any(activity.kind == "generated" for activity in selected)
    assert not any(activity.kind == "generated" for activity in independent)


def test_native_proof_retains_its_generated_runtime_subject_ancestry():
    source = """
type Failure:
    | ModelFailure
    | ProofError
def Same(left: Nat, right: Nat) -> Prop:
    return left == right
def main(model: Model, access: ModelGenerate) -> Result[Verified[value: Nat, Same(value, value)], Failure] ! {AI.Generate}:
    generated = try generate[Nat](3, model, access)
    value = generated.value
    term = try elaborate_proof[Same(value, value)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(value, proof))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == "accepted"
    assert output.result.value.value == 3
    proof = _provenance_path(output, "value", "proof")
    assert any(
        activity.kind == "generated"
        for activity in _provenance_activities(output, proof)
    )
    assert any(event.kind == "kernel-check-accepted" for event in output.trace)


def test_accepted_support_retains_evidence_and_subject_references():
    source = """
type Failure:
    | ModelFailure
    | SupportError
def Positive(value: Int) -> Prop
type Assured:
    subject: Int
    support: Supported[Positive(subject)]
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return accept_assessment("accepted for this fixture")
def main(model: Model, access: ModelGenerate) -> Result[Assured, Failure] ! {AI.Generate}:
    generated = try generate[Int](3, model, access)
    value = generated.value
    evidence = observe(value, source = "asserted candidate")
    policy = material_policy[Int, Positive(value), Never]("fixture", evaluator = evaluate)
    assessment = try evidence |~[policy] Positive(value)
    supported = try accept_support(assessment)
    return Ok(Assured(subject = value, support = supported))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == "accepted"
    evidence = _provenance_path(output, "value", "support", "evidence")
    activities = _provenance_activities(output, evidence)
    assert any(activity.kind == "generated" for activity in activities)
    assert any(activity.kind == "asserted" for activity in activities)
    subject = _provenance_path(output, "value", "subject")
    graph = output.provenance
    assert graph is not None
    references = {value.identity: value for value in graph.values}
    activities_by_id = {activity.identity: activity for activity in graph.activities}
    assert activities_by_id[references[subject].activity].kind == "generated"


def test_selection_and_computation_preserve_nested_generated_producers():
    source = """
type Outputs:
    selected: Generated[Int]
    computed: Computed[Generated[Int]]
def identity[A](value: A) -> A:
    return value
def main(model: Model, access: ModelGenerate) -> Result[Outputs, ModelFailure] ! {AI.Generate}:
    first = try generate[Int](1, model, access)
    second = try generate[Int](2, model, access)
    selected = second if first.value > 0 else first
    return Ok(Outputs(selected = selected, computed = compute(selected, procedure = identity)))
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value.fields["selected"].value == 2
    assert output.result.value.fields["computed"].value.value == 2
    graph = output.provenance
    assert graph is not None
    values = {value.identity: value for value in graph.values}
    activities = {activity.identity: activity for activity in graph.activities}
    for path in [("value", "selected"), ("value", "computed", "value")]:
        reference = _provenance_path(output, *path)
        assert activities[values[reference].activity].kind == "generated"
        assert (
            len(
                [
                    activity
                    for activity in _provenance_activities(output, reference)
                    if activity.kind == "generated"
                ]
            )
            == 2
        )
    computation = _provenance_path(output, "value", "computed")
    assert activities[values[computation].activity].kind == "computed"


def test_generated_index_is_a_dependency_without_changing_selected_producer():
    source = """
def main(model: Model, access: ModelGenerate) -> Result[Int, ModelFailure] ! {AI.Generate}:
    index = try generate[Int](1, model, access)
    values = [7, 9]
    return Ok(values[index.value])
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.result.value == 9
    reference = _provenance_path(output, "value")
    assert any(
        activity.kind == "generated"
        for activity in _provenance_activities(output, reference)
    )
    graph = output.provenance
    assert graph is not None
    selected = next(value for value in graph.values if value.identity == reference)
    assert (
        next(
            activity
            for activity in graph.activities
            if activity.identity == selected.activity
        ).kind
        == "literal"
    )


def test_reasoning_switch_retains_the_actual_handoff_ancestry():
    source = """
type State:
    count: Int
    Reframe: Bool
type Step = State -> State
reasoning Next(state: State) -> State:
    [result: Step(state)]
    return result
reasoning Plan(state: State) -> State:
    [result: Step(state)]
    on result.Reframe => switch @Next
    return result
def reframe(state: State) -> State:
    return State(count = state.count + 1, Reframe = True)
def finish(state: State) -> State:
    return State(count = state.count + 1, Reframe = False)
next_plan = Next(result = finish)
plan = Plan(result = reframe, Next = next_plan)
def main(initial: Int) -> State:
    state = State(count = initial, Reframe = False)
    return solve Plan(state) using plan(state)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))),
        handler=_fake_handler(),
        entry_arguments={"initial": 20},
    )
    assert output.result.fields["count"] == 22
    activities = _provenance_activities(output, _provenance_path(output, "count"))
    assert any(
        activity.kind == "supplied" and activity.operation == "input:initial"
        for activity in activities
    )


def _example_variant(example: str, replacements: dict[str, tuple[str, str]]):
    from dataclasses import replace

    class VariantLoader(WorkspaceModuleLoader):
        def load_module(self, name):
            module = super().load_module(name)
            if name in replacements:
                before, after = replacements[name]
                assert before in module.source
                return replace(module, source=module.source.replace(before, after))
            return module

    loader = VariantLoader(project_root=ROOT, entry_points=False)
    name = f"examples.language.{example}.main"
    module = loader.load_module(name)
    return compile(
        elaborate(
            check(parse_source(module.source, path=module.origin), module_loader=loader)
        )
    )


@pytest.mark.parametrize("computed", [False, True])
def test_strict_example_admits_both_declared_producers(computed):
    replacements = {}
    if computed:
        replacements["examples.language.strict_inference.main"] = (
            "import release_approval",
            "import computed_release_approval as release_approval",
        )
    output = run(
        _example_variant("strict_inference", replacements), handler=_fake_handler()
    )
    assert output.result == Ok(7)
    node = next(event for event in output.trace if event.kind == "workflow-node")
    assert node.outcome is not None
    assert node.outcome.contract == "satisfied"
    assert node.outcome.observed[0].producer == ("computed" if computed else "literal")
    assert node.outcome.observed[0].assurance == "unchecked"
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.outcome is not None
    assert relation.outcome.contract == "satisfied"
    assert relation.outcome.observed[0].assurance == "proved"


def test_strict_example_rejects_an_excluded_producer():
    executable = _example_variant(
        "strict_inference",
        {
            "examples.language.strict_inference.materialization": (
                "return approved",
                'asserted = observe(approved, source = "release list", method = "assertion")\n    return asserted.value',
            ),
        },
    )
    with pytest.raises(ValueError, match="producer 'asserted'"):
        run(executable, handler=_fake_handler())


@pytest.mark.parametrize("boundary", ["mission", "final_plan"])
def test_refinement_example_rejects_failed_validation(boundary):
    if boundary == "mission":
        replacements = {
            "examples.language.refinement_loop.main": (
                'description = "Land a throttleable 2D lunar lander safely inside the target zone."',
                'description = ""',
            )
        }
    else:
        replacements = {
            "examples.language.refinement_loop.simulation": (
                "        checks.inside_landing_zone\n        and checks.horizontal_speed_safe",
                "        False\n        and checks.horizontal_speed_safe",
            )
        }
    output = run(
        _example_variant("refinement_loop", replacements), handler=_fake_handler()
    )
    assert output.status == "rejected"
    rejected = [
        event
        for event in output.trace
        if event.kind == "validation" and event.status == "rejected"
    ]
    assert len(rejected) == 1
    assert rejected[0].name.endswith(
        "::mission_check" if boundary == "mission" else "::safe_under_model"
    )
    assert not any(event.kind == "kernel-check-accepted" for event in output.trace)
    if boundary == "mission":
        assert not any(event.kind == "agent-invoked" for event in output.trace)
    else:
        node = next(
            event
            for event in output.trace
            if event.kind == "workflow-node" and event.name == "safe_plan"
        )
        assert node.outcome is not None
        assert node.outcome.contract == "rejected"


@pytest.mark.parametrize("approved", [True, False])
def test_quick_start_validates_the_actual_candidate(approved):
    path = ROOT / "docs/static/examples/quick-start/main.prism"
    source = path.read_text().replace("approved = True", f"approved = {approved}")
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=_fake_handler()
    )
    assert output.status == ("accepted" if approved else "rejected")
    event = next(event for event in output.trace if event.kind == "validation")
    assert event.status == output.status
    if approved:
        assert isinstance(output.result.value, ValidatedValue)
        assert output.result.value.value.fields == {
            "tests_passed": True,
            "approved": True,
        }
