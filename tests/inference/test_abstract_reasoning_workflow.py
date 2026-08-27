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
