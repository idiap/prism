# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language import InMemoryModuleLoader, check, compile, elaborate, parse_source
from prism.language.core import CoreType
from prism.language.developer import PrismSyntaxError, PrismTypeError
from prism.language.developer.syntax import ReasoningDecl, RelationDecl
from prism.language.workflows import ReasoningDefinition
from prism.runtime import FakeEffectHandler, run

SOURCE = """type Input:
    text: String
type Candidate:
    text: String
type Status:
    | Accepted
    | Refuted
type EdgeError:
    | InvalidEdge
type CandidateMethod[Inputs] = Inputs -> Candidate
type VerdictMethod[Inputs] = Inputs -> Status
type Tested[SourceValue, TargetValue]:
    source: SourceValue
    target: TargetValue
    label: String
relation Test[SourceValue, TargetValue](source: SourceValue, target: TargetValue) -> Tested[SourceValue, TargetValue]
reasoning Review(source: Input) -> Status:
    sequence:
        [candidate: CandidateMethod(source)]
        [status: VerdictMethod(candidate)] by Test
    on status.Accepted => accept
    on status.Refuted => stop
    return status
def form_candidate(source: Input) -> Candidate:
    return Candidate(text = source.text)
def accept_candidate(candidate: Candidate) -> Status:
    return Accepted()
def build_test[SourceValue, TargetValue](
    source: SourceValue,
    target: TargetValue,
) -> Result[Tested[SourceValue, TargetValue], EdgeError]:
    return Ok(Tested(source = source, target = target, label = "checked"))
configured_review = Review(
    candidate = form_candidate,
    status = accept_candidate,
    status_by = build_test,
)
def main() -> Result[Status, FailureUnion[EdgeError, ReasoningStopped[Review]]]:
    source = Input(text = "candidate")
    flow = configured_review(source)
    return solve Review(source) using flow
"""


STRUCTURAL_SOURCE = """
def collect[A](value: A) -> List[A]:
    return [value, value]
type Step = List[Int] -> Int
reasoning Plan(value: Int) -> Int:
    sequence:
        [prepared: collect(value)]
        [result: Step(prepared)]
    return result
def choose(values: List[Int]) -> Int:
    return values[1]
configured = Plan(result = choose)
def main() -> Int:
    return solve Plan(3) using configured(3)
"""


def test_fixed_generic_structural_collector_has_no_materialization_slot():
    checked = check(parse_source(STRUCTURAL_SOURCE))
    assert tuple(checked.reasoning_methods["Plan"]) == ("result",)
    assert checked.callable_contracts["collect"].structural_error is None
    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())
    assert output.result == 3
    nodes = [event for event in output.trace if event.kind == "workflow-node"]
    assert [
        event.metadata["declared_contract"]["execution_kind"] for event in nodes
    ] == ["structural", "method"]
    assert nodes[0].outcome is not None
    assert (
        nodes[0].metadata["declared_contract"]["classification"]["archetype_state"]
        == "not_applicable"
    )
    assert nodes[0].outcome.contract == "satisfied"
    assert all(item.assurance == "unchecked" for item in nodes[0].outcome.observed)
    with pytest.raises(PrismTypeError, match="extra prepared"):
        check(
            parse_source(
                STRUCTURAL_SOURCE.replace(
                    "Plan(result = choose)", "Plan(prepared = collect, result = choose)"
                )
            )
        )


@pytest.mark.parametrize(
    "definition, call, expected",
    [
        (
            "def collect[A](first: A, second: A) -> List[A]:\n    return [first, second]",
            "collect(value, value + 1)",
            4,
        ),
        ("def collect() -> List[Int]:\n    return [5, 5]", "collect()", 5),
        (
            "def collect(value: Int) -> Result[List[Int], Never]:\n    return Ok([value, value])",
            "collect(value)",
            3,
        ),
    ],
)
def test_fixed_helpers_use_ordinary_callable_arguments(definition, call, expected):
    source = STRUCTURAL_SOURCE.replace(
        "def collect[A](value: A) -> List[A]:\n    return [value, value]", definition
    ).replace("collect(value)", call)
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.result == expected


@pytest.mark.parametrize("imported", [False, True])
def test_structural_helpers_cannot_hide_operational_work(imported):
    helpers = """
def hidden(value: Int) -> Int:
    backend = inline_resource("backend", "YQ==", "hash")
    return value
def prepare(value: Int) -> Int:
    return hidden(value)
"""
    topology = """
reasoning Plan(value: Int) -> Int:
    [result: prepare(value)]
    return result
"""
    source = (
        "from helpers import prepare\n" + topology if imported else helpers + topology
    )
    loader = InMemoryModuleLoader({"helpers": helpers}) if imported else None
    with pytest.raises(PrismTypeError, match="structural helper.*Resource"):
        check(parse_source(source), module_loader=loader)


def test_logical_input_helpers_are_audited_transitively():
    source = """
def hidden(value: Int) -> Int:
    backend = inline_resource("backend", "YQ==", "hash")
    return value
type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(hidden(value))]
    return result
"""
    with pytest.raises(PrismTypeError, match="structural helper.*Resource"):
        check(parse_source(source))


def test_structural_transforms_cannot_hide_an_unaudited_callback():
    source = """
def hidden(value: Int) -> Int:
    backend = inline_resource("backend", "YQ==", "hash")
    return value
callback = hidden
def prepare(value: Int) -> Computed[Int]:
    return compute(value, procedure = callback)
reasoning Plan(value: Int) -> Computed[Int]:
    [result: prepare(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="dynamic callable"):
        check(parse_source(source))


@pytest.mark.parametrize(
    "signature, body",
    [
        ("Int ! {Python.Call}", "return value"),
        ("Result[Int, String]", 'return Err("failed")'),
        ("Evidence[Int]", 'return observe(value, source = "backend")'),
    ],
)
def test_structural_helpers_reject_effects_failures_and_source_assertions(
    signature, body
):
    output_type = "Evidence[Int]" if signature == "Evidence[Int]" else "Int"
    source = f"""
def prepare(value: Int) -> {signature}:
    {body}
reasoning Plan(value: Int) -> {output_type}:
    [result: prepare(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="operational|structural"):
        check(parse_source(source))


def test_imported_structural_helper_preserves_its_audited_body():
    helper = "def duplicate[A](value: A) -> List[A]:\n    return [value, value]\n"
    source = STRUCTURAL_SOURCE.replace(
        "def collect[A](value: A) -> List[A]:\n    return [value, value]",
        "from helpers import duplicate as collect",
    )
    checked = check(
        parse_source(source), module_loader=InMemoryModuleLoader({"helpers": helper})
    )
    assert checked.callable_contracts["collect"].structural_error is None
    assert run(compile(elaborate(checked)), handler=FakeEffectHandler()).result == 3


def test_imported_reasoning_retains_its_fixed_helpers():
    boundary = STRUCTURAL_SOURCE.index("def choose")
    library = STRUCTURAL_SOURCE[:boundary]
    source = "from plans import Plan\n" + STRUCTURAL_SOURCE[boundary:]
    checked = check(
        parse_source(source), module_loader=InMemoryModuleLoader({"plans": library})
    )
    assert run(compile(elaborate(checked)), handler=FakeEffectHandler()).result == 3


def test_fixed_helper_can_have_an_explicit_relation_binding():
    source = (
        STRUCTURAL_SOURCE.replace(
            "type Step =",
            "type Certificate:\n    source: Int\n    target: List[Int]\n"
            "relation Collects(source: Int, target: List[Int]) -> Certificate\n"
            "def certify(source: Int, target: List[Int]) -> Certificate:\n"
            "    return Certificate(source = source, target = target)\n"
            "type Step =",
        )
        .replace("[prepared: collect(value)]", "[prepared: collect(value)] by Collects")
        .replace(
            "Plan(result = choose)", "Plan(result = choose, prepared_by = certify)"
        )
    )
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.result == 3
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.metadata["certificate_valid"] is True


def test_fixed_helper_preserves_existing_validation():
    source = """
def Positive(value: Int) -> Prop
type PositiveValue = Validated[item: Int, Positive(item)]
def positive(value: Int) -> Bool:
    return value > 0
registered = validator[value: Int, Positive(value)](positive)
def identity(value: PositiveValue) -> PositiveValue:
    return value
reasoning Plan(value: PositiveValue) -> PositiveValue:
    [result: identity(value)]
    return result
configured = Plan()
def main() -> Result[PositiveValue, ValidationError]:
    value = try validate[Positive(3)](3, validator = registered)
    result = solve Plan(value) using configured(value)
    return Ok(result)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.result.value.value == 3
    node = next(event for event in output.trace if event.kind == "workflow-node")
    assert node.outcome is not None
    assert node.outcome.observed[0].assurance == "validated"
    assert node.metadata["input_reference"] == node.metadata["output_reference"]


def test_fixed_helper_cannot_establish_a_new_verified_pair():
    source = """
def Truth(value: Nat) -> Prop:
    return value == value
type Input:
    value: Nat
    proof: Proof[Truth(value)]
def attach(value: Input) -> Verified[item: Nat, Truth(item)]:
    return verify(value.value, value.proof)
reasoning Plan(value: Input) -> Verified[item: Nat, Truth(item)]:
    [result: attach(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="uses operation verify"):
        check(parse_source(source))


def test_fixed_structural_helpers_carry_repeat_state_without_configuration_slots():
    source = """
type State:
    count: Int
    done: Bool
def advance(state: State) -> State:
    count = state.count + 1
    return State(count = count, done = count >= 2)
reasoning Loop(state: State) -> State:
    repeat refinement_policy(3, until = state.done):
        [state: advance(state)]
    return state
configured = Loop()
def main() -> State:
    initial = State(count = 0, done = False)
    return solve Loop(initial) using configured(initial)
"""
    checked = check(parse_source(source))
    assert checked.reasoning_methods["Loop"] == {}
    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())
    assert output.result.fields["count"] == 2
    nodes = [event for event in output.trace if event.kind == "workflow-node"]
    assert len(nodes) == 2
    assert all(
        event.metadata["declared_contract"]["execution_kind"] == "structural"
        for event in nodes
    )


def test_abstract_choice_with_fixed_helpers_is_exhaustive_and_converges():
    source = """
type Route:
    | Static
    | Dynamic
def choose(route: Route) -> Route:
    return route
def static_value(route: Route) -> Int:
    return 1
def dynamic_value(route: Route) -> Int:
    return 2
type Step = Int -> Int
reasoning Plan(route: Route) -> Int:
    sequence:
        choice [selected: choose(route)]:
            case Static:
                [prepared: static_value(selected)]
            case Dynamic:
                [prepared: dynamic_value(selected)]
        [result: Step(prepared)]
    return result
def identity(value: Int) -> Int:
    return value
configured = Plan(result = identity)
def main() -> Int:
    return solve Plan(Dynamic()) using configured(Dynamic())
"""
    checked = check(parse_source(source))
    assert tuple(checked.reasoning_methods["Plan"]) == ("result",)
    assert run(compile(elaborate(checked)), handler=FakeEffectHandler()).result == 2
    with pytest.raises(PrismTypeError, match="not exhaustive"):
        check(
            parse_source(
                source.replace(
                    "            case Dynamic:\n                [prepared: dynamic_value(selected)]\n",
                    "",
                )
            )
        )
    with pytest.raises(PrismTypeError, match="converge"):
        check(
            parse_source(
                source.replace(
                    "[prepared: dynamic_value(selected)]",
                    "[different: dynamic_value(selected)]",
                )
            )
        )


@pytest.mark.parametrize(
    "hidden_type",
    [
        "Model",
        "ModelGenerate",
        "List[Model]",
        "Option[ModelGenerate]",
        "Int -> Model",
        "ModelGenerate -> Int",
        "Int -> Result[Int, String]",
        "Int -> Int ! {Python.Call}",
    ],
)
def test_reasoning_rejects_operational_types_hidden_in_records(hidden_type):
    source = f"""
type Hidden:
    operation: {hidden_type}
type Envelope[A]:
    value: A
type Step = Envelope[Hidden] -> Int
reasoning Plan(value: Envelope[Hidden]) -> Int:
    [result: Step(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="cannot carry operational type"):
        check(parse_source(source))


def test_reasoning_rejects_an_imported_alias_hiding_a_permission():
    loader = InMemoryModuleLoader(
        {
            "operations": """
type Hidden:
    access: ModelGenerate
type Payload = List[Hidden]
"""
        }
    )
    source = """
from operations import Payload
type Step = Payload -> Int
reasoning Plan(value: Payload) -> Int:
    [result: Step(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="cannot carry operational type"):
        check(parse_source(source), module_loader=loader)


def test_reasoning_purity_inspects_recursive_records_and_variant_payloads():
    source = """
type Chain:
    next: Option[Chain]
    hidden: Payload
type Payload:
    | Domain(value: Int)
    | Operational(access: ModelGenerate)
type Step = Chain -> Int
reasoning Plan(value: Chain) -> Int:
    [result: Step(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="cannot carry operational type"):
        check(parse_source(source))


def test_reasoning_accepts_a_domain_string_literal():
    source = """
type Step = String -> String
reasoning Plan(value: String) -> String:
    [result: Step("domain category")]
    return result
def identity(value: String) -> String:
    return value
configured = Plan(result = identity)
def main() -> String:
    return solve Plan("input") using configured("input")
"""
    assert (
        run(
            compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
        ).result
        == "domain category"
    )


def test_reasoning_rejects_operational_method_outputs():
    source = """
type Hidden:
    access: ModelGenerate
type Step = Int -> Hidden
reasoning Plan(value: Int) -> Hidden:
    [result: Step(value)]
    return result
"""
    with pytest.raises(PrismTypeError, match="operational type `ModelGenerate`"):
        check(parse_source(source))


def test_relation_inference_judgments_desugar_to_assurance_certificates() -> None:
    program = parse_source("""
type Endpoint:
    value: String
def MateriallyRelated(source: Endpoint, target: Endpoint) -> Prop:
    return claim("material relation")
def StrictlyRelated(source: Endpoint, target: Endpoint) -> Prop:
    return claim("strict relation")
relation Material(source: Endpoint, target: Endpoint) |~ MateriallyRelated(source, target)
relation Strict(source: Endpoint, target: Endpoint) |- StrictlyRelated(source, target)
""")
    relations = {
        declaration.name: declaration
        for declaration in program.declarations
        if isinstance(declaration, RelationDecl)
    }

    assert relations["Material"].result.text == (
        "Supported[MateriallyRelated(source, target)]"
    )
    assert relations["Strict"].result.text == ("Proof[StrictlyRelated(source, target)]")

    checked = check(program)
    assert checked.callable_contracts["Material"].result.render() == (
        "Supported[MateriallyRelated(source, target)]"
    )
    assert checked.callable_contracts["Strict"].result.render() == (
        "Proof[StrictlyRelated(source, target)]"
    )


def test_material_relation_judgment_rejects_an_embedded_policy() -> None:
    with pytest.raises(PrismSyntaxError, match="omit the policy"):
        parse_source("""
type Endpoint:
    value: String
def Related(source: Endpoint, target: Endpoint) -> Prop:
    return claim("related")
relation Material(source: Endpoint, target: Endpoint) |~[policy] Related(source, target)
""")


def test_user_defined_method_and_relation_compile_run_and_trace() -> None:
    program = parse_source(SOURCE)
    assert any(isinstance(item, RelationDecl) for item in program.declarations)
    assert any(isinstance(item, ReasoningDecl) for item in program.declarations)

    checked = check(program)
    executable = compile(elaborate(checked))
    reasoning = next(
        item
        for item in executable.declarations
        if isinstance(item, ReasoningDefinition) and item.name == "Review"
    )
    status_node = reasoning.composition.children[1]
    assert status_node.method_type.render() == "(Candidate) -> Status"
    assert status_node.input_type.render() == "Candidate"
    assert status_node.output_type.render() == "Status"
    assert status_node.relation_type.render() == (
        "Relation[Test, Candidate, Status, Tested[Candidate, Status]]"
    )
    assert status_node.certificate_type.render() == "Tested[Candidate, Status]"

    output = run(executable, handler=FakeEffectHandler())

    assert output.status == "accepted"
    assert checked.reasoning_methods["Review"]["status"].render() == (
        "(Candidate) -> Status"
    )
    occurrence = next(event for event in output.trace if event.name == "status")
    reasoning_steps = [
        event
        for event in output.trace
        if event.kind == "workflow-node" and "method_type" in event.metadata
    ]
    assert [event.name for event in reasoning_steps] == ["candidate", "status"]
    assert reasoning_steps[0].metadata["reasoning"] == "Review"
    assert reasoning_steps[0].status == "accepted"
    assert reasoning_steps[0].metadata["result"].fields["text"] == "candidate"
    assert reasoning_steps[1].metadata["result"].type_name == "Accepted"
    serialized_steps = [
        event
        for event in output.to_dict()["trace"]
        if event["kind"] == "workflow-node" and "method_type" in event["metadata"]
    ]
    assert serialized_steps[0]["metadata"]["result"] == {
        "type_name": "Candidate",
        "fields": {"text": "candidate"},
    }
    assert occurrence.metadata["input_type"] == "Candidate"
    assert occurrence.metadata["output_type"] == "Status"
    assert (
        occurrence.metadata["implementation_type"] == "(candidate: Candidate) -> Status"
    )
    assert occurrence.metadata["failure_type"] == "Never"
    assert occurrence.metadata["effects"] == ()
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.name == "Test"
    assert relation.assurance is None
    assert relation.metadata["source_type"] == "Candidate"
    assert relation.metadata["target_type"] == "Status"
    assert relation.metadata["certificate_type"] == "Tested[Candidate, Status]"
    assert relation.metadata["builder_type"].endswith(
        "Result[Tested[SourceValue, TargetValue], EdgeError]"
    )
    assert relation.metadata["failure_type"] == "EdgeError"
    assert relation.metadata["effects"] == ()
    assert relation.metadata["certificate"].type_name == "Tested"


INPUT_ADAPTER_SOURCE = """type Raw:
    text: String
type SemanticInput:
    raw: Raw
    prefix: String
type Status:
    text: String
type Certificate:
    source: SemanticInput
    target: Status
type Seed = Raw -> Raw
type Assess = SemanticInput -> Status
relation Test(source: SemanticInput, target: Status) -> Certificate
reasoning Review(raw: Raw) -> Status:
    sequence:
        [seed: Seed(raw)]
        [status: Assess(seed)] by Test
    return status
def preserve(raw: Raw) -> Raw:
    return raw
def prepare(source: Raw, prefix: String) -> SemanticInput:
    return SemanticInput(raw = source, prefix = prefix)
def assess(source: SemanticInput) -> Status:
    return Status(text = source.prefix)
def certify(source: SemanticInput, target: Status) -> Certificate:
    return Certificate(source = source, target = target)
configured = Review(
    seed = preserve,
    status_input = prepare,
    status = assess,
    status_by = certify,
)
def main() -> Status:
    raw = Raw(text = "visible")
    return solve Review(raw) using configured(raw, prefix = "adapted")
"""


def test_reasoning_input_adapter_bridges_visible_and_semantic_inputs() -> None:
    checked = check(parse_source(INPUT_ADAPTER_SOURCE))
    configured = checked.globals["configured"].type
    assert configured.parameters == (
        ("raw", CoreType("Raw")),
        ("prefix", CoreType("String")),
    )

    executable = compile(elaborate(checked))
    reasoning = next(
        item
        for item in executable.declarations
        if isinstance(item, ReasoningDefinition) and item.name == "Review"
    )
    status_node = reasoning.composition.children[1]
    assert status_node.input_adapter is not None
    assert status_node.topology_input_type == CoreType("Raw")
    assert status_node.input_type == CoreType("SemanticInput")

    output = run(executable, handler=FakeEffectHandler())
    assert output.status == "accepted"
    assert output.result.fields["text"] == "adapted"

    occurrence = next(event for event in output.trace if event.name == "status")
    assert occurrence.metadata["topology_input_type"] == "Raw"
    assert occurrence.metadata["input_type"] == "SemanticInput"
    assert occurrence.metadata["input_adapter_type"] == (
        "(source: Raw, prefix: String) -> SemanticInput"
    )
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.metadata["source_type"] == "SemanticInput"
    assert relation.metadata["certificate"].fields["source"].fields["prefix"] == (
        "adapted"
    )


def test_reasoning_repeat_carries_state_and_resumes_after_switch() -> None:
    source = """type Gap:
    attempt: Int
type Status:
    gap: Gap
    Reframe: Bool
    Finished: Bool
type Assess = Gap -> Status
type NextGap = Status -> Gap
type Reroute = Status -> Status
reasoning RerouteLoop(handoff: Status) -> Status:
    [status: Reroute(handoff)]
    return status
reasoning Loop(gap: Gap) -> Status:
    repeat refinement_policy(5, until = status.Finished):
        [status: Assess(gap)]
        [gap: NextGap(status)]
    on status.Reframe => switch @RerouteLoop
    return status
def assess(gap: Gap) -> Status:
    next = Gap(attempt = gap.attempt + 1)
    return Status(gap = next, Reframe = gap.attempt == 0, Finished = next.attempt >= 3)
def reroute(status: Status) -> Status:
    return Status(gap = Gap(attempt = status.gap.attempt + 1), Reframe = False, Finished = False)
def next_gap(status: Status) -> Gap:
    return status.gap
reroute_loop = RerouteLoop(status = reroute)
loop = Loop(status = assess, gap = next_gap, RerouteLoop = reroute_loop)
def main() -> Status:
    initial = Gap(attempt = 0)
    return solve Loop(initial) using loop(initial)
"""

    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )

    assert output.result.fields["gap"].fields["attempt"] == 3
    assert output.result.fields["Finished"] is True
    assert (
        len(
            [
                event
                for event in output.trace
                if event.kind == "workflow-node" and event.name == "status"
            ]
        )
        == 3
    )
    assert any(event.kind == "reasoning-exit" for event in output.trace)


def test_reasoning_input_adapter_is_required_when_topology_input_is_concise() -> None:
    with pytest.raises(PrismTypeError, match="missing status_input"):
        check(
            parse_source(
                INPUT_ADAPTER_SOURCE.replace("    status_input = prepare,\n", "")
            )
        )


def test_reasoning_input_adapter_must_be_pure_and_return_semantic_input() -> None:
    effectful = INPUT_ADAPTER_SOURCE.replace(
        "def prepare(source: Raw, prefix: String) -> SemanticInput:",
        "def prepare(source: Raw, prefix: String) -> SemanticInput ! {AI.Generate}:",
    )
    with pytest.raises(
        PrismTypeError, match="input adapter `status_input` must be pure"
    ):
        check(parse_source(effectful))

    wrong_result = INPUT_ADAPTER_SOURCE.replace(
        "def prepare(source: Raw, prefix: String) -> SemanticInput:\n"
        "    return SemanticInput(raw = source, prefix = prefix)",
        "def prepare(source: Raw, prefix: String) -> Raw:\n    return source",
    )
    with pytest.raises(
        PrismTypeError,
        match="input adapter `status_input` result expects SemanticInput",
    ):
        check(parse_source(wrong_result))


def test_imported_configuration_carries_its_relation_declaration() -> None:
    contracts = """type Input:
    text: String
type Status:
    text: String
type Prepare = Input -> Status
type Method = Status -> Status
type Certificate:
    source: Status
    target: Status
relation Relates(source: Status, target: Status) -> Certificate
reasoning Review(source: Input) -> Status:
    sequence:
        [prepared: Prepare(source)]
        [status: Method(prepared)] by Relates
    return status
"""
    materialization = """from contracts import (
    Certificate,
    Input,
    Relates,
    Review,
    Status,
)
def prepare(source: Input) -> Status:
    return Status(text = source.text)
def materialize(source: Status) -> Status:
    return source
def certify(source: Status, target: Status) -> Certificate:
    return Certificate(source = source, target = target)
configured = Review(
    prepared = prepare,
    status = materialize,
    status_by = certify,
)
"""
    main = """from contracts import Input, Review, Status
from materialization import configured
def main() -> Status:
    source = Input(text = "ready")
    return solve Review(source) using configured(source)
"""
    loader = InMemoryModuleLoader(
        {"contracts": contracts, "materialization": materialization}
    )

    output = run(
        compile(elaborate(check(parse_source(main), module_loader=loader))),
        handler=FakeEffectHandler(),
    )

    assert output.status == "accepted"
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    assert relation.metadata["certificate_type"] == "Certificate"


def test_partial_method_specialization_infers_trailing_input_index() -> None:
    source = """type Input:
    text: String
type Tagged[P]:
    source: Input
type TagMethod[P, Inputs] = Inputs -> Tagged[P]
reasoning Tag[P](source: Input) -> Tagged[P]:
    [tagged: TagMethod[P](source)]
    return tagged
"""
    checked = check(parse_source(source))

    assert checked.reasoning_methods["Tag"]["tagged"] == CoreType(
        "Function",
        parameters=((None, CoreType("Input")),),
        result=CoreType("Tagged", (CoreType("P"),)),
    )
    assert checked.reasoning_outputs["Tag"]["tagged"].render() == "Tagged[P]"


def test_wrong_occurrence_success_type_is_rejected_at_configuration() -> None:
    with pytest.raises(
        PrismTypeError, match="occurrence binding `candidate` result expects Candidate"
    ):
        check(
            parse_source(
                SOURCE.replace(
                    "def form_candidate(source: Input) -> Candidate:\n"
                    "    return Candidate(text = source.text)",
                    "def form_candidate(source: Input) -> Input:\n    return source",
                )
            )
        )


def test_relation_builder_success_type_is_declaration_directed() -> None:
    with pytest.raises(PrismTypeError, match="certificate expects Tested"):
        check(
            parse_source(
                SOURCE.replace(
                    ") -> Result[Tested[SourceValue, TargetValue], EdgeError]:",
                    ") -> Result[Candidate, EdgeError]:",
                ).replace(
                    'return Ok(Tested(source = source, target = target, label = "checked"))',
                    'return Ok(Candidate(text = "wrong"))',
                )
            )
        )


def test_relation_failure_is_inferred_without_a_compiler_owned_error() -> None:
    checked = check(parse_source(SOURCE))
    configured = checked.globals["configured_review"].type

    assert configured.result is not None
    workflow = configured.result
    assert workflow.name == "Workflow"
    assert workflow.arguments[1].render() == (
        "FailureUnion[EdgeError, ReasoningStopped[Review]]"
    )


def test_relation_builder_must_be_pure() -> None:
    effectful = SOURCE.replace(
        ") -> Result[Tested[SourceValue, TargetValue], EdgeError]:",
        ") -> Result[Tested[SourceValue, TargetValue], EdgeError] ! {AI.Generate}:",
    )
    with pytest.raises(
        PrismTypeError, match="relation builder `status_by` must be pure"
    ):
        check(parse_source(effectful))


def test_relation_builder_receives_the_complete_tuple_source() -> None:
    source = """type Item:
    value: String
type Combined:
    value: String
type PairMethod[Left, Right] = ((Left, Right)) -> Combined
type Paired[InputValue, OutputValue]:
    source: InputValue
    target: OutputValue
relation Pair[InputValue, OutputValue](source: InputValue, target: OutputValue) -> Paired[InputValue, OutputValue]
reasoning Combine(first: Item) -> Combined:
    sequence:
        [second: PairMethod((first, first))]
        [combined: PairMethod((second, first))] by Pair
    return combined
def make_combined[Left, Right](source: (Left, Right)) -> Combined:
    return Combined(value = "combined")
def build_pair[InputValue, OutputValue](source: InputValue, target: OutputValue) -> Paired[InputValue, OutputValue]:
    return Paired(source = source, target = target)
configured = Combine(second = make_combined, combined = make_combined, combined_by = build_pair)
def main() -> Combined:
    first = Item(value = "first")
    return solve Combine(first) using configured(first)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    relation = next(
        event for event in output.trace if event.kind == "reasoning-relation"
    )
    complete_source = relation.metadata["certificate"].fields["source"]
    assert complete_source[0].type_name == "Combined"
    assert complete_source[1].type_name == "Item"
    assert complete_source[1].fields["value"] == "first"


def test_relation_on_composition_block_is_rejected() -> None:
    source = SOURCE.replace("    sequence:", "    sequence by Test:")
    with pytest.raises(PrismTypeError, match="allowed only on a reasoning occurrence"):
        check(parse_source(source))


def test_relation_certificate_missing_proof_field_is_uninhabitable() -> None:
    source = """def Invariant() -> Prop:
    return claim("the invariant holds")
type Certificate:
    proof: Proof[Invariant()]
def invalid() -> Certificate:
    return Certificate()
"""
    with pytest.raises(PrismTypeError, match="requires exact named fields"):
        check(parse_source(source))


def test_reasoning_must_be_configured_before_invocation() -> None:
    with pytest.raises(PrismTypeError, match="requires named bindings"):
        check(
            parse_source(SOURCE.replace("configured_review(source)", "Review(source)"))
        )


def test_reasoning_implementation_is_total() -> None:
    with pytest.raises(PrismTypeError, match="configuration `Review` is not total"):
        check(parse_source(SOURCE.replace("    status_by = build_test,\n", "")))


def test_stop_exit_preserves_a_typed_reasoning_failure() -> None:
    output = run(
        compile(
            elaborate(
                check(
                    parse_source(
                        SOURCE.replace("return Accepted()", "return Refuted()")
                    )
                )
            )
        ),
        handler=FakeEffectHandler(),
    )

    assert output.status == "rejected"
    assert output.result.error.reasoning == "Review"
    assert output.result.error.selector == "Refuted"


@pytest.mark.parametrize("operation", ["solve", "execute"])
def test_resolution_rejects_different_logical_arguments_before_steps(
    operation: str,
) -> None:
    source = f"""type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
def increment(value: Int) -> Int:
    return value + 1
configured = Plan(result = increment)
def main() -> {"Int" if operation == "solve" else "Execution[Int, Never]"}:
    return {operation} Plan(1) using configured(999)
"""
    from prism.runtime.engine import _Engine

    executable = compile(elaborate(check(parse_source(source))))
    from prism.language.kernel import Kernel
    from prism.runtime.replay import EffectRecorder

    engine = _Engine(
        executable, FakeEffectHandler(), Kernel(), None, EffectRecorder(), None, None
    )
    with pytest.raises(ValueError, match="different logical arguments"):
        engine.execute()
    assert not any(event.name == "increment" for event in engine.trace)


@pytest.mark.parametrize("operation", ["solve", "execute"])
def test_resolution_accepts_equal_records_named_arguments_and_operational_inputs(
    operation: str,
) -> None:
    source = f"""type Input:
    value: Int
type Step = Input -> Int
reasoning Plan(source: Input) -> Int:
    [result: Step(source)]
    return result
def increment(source: Input, offset: Int) -> Int:
    return source.value + offset
configured = Plan(result = increment)
def main() -> {"Int" if operation == "solve" else "Execution[Int, Never]"}:
    value = Input(value = 1)
    alias = value
    flow = configured(offset = 41, source = alias)
    return {operation} Plan(source = Input(value = 1)) using flow
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.status == "accepted"
    assert (output.result if operation == "solve" else output.result.result) == 42


def test_resolution_rejects_a_different_modules_same_named_plan() -> None:
    module = """type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
"""
    source = """import first as requested
import second as actual
def increment(value: Int) -> Int:
    return value + 1
configured = actual.Plan(result = increment)
def main() -> Int:
    return solve requested.Plan(1) using configured(1)
"""
    executable = compile(
        elaborate(
            check(
                parse_source(source),
                module_loader=InMemoryModuleLoader({"first": module, "second": module}),
            )
        )
    )
    with pytest.raises(ValueError, match="does not materialize"):
        run(executable, handler=FakeEffectHandler())


def test_resolution_accepts_renamed_imports_of_the_same_plan() -> None:
    module = """type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
"""
    source = """import plans as requested
from plans import Plan as Alias
def increment(value: Int) -> Int:
    return value + 1
configured = Alias(result = increment)
def main() -> Int:
    return solve requested.Plan(1) using configured(1)
"""
    output = run(
        compile(
            elaborate(
                check(
                    parse_source(source),
                    module_loader=InMemoryModuleLoader({"plans": module}),
                )
            )
        ),
        handler=FakeEffectHandler(),
    )
    assert output.result == 2


@pytest.mark.parametrize("specialization", ["Int", "String"])
def test_resolution_checks_specialization_even_when_result_types_match(
    specialization: str,
) -> None:
    source = f"""type Step = Int -> Int
reasoning Plan[Tag](value: Int) -> Int:
    [result: Step(value)]
    return result
def increment(value: Int) -> Int:
    return value + 1
configured = Plan[Int](result = increment)
def main() -> Int:
    return solve Plan[{specialization}](1) using configured(1)
"""
    executable = compile(elaborate(check(parse_source(source))))
    if specialization == "Int":
        assert run(executable, handler=FakeEffectHandler()).result == 2
    else:
        with pytest.raises(ValueError, match="different type specialization"):
            run(executable, handler=FakeEffectHandler())


def test_generic_reasoning_specializes_its_logical_and_occurrence_types() -> None:
    source = """type Step[A] = A -> A
reasoning Plan[A](value: A) -> A:
    [result: Step(value)]
    return result
def increment(value: Int) -> Int:
    return value + 1
configured = Plan[Int](result = increment)
def main() -> Int:
    return solve Plan(1) using configured(1)
"""
    checked = check(parse_source(source))
    result_type = checked.globals["configured"].type.result
    assert result_type is not None
    invocation = result_type.invocation
    assert invocation is not None
    assert invocation.specialization == (CoreType("Int"),)
    assert invocation.parameters[0].type == CoreType("Int")
    output = run(compile(elaborate(checked)), handler=FakeEffectHandler())
    assert output.result == 2


def test_resolution_keeps_invocations_through_nested_and_first_class_workflows() -> (
    None
):
    source = """type Step = Int -> Int
type Factory = (value: Int) -> Workflow[Int, Never]
reasoning Inner(value: Int) -> Int:
    [result: Step(value)]
    return result
reasoning Outer(value: Int) -> Int:
    [result: Step(value)]
    return result
def increment(value: Int) -> Int:
    return value + 1
inner = Inner(result = increment)
def nested(value: Int) -> Int:
    factory: Factory = inner
    return solve Inner(value) using factory(value)
outer = Outer(result = nested)
def main() -> Int:
    return solve Outer(1) using outer(1)
"""
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.result == 2
    assert [
        event.name for event in output.trace if event.kind == "reasoning-started"
    ] == ["Outer", "Inner"]


def test_resolution_evaluates_each_supplied_argument_expression_once() -> None:
    source = """type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
def argument(value: Int) -> Int:
    return value
def identity(value: Int) -> Int:
    return value
configured = Plan(result = identity)
def main() -> Int:
    return solve Plan(argument(1)) using configured(argument(1))
"""
    executable = compile(elaborate(check(parse_source(source))))
    output = run(executable, handler=FakeEffectHandler())
    assert output.result == 1
    assert (
        sum(
            event.kind == "function-call" and event.name == "argument"
            for event in output.trace
        )
        == 2
    )
    ordinary = source.replace(
        "solve Plan(argument(1)) using configured(argument(1))", "solve configured(1)"
    )
    assert (
        run(
            compile(elaborate(check(parse_source(ordinary)))),
            handler=FakeEffectHandler(),
        ).result
        == 1
    )


def test_wrong_invocation_prevents_effectful_materializers() -> None:
    from prism.language.effects import EffectRequest, EffectResult

    class RecordingHandler:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def handles(self, symbol: str, effects: tuple[str, ...]) -> bool:
            return True

        def execute(self, request: EffectRequest) -> EffectResult:
            self.calls.append(request.symbol)
            raise AssertionError("mismatched invocation reached an effect")

    source = """type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)]
    return result
def calculate(value: Int, access: PythonCall) -> Result[Int, PythonError] ! {Python.Call}:
    return python_call[Int]("test.calculate", value, access)
configured = Plan(result = calculate)
def main(access: PythonCall) -> Result[Int, PythonError] ! {Python.Call}:
    return solve Plan(1) using configured(999, access)
"""
    handler = RecordingHandler()
    with pytest.raises(ValueError, match="different logical arguments"):
        run(compile(elaborate(check(parse_source(source)))), handler=handler)
    assert handler.calls == []


def test_generic_reasoning_configuration_infers_specialization_from_materializers() -> (
    None
):
    source = """type Step[A] = A -> A
reasoning Plan[A](value: A) -> A:
    [result: Step(value)]
    return result
def increment(value: Int) -> Int:
    return value + 1
configured = Plan(result = increment)
def main() -> Int:
    return solve Plan(1) using configured(1)
"""
    assert (
        run(
            compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
        ).result
        == 2
    )


PROVEN_RELATION_SOURCE = """
def Same(source: Nat, target: Nat) -> Prop:
    return source == target
type Step = Nat -> Nat
relation Certifies(source: Nat, target: Nat) |- Same(source, target)
reasoning Plan(value: Nat) -> Nat:
    sequence:
        [result: Step(value)] by Certifies
        [finished: Step(result)]
    return finished
def produce(value: Nat) -> Nat:
    return value
def finish(value: Nat) -> Nat:
    return value
def certify(source: Nat, target: Nat) -> Result[Proof[Same(source, target)], ProofError]:
    term = try elaborate_proof[Same(source, target)]("rfl")
    return kernel.check(term)
configured = Plan(result = produce, result_by = certify, finished = finish)
def main() -> Result[Nat, ProofError]:
    initial: Nat = 1
    return solve Plan(initial) using configured(initial)
"""


@pytest.mark.parametrize("decision", ["accept", "reject", "inconclusive"])
def test_completed_assessment_occurrence_keeps_disposition_independent(decision):
    source = f"""
def Positive(value: Int) -> Prop
packet = observe(1, source = "fixture")
def evaluate(evidence: Evidence[Int], value: Int) -> PolicyDecision:
    return {decision}_assessment("decision")
policy = material_policy[Int, Positive(1), Never]("evaluation", evaluator = evaluate)
type Step = Int -> Assessment[Positive(1)]
reasoning Plan(value: Int) -> Assessment[Positive(1)]:
    [result: Step(value)]
    return result
def produce(value: Int) -> Result[Assessment[Positive(1)], Never]:
    return packet |~[policy] Positive(1)
configured = Plan(result = produce)
def main() -> Assessment[Positive(1)]:
    return solve Plan(1) using configured(1)
"""
    output = _relation_engine(source).execute()
    assert output.status == "accepted"
    event = next(event for event in output.trace if event.kind == "workflow-node")
    assert event.outcome is not None
    assert event.outcome.execution == "completed"
    assert event.outcome.contract == "satisfied"
    dispositions = {
        "accept": "accepted",
        "reject": "rejected",
        "inconclusive": "inconclusive",
    }
    observed = next(
        item
        for item in event.outcome.observed
        if item.claim_disposition != "not_applicable"
    )
    assert observed.claim_disposition == dispositions[decision]
    assert observed.assurance == "unchecked"


@pytest.mark.parametrize("mismatch", ["input", "output", "effects", "failure"])
def test_runtime_rechecks_materializer_signature_before_invocation(
    monkeypatch, mismatch
):
    from dataclasses import replace

    from prism.language.core import CoreType
    from prism.language.effects import Reference

    runtime = _relation_engine(PROVEN_RELATION_SOURCE)
    evaluate = runtime._eval

    def tampered(expression, environment):
        value = evaluate(expression, environment)
        if (
            isinstance(expression, Reference)
            and expression.name == "__reasoning_implementation_result"
        ):
            changes = {
                "input": {"parameters": (("value", CoreType("String")),)},
                "output": {"result_type": CoreType("String")},
                "effects": {"effects": ("AI.Generate",)},
                "failure": {
                    "result_type": CoreType(
                        "Result", (CoreType("Nat"), CoreType("String"))
                    )
                },
            }[mismatch]
            value = replace(value, definition=replace(value.definition, **changes))
        return value

    monkeypatch.setattr(runtime, "_eval", tampered)
    with pytest.raises(ValueError, match="occurrence materializer"):
        runtime.execute()
    assert not any(
        event.kind == "function-call" and event.name == "produce"
        for event in runtime.trace
    )
    occurrence = next(event for event in runtime.trace if event.kind == "workflow-node")
    assert occurrence.outcome is not None
    assert occurrence.outcome.execution == "failed"
    assert occurrence.outcome.contract == "rejected"


def test_ordinary_occurrence_records_a_failure_during_call_evaluation(monkeypatch):
    source = """
def prepare(value: Int) -> Int:
    return value
workflow Plan() -> Int:
    [result: prepare(7)]
def main() -> Int:
    return solve Plan()
"""
    runtime = _relation_engine(source)
    invoke = runtime._call

    def failed(callee, *args, **kwargs):
        if getattr(getattr(callee, "definition", None), "name", None) == "prepare":
            raise ValueError("materializer failed during invocation")
        return invoke(callee, *args, **kwargs)

    monkeypatch.setattr(runtime, "_call", failed)
    with pytest.raises(ValueError, match="failed during invocation"):
        runtime.execute()
    occurrence = next(event for event in runtime.trace if event.kind == "workflow-node")
    assert occurrence.outcome is not None
    assert occurrence.outcome.execution == "failed"
    assert occurrence.outcome.contract == "rejected"
    assert occurrence.metadata["occurrence_instance_id"]


@pytest.mark.parametrize(
    "body, permitted, accepted",
    [
        ("7", "literal, computed", True),
        ("value + 1", "literal, computed", True),
        ("value + 1", "literal", False),
    ],
)
def test_explicit_occurrence_origins_survive_generic_materialization(
    body, permitted, accepted
):
    source = f"""
type Step[A] = A -> A
reasoning Plan[A](value: A) -> A:
    [result: Step(value)] with:
        input.producers = [literal]
        output.producers = [{permitted}]
        output.ancestors = [literal, computed]
    return result
def produce(value: Int) -> Int:
    return {body}
configured = Plan(result = produce)
def main() -> Int:
    return solve Plan(1) using configured(1)
"""
    engine = _relation_engine(source)
    if not accepted:
        with pytest.raises(ValueError, match="origin mismatch"):
            engine.execute()
        return
    output = engine.execute()
    assert output.result == (7 if body == "7" else 2)
    event = next(event for event in output.trace if event.kind == "workflow-node")
    assert event.metadata["declared_contract"]["requirements"][0]["origin"][
        "producers"
    ] == ("literal", "computed")
    assert event.outcome is not None
    assert event.outcome.contract == "satisfied"


@pytest.mark.parametrize(
    "constraint, message",
    [
        ("output.missing.producers = [computed]", "unknown occurrence constraint path"),
        ("output.producers = [deductive]", "invalid occurrence origins"),
        ("output.producers = [literal, literal]", "invalid occurrence origins"),
        (
            "output.producers = [literal]\n        output.producers = [computed]",
            "duplicate occurrence constraint",
        ),
    ],
)
def test_invalid_occurrence_origin_declarations_are_rejected(constraint, message):
    source = f"""
type Step = Int -> Int
reasoning Plan(value: Int) -> Int:
    [result: Step(value)] with:
        {constraint}
    return result
"""
    with pytest.raises(ValueError, match=message):
        check(parse_source(source))


@pytest.mark.parametrize("forgery", ["unknown_case", "missing_field", "member_origin"])
def test_occurrence_variant_requirements_cannot_be_skipped(monkeypatch, forgery):
    from prism.language.core import RecordValue

    source = """
type Outcome:
    | Present(value: Computed[Int])
    | Empty
type Step = Int -> Outcome
reasoning Plan(value: Int) -> Outcome:
    [result: Step(value)]
    return result
def identity(value: Int) -> Int:
    return value
def produce(value: Int) -> Outcome:
    return Present(value = compute(value, procedure = identity))
configured = Plan(result = produce)
def main() -> Outcome:
    return solve Plan(1) using configured(1)
"""
    runtime = _relation_engine(source)
    valid = runtime.execute()
    assert valid.result.type_name == "Present"
    empty_source = source.replace(
        "return Present(value = compute(value, procedure = identity))", "return Empty()"
    )
    assert _relation_engine(empty_source).execute().result.type_name == "Empty"
    runtime = _relation_engine(source)
    invoke = runtime._call

    def tampered(callee, positional, named, env, *args, **kwargs):
        result = invoke(callee, positional, named, env, *args, **kwargs)
        if getattr(getattr(callee, "definition", None), "name", None) == "produce":
            if forgery == "unknown_case":
                result = RecordValue("NotACase", {})
            elif forgery == "missing_field":
                result = RecordValue("Present", {})
            runtime.provenance.record(result, "supplied", "forged variant")
        return result

    monkeypatch.setattr(runtime, "_call", tampered)
    with pytest.raises(ValueError, match="occurrence"):
        runtime.execute()


@pytest.mark.parametrize("forgery", ["origin", "assurance"])
@pytest.mark.parametrize("use_alias", [True, False])
def test_occurrence_rejects_actual_contract_mismatch_before_downstream(
    monkeypatch, forgery, use_alias
):
    from dataclasses import replace

    from prism.language.core import Ok

    source = """
def Positive(value: Int) -> Prop
type Assurance = Validated[subject: Int, Positive(subject)]
def positive(value: Int) -> Bool:
    return value > 0
registered = validator[value: Int, Positive(value)](positive)
type Step = Int -> Assurance
reasoning Plan(value: Int) -> Assurance:
    [result: Step(value)]
    return result
def produce(value: Int) -> Result[Assurance, ValidationError]:
    return validate[Positive(value)](value, validator = registered)
def finish(value: Assurance) -> Int:
    return value.value
configured = Plan(result = produce)
def main() -> Result[Int, ValidationError]:
    checked = try solve Plan(1) using configured(1)
    return Ok(finish(checked))
"""
    if forgery == "origin":
        source = source.replace(
            "Validated[subject: Int, Positive(subject)]", "Computed[Int]"
        )
        source = source.replace(
            "    return validate[Positive(value)](value, validator = registered)",
            "    return Ok(compute(value, procedure = identity))",
        )
        source = "def identity(value: Int) -> Int:\n    return value\n" + source
    if not use_alias:
        source = source.replace(
            "type Assurance = Validated[subject: Int, Positive(subject)]\n", ""
        ).replace("type Assurance = Computed[Int]\n", "")
        source = source.replace(
            "Assurance",
            "Validated[subject: Int, Positive(subject)]"
            if forgery == "assurance"
            else "Computed[Int]",
        )
    assert _relation_engine(source).execute().result == Ok(1)
    engine = _relation_engine(source)
    invoke = engine._call

    def tampered(callee, positional, named, env, *args, **kwargs):
        result = invoke(callee, positional, named, env, *args, **kwargs)
        if getattr(getattr(callee, "definition", None), "name", None) == "produce":
            assert isinstance(result, Ok)
            if forgery == "origin":
                engine.provenance.record(result, "supplied", "forged computation")
            else:
                result = Ok(replace(result.value, value=-1))
        return result

    monkeypatch.setattr(engine, "_call", tampered)
    with pytest.raises(ValueError, match="origin mismatch|different claim"):
        engine.execute()
    assert not any(
        event.kind == "function-call" and event.name == "finish"
        for event in engine.trace
    )
    occurrence = next(event for event in engine.trace if event.kind == "workflow-node")
    assert occurrence.outcome is not None
    assert occurrence.outcome.contract == "rejected"


def _relation_engine(source):
    from prism.language.kernel import Kernel
    from prism.runtime.engine import _Engine
    from prism.runtime.replay import EffectRecorder

    executable = compile(elaborate(check(parse_source(source))))
    assert executable.checked_module is not None
    return _Engine(
        executable,
        FakeEffectHandler(),
        Kernel(executable.checked_module.environment),
        None,
        EffectRecorder(),
        None,
        None,
    )


@pytest.mark.parametrize("forgery", ["neighbor", "policy", "missing_proof"])
def test_relation_rechecks_certificates_before_downstream_execution(
    monkeypatch, forgery
):
    from prism.language.core import Ok, RecordValue
    from prism.runtime.engine.values import ClaimValue, PolicyValue

    source = PROVEN_RELATION_SOURCE
    if forgery == "missing_proof":
        source = source.replace(
            "type Step =", "type Certificate[P]:\n    proof: Proof[P]\ntype Step ="
        )
        source = source.replace(
            "|- Same(source, target)", "-> Certificate[Same(source, target)]"
        )
        source = source.replace(
            "Result[Proof[Same(source, target)], ProofError]",
            "Result[Certificate[Same(source, target)], ProofError]",
        )
        source = source.replace(
            "    return kernel.check(term)",
            "    proof = try kernel.check(term)\n    return Ok(Certificate(proof = proof))",
        )
    original = _relation_engine(source).execute()
    certificate = next(
        item.metadata["certificate"]
        for item in original.trace
        if item.kind == "reasoning-relation"
    )
    engine = _relation_engine(source)
    invoke = engine._call

    def tampered(callee, positional, named, env, *args, **kwargs):
        name = getattr(getattr(callee, "definition", None), "name", None)
        if name == "produce" and forgery == "neighbor":
            return 2
        if name == "certify":
            if forgery == "policy":
                return Ok(
                    PolicyValue(
                        "forged", None, {}, ClaimValue("forged"), "forged", "forged"
                    )
                )
            if forgery == "missing_proof":
                return Ok(RecordValue("Certificate", {}))
            return Ok(certificate)
        return invoke(callee, positional, named, env, *args, **kwargs)

    monkeypatch.setattr(engine, "_call", tampered)
    with pytest.raises(ValueError, match="rejected its certificate"):
        engine.execute()
    relation = next(item for item in engine.trace if item.kind == "reasoning-relation")
    assert relation.status == "rejected"
    assert relation.metadata["certificate_valid"] is False
    occurrence = next(
        item
        for item in engine.trace
        if item.kind == "workflow-node" and item.name == "result"
    )
    assert occurrence.status == "rejected"
    assert occurrence.outcome is not None
    assert occurrence.outcome.execution == "completed"
    assert occurrence.outcome.contract == "rejected"
    assert occurrence.outcome.observed[0].assurance == "unchecked"
    assert occurrence.outcome.observed[0].claim_disposition == "not_applicable"
    assert "rejected its certificate" in occurrence.metadata["error"]
    assert not any(
        item.kind == "function-call" and item.name == "finish" for item in engine.trace
    )


def test_relation_implementation_hash_tracks_body_changes():
    changed = PROVEN_RELATION_SOURCE.replace(
        '    term = try elaborate_proof[Same(source, target)]("rfl")',
        '    unused: Nat = 0\n    term = try elaborate_proof[Same(source, target)]("rfl")',
    )
    events = [
        next(
            item
            for item in _relation_engine(source).execute().trace
            if item.kind == "reasoning-relation"
        )
        for source in (PROVEN_RELATION_SOURCE, changed)
    ]
    assert events[0].metadata["implementation"] == events[1].metadata["implementation"]
    assert (
        events[0].metadata["implementation_hash"]
        != events[1].metadata["implementation_hash"]
    )


@pytest.mark.parametrize("forgery", ["neighbor", "rejected"])
def test_relation_support_must_accept_the_actual_endpoints(monkeypatch, forgery):
    from dataclasses import replace

    from prism.language.core import Ok
    from prism.language.evidence import PolicyDecision

    source = PROVEN_RELATION_SOURCE.replace(
        "|- Same(source, target)", "|~ Same(source, target)"
    )
    start = source.index("def certify(")
    end = source.index("configured =", start)
    source = (
        source[:start]
        + """
def evaluate(evidence: Evidence[Nat], source: Nat, target: Nat) -> PolicyDecision:
    return accept_assessment("same endpoints") if source == target and evidence.value == source else reject_assessment("different endpoints")
def certify(source: Nat, target: Nat) -> Result[Supported[Same(source, target)], SupportError]:
    policy = material_policy[Nat, Same(source, target), Never]("same", evaluator = evaluate)
    assessment = try observe(source) |~[policy] Same(source, target)
    return accept_support(assessment)
"""
        + source[end:]
    )
    source = source.replace("Result[Nat, ProofError]", "Result[Nat, SupportError]")
    output = _relation_engine(source).execute()
    certificate = next(
        item.metadata["certificate"]
        for item in output.trace
        if item.kind == "reasoning-relation"
    )
    assert certificate.status == "accepted"
    engine = _relation_engine(source)
    invoke = engine._call

    def tampered(callee, positional, named, env, *args, **kwargs):
        name = getattr(getattr(callee, "definition", None), "name", None)
        if name == "produce" and forgery == "neighbor":
            return 2
        if name == "certify":
            return Ok(
                replace(
                    certificate.assessment,
                    decision=PolicyDecision("rejected", "rejected"),
                )
                if forgery == "rejected"
                else certificate
            )
        return invoke(callee, positional, named, env, *args, **kwargs)

    monkeypatch.setattr(engine, "_call", tampered)
    with pytest.raises(ValueError, match="rejected its certificate"):
        engine.execute()
    relation = next(item for item in engine.trace if item.kind == "reasoning-relation")
    assert relation.status == "rejected"
    assert not any(
        item.kind == "function-call" and item.name == "finish" for item in engine.trace
    )


def test_relation_rechecks_a_verified_pair():
    source = (
        PROVEN_RELATION_SOURCE.replace(
            "|- Same(source, target)", "-> Verified[Nat, Same(source, target)]"
        )
        .replace(
            "Result[Proof[Same(source, target)], ProofError]",
            "Result[Verified[Nat, Same(source, target)], ProofError]",
        )
        .replace(
            "    return kernel.check(term)",
            "    proof = try kernel.check(term)\n    return Ok(verify(target, proof))",
        )
    )
    output = _relation_engine(source).execute()
    assert output.status == "accepted"
    relation = next(item for item in output.trace if item.kind == "reasoning-relation")
    assert relation.metadata["certificate_valid"] is True
    assert relation.metadata["certificate"].value == 1
    assert relation.outcome is not None
    assert relation.outcome.execution == "completed"
    assert relation.outcome.contract == "satisfied"
    assert relation.outcome.observed[0].assurance == "proved"


def test_runtime_rejects_an_effectful_relation_builder_before_calling_it(monkeypatch):
    from dataclasses import replace

    from prism.language.effects import FunctionDefinition

    engine = _relation_engine(PROVEN_RELATION_SOURCE)
    engine.program = replace(
        engine.program,
        declarations=tuple(
            replace(item, effects=("Python.Call",))
            if isinstance(item, FunctionDefinition) and item.name == "certify"
            else item
            for item in engine.program.declarations
        ),
    )
    invoke = engine._call

    def guarded(callee, positional, named, env, *args, **kwargs):
        assert getattr(getattr(callee, "definition", None), "name", None) != "certify"
        return invoke(callee, positional, named, env, *args, **kwargs)

    monkeypatch.setattr(engine, "_call", guarded)
    with pytest.raises(ValueError, match="relation builders must be pure"):
        engine.execute()
    assert any(
        item.kind == "reasoning-relation" and item.status == "rejected"
        for item in engine.trace
    )
    relation = next(item for item in engine.trace if item.kind == "reasoning-relation")
    occurrence = next(item for item in engine.trace if item.kind == "workflow-node")
    assert (
        relation.metadata["target_occurrence_instance"]
        == occurrence.metadata["occurrence_instance_id"]
    )
    assert relation.outcome is not None
    assert relation.outcome.execution == "failed"
    assert relation.outcome.contract == "rejected"


def test_runtime_relation_cannot_replace_the_checked_declaration():
    from dataclasses import replace

    from prism.language.workflows import RelationDefinition

    runtime = _relation_engine(PROVEN_RELATION_SOURCE)
    runtime.program = replace(
        runtime.program,
        declarations=tuple(
            replace(item, identity="Other::Certifies")
            if isinstance(item, RelationDefinition)
            else item
            for item in runtime.program.declarations
        ),
    )
    with pytest.raises(ValueError, match="different declaration identity"):
        runtime.execute()
    relations = [event for event in runtime.trace if event.kind == "reasoning-relation"]
    assert len(relations) == 1
    assert relations[0].status == "rejected"
    assert not any(
        event.kind == "function-call" and event.name == "certify"
        for event in runtime.trace
    )


def test_relation_validation_is_bound_to_the_actual_certificate_value(monkeypatch):
    from dataclasses import replace

    from prism.language.core import Ok

    source = PROVEN_RELATION_SOURCE.replace(
        "|- Same(source, target)", "-> Validated[value: Nat, Same(value, target)]"
    )
    start = source.index("def certify(")
    end = source.index("configured =", start)
    source = (
        source[:start]
        + """
def valid(value: Nat) -> Bool:
    return value >= 0
def certify(source: Nat, target: Nat) -> Result[Validated[value: Nat, Same(value, target)], ValidationError]:
    registered = validator[value: Nat, Same(value, target)](valid)
    return validate[Same(target, target)](target, validator = registered)
"""
        + source[end:]
    )
    source = source.replace("Result[Nat, ProofError]", "Result[Nat, ValidationError]")
    assert _relation_engine(source).execute().status == "accepted"
    engine = _relation_engine(source)
    invoke = engine._call

    def tampered(callee, positional, named, env, *args, **kwargs):
        result = invoke(callee, positional, named, env, *args, **kwargs)
        if getattr(getattr(callee, "definition", None), "name", None) == "certify":
            return Ok(replace(result.value, value=2))
        return result

    monkeypatch.setattr(engine, "_call", tampered)
    with pytest.raises(ValueError, match="validation certifies a different claim"):
        engine.execute()


def test_checked_occurrence_contract_is_preserved_in_compiled_output():
    checked = check(parse_source(PROVEN_RELATION_SOURCE))
    typed = elaborate(checked)
    executable = compile(typed)
    declaration = next(
        item for item in checked.program.declarations if isinstance(item, ReasoningDecl)
    )
    from prism.language.developer.syntax.ast import SequenceComposition

    assert isinstance(declaration.composition, SequenceComposition)
    source_node = declaration.composition.children[0]
    contract = checked.occurrence_contracts[id(source_node)]
    compiled = next(
        item
        for item in executable.declarations
        if isinstance(item, ReasoningDefinition)
    )
    assert typed.occurrence_contracts[id(source_node)] is contract
    assert compiled.composition.children[0].contract is contract
    assert contract.owner_identity == "Main::Plan"
    assert contract.method_identity == "Main::Step"
    assert contract.classification.state == "unclassified"
    assert contract.classification.references == ()
    assert contract.input_type == CoreType("Nat")
    assert contract.output_type == CoreType("Nat")
    assert contract.requirements[0].origin.producers == ("unconstrained",)
    assert contract.requirements[0].assurance.kind == "unchecked"
    assert contract.relation is not None
    assert contract.relation.identity == "Main::Certifies"
    proof = contract.relation.requirements[0].assurance
    assert proof.kind == "proof"
    assert proof.proposition is not None
    assert proof.proposition.proposition is not None
    assert proof.proposition.proposition.children[0].symbol == "Main::Same"


def test_occurrence_requirements_keep_nested_origins_and_assurance_independent():
    source = """
approved: Nat = 7
def Positive(value: Nat) -> Prop
type Payload:
    draft: Generated[Int]
    observation: Evidence[Int]
    computed: Computed[Int]
    proof: Proof[Positive(approved)]
    validated: Validated[value: Nat, Positive(value)]
type Step = Payload -> Payload
reasoning Plan(value: Payload) -> Payload:
    [result: Step(value)]
    return result
"""
    checked = check(parse_source(source))
    contract = next(iter(checked.occurrence_contracts.values()))
    requirements = {item.path: item for item in contract.requirements}
    assert requirements[()].assurance.kind == "unchecked"
    assert requirements[("draft",)].origin.producers == ("generated",)
    assert requirements[("draft",)].assurance.kind == "unchecked"
    assert requirements[("observation",)].origin.producers == (
        "asserted",
        "acquired",
        "computed",
    )
    assert requirements[("computed",)].origin.producers == ("computed",)
    assert requirements[("computed",)].origin.ancestors == ("unconstrained",)
    assert requirements[("proof",)].assurance.kind == "proof"
    assert requirements[("proof",)].origin.producers == ("unconstrained",)
    assert requirements[("validated",)].assurance.kind == "validated"
    proposition = requirements[("validated",)].assurance.proposition
    assert proposition is not None
    assert proposition.proposition is not None


def test_imported_generic_contract_specializes_nested_value_requirements():
    modules = InMemoryModuleLoader(
        {
            "plan": """
type Original[A] = A -> A
type Alias[A] = Original[A]
reasoning Echo[A](value: A) -> A:
    [result: Alias[A](value)]
    return result
"""
        }
    )
    source = """
from plan import Echo as Renamed
type Envelope:
    data: Computed[Int]
def keep(value: Envelope) -> Envelope:
    return value
configured = Renamed[Envelope](result = keep)
def computed_fixture(value: Int) -> Int:
    return value
def main() -> Workflow[Envelope, Never]:
    value = Envelope(data = compute(3, procedure = computed_fixture))
    return configured(value)
"""
    checked = check(parse_source(source), module_loader=modules)
    executable = compile(elaborate(checked))
    workflow = run(executable, handler=FakeEffectHandler()).result
    materialized = workflow.definition.composition.contract
    assert materialized.owner_identity == "memory:plan::Echo"
    assert materialized.method_identity == "memory:plan::Original"
    assert materialized.input_type == CoreType("Envelope")
    assert materialized.output_type == CoreType("Envelope")
    requirements = {item.path: item for item in materialized.requirements}
    assert requirements[("data",)].origin.producers == ("computed",)
    template = next(
        item
        for item in checked.occurrence_contracts.values()
        if item.owner_identity == "memory:plan::Echo"
    )
    assert template.output_type == CoreType("A")
    assert materialized == template.specialize(
        {"A": CoreType("Envelope")}, executable.record_contracts, executable.variants
    )


def test_nested_and_ordinary_workflow_nodes_have_checked_contracts():
    source = """
type Step = Int -> Int
reasoning Inner(value: Int) -> Int:
    [result: Step(value)]
    return result
reasoning Outer(value: Int) -> Int:
    [result: Step(value)]
    return result
def keep[A](value: A) -> A:
    return value
def concrete(value: Int) -> Int:
    return value
inner_plan = Inner(result = concrete)
def run_inner(value: Int) -> Int:
    return solve Inner(value) using inner_plan(value)
workflow inner(value: Int) -> Int:
    sequence:
        [prepared: keep(value)]
        [result: run_inner(prepared)]
    return result
configured = Outer(result = inner)
def main() -> Int:
    return solve Outer(3) using configured(3)
"""
    checked = check(parse_source(source))
    contracts = {
        item.owner_identity: item for item in checked.occurrence_contracts.values()
    }
    assert set(contracts) == {"Main::Inner", "Main::Outer", "Main::inner"}
    assert contracts["Main::Inner"].identity != contracts["Main::Outer"].identity
    assert contracts["Main::inner"].input_type == CoreType("Int")
    assert contracts["Main::inner"].output_type == CoreType("Int")
    assert all(
        item.requirements[0].assurance.kind == "unchecked"
        for item in contracts.values()
    )
    assert run(compile(elaborate(checked)), handler=FakeEffectHandler()).result == 3


def test_occurrence_contracts_retain_variant_proof_obligations():
    source = """
approved: Nat = 7
def Positive(value: Nat) -> Prop
type Outcome:
    | HasProof(proof: Proof[Positive(approved)])
    | NoProof
type Step = Outcome -> Outcome
reasoning Plan(value: Outcome) -> Outcome:
    [result: Step(value)]
    return result
"""
    contract = next(iter(check(parse_source(source)).occurrence_contracts.values()))
    output = {item.path: item for item in contract.requirements}
    assert output[()].assurance.kind == "unchecked"
    assert output[("case:HasProof", "proof")].assurance.kind == "proof"
    assert output[("case:NoProof",)].assurance.kind == "unchecked"
    assert contract.input_requirements == contract.requirements


def test_same_signature_methods_have_distinct_occurrence_method_identities():
    source = """
type First = Int -> Int
type Second = Int -> Int
reasoning Plan(value: Int) -> Int:
    sequence:
        [first: First(value)]
        [second: Second(first)]
    return second
"""
    contracts = tuple(check(parse_source(source)).occurrence_contracts.values())
    assert {item.method_identity for item in contracts} == {
        "Main::First",
        "Main::Second",
    }
    assert contracts[0].output_type == contracts[1].output_type


@pytest.mark.parametrize("budget,expected", [(1, 1), (2, 2), (7, 2)])
def test_reasoning_repeat_uses_runtime_budget(budget, expected):
    source = """type State:
    count: Int
    done: Bool
def advance(state: State) -> State:
    count = state.count + 1
    return State(count = count, done = count >= 2)
reasoning Loop(state: State, budget: Int) -> State:
    repeat refinement_policy(budget, until = state.done):
        [state: advance(state)]
    return state
configured = Loop()
def main(budget: Int) -> State:
    initial = State(count = 0, done = False)
    return solve Loop(initial, budget) using configured(initial, budget)
"""
    checked = check(parse_source(source))
    output = run(
        compile(elaborate(checked)),
        handler=FakeEffectHandler(),
        entry_arguments={"budget": budget},
    )
    assert output.status == "accepted"
    assert output.result.fields["count"] == expected
    assert (
        len([event for event in output.trace if event.kind == "workflow-node"])
        == expected
    )


@pytest.mark.parametrize("branch,expected", [("Left", 11), ("Right", 22)])
@pytest.mark.parametrize("kind", ["workflow", "reasoning"])
def test_choice_keeps_branch_local_intermediates_and_joins_shared_result(
    branch, expected, kind
):
    source = """type Route:
    | Left
    | Right
def choose(route: Route) -> Route:
    return route
def left(value: Int) -> Int:
    return value + 10
def right(value: Int) -> Int:
    return value + 20
def identity(value: Int) -> Int:
    return value
type LeftStep = Int -> Int
type RightStep = Int -> Int
KIND Plan(route: Route) -> Int:
    choice [selected: choose(route)]:
        case Left:
            [left_value: LEFT(1)]
            [result: identity(left_value)]
        case Right:
            [right_value: RIGHT(2)]
            [result: identity(right_value)]
    return result
""".replace("KIND", kind)
    if kind == "reasoning":
        source = source.replace("LEFT", "LeftStep").replace("RIGHT", "RightStep")
        source += "configured = Plan(left_value = left, right_value = right)\n"
        source += f"def main() -> Int:\n    return solve Plan({branch}()) using configured({branch}())\n"
    else:
        source = source.replace("LEFT", "left").replace("RIGHT", "right")
        source += f"def main() -> Int:\n    return solve Plan({branch}())\n"
    output = run(
        compile(elaborate(check(parse_source(source)))), handler=FakeEffectHandler()
    )
    assert output.result == expected
    nodes = [event.name for event in output.trace if event.kind == "workflow-node"]
    assert ("left_value" if branch == "Left" else "right_value") in nodes
    assert ("right_value" if branch == "Left" else "left_value") not in nodes
    for leaked in ("left_value", "right_value"):
        with pytest.raises(PrismTypeError):
            check(
                parse_source(
                    source.replace("    return result\n", f"    return {leaked}\n")
                )
            )
