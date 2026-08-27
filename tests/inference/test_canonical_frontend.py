# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from prism.language import check, compile, elaborate, parse_source
from prism.language.core import ASSURANCE_TYPES, PROVENANCE_TYPES, RecordValue
from prism.language.developer import PrismSyntaxError, PrismTypeError
from prism.language.developer.syntax import (
    CallExpr,
    ChoiceComposition,
    FunctionDecl,
    NameExpr,
    ParallelComposition,
    RepeatComposition,
    SequenceComposition,
    WorkflowDecl,
)
from prism.runtime import FakeEffectHandler, run


def _check(source: str):
    return check(parse_source(source))


def test_provenance_and_assurance_types_are_disjoint() -> None:
    assert PROVENANCE_TYPES == {"Generated", "Evidence", "Computed"}
    assert ASSURANCE_TYPES == {"Supported", "Validated", "Proof", "Verified"}
    assert PROVENANCE_TYPES.isdisjoint(ASSURANCE_TYPES)


def test_bodyless_functions_declare_only_abstract_propositions() -> None:
    checked = _check("""type Draft:
    text: String
type Critique:
    text: String
def Addresses(draft: Draft, critique: Critique) -> Prop
""")

    declaration = checked.program.declarations[2]
    assert isinstance(declaration, FunctionDecl)
    assert declaration.is_proposition_declaration
    assert declaration.body == ()

    with pytest.raises(
        PrismSyntaxError,
        match="only a pure function returning `Prop` may omit its body",
    ):
        parse_source("def unfinished(value: String) -> String\n")


def test_abstract_proposition_applications_are_value_indexed_at_runtime() -> None:
    executable = compile(
        elaborate(
            _check("""def Indexed(value: String) -> Prop
def main() -> Bool:
    return Indexed("first") != Indexed("second")
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result is True


def test_conditional_expression_evaluates_only_the_selected_branch() -> None:
    executable = compile(
        elaborate(
            _check("""def choose(enabled: Bool) -> Int:
    return 7 if enabled else 3 / 0
def main() -> Int:
    return choose(True)
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result == 7


def test_lists_support_typed_length_and_indexing() -> None:
    executable = compile(
        elaborate(
            _check("""def choose(values: List[Int]) -> Int:
    last = length(values) - 1
    return values[last]
def main() -> Int:
    return choose([2, 3, 5, 8])
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result == 8


def test_list_index_must_be_an_integer() -> None:
    with pytest.raises(PrismTypeError, match="list index"):
        _check("""def invalid(values: List[Int]) -> Int:
    return values[True]
""")


def test_computed_values_have_no_public_constructor() -> None:
    with pytest.raises(
        PrismTypeError,
        match="Computed values can only be produced by `compute`",
    ):
        _check("""def main() -> Computed[String]:
    return Computed("unsafe")
""")


def test_goal_keyword_is_not_part_of_prism_syntax() -> None:
    with pytest.raises(
        PrismSyntaxError, match="expected a declaration or immutable binding"
    ):
        parse_source("goal removed() -> String\n")


def test_workflow_main_cannot_replace_the_function_entry() -> None:
    with pytest.raises(PrismTypeError, match="application entry is `def main`"):
        _check("""def identity(value: String) -> String:
    return value
workflow main(value: String) -> String:
    [result: identity]
""")


def test_workflow_visual_topology_parses_recursively() -> None:
    program = parse_source(
        """workflow audit(value: String, policy: RefinementPolicy) -> String fails Error:
    sequence:
        parallel:
            [left: inspect.left]
            [right: inspect.right]
        choice [route: choose]:
            case Static:
                [result: static_review]
            case Dynamic:
                sequence:
                    [observations: observe_dynamic]
                    [result: dynamic_review]
        repeat policy:
            [accepted: validate]
    return accepted
"""
    )
    workflow = program.declarations[0]
    assert isinstance(workflow, WorkflowDecl)
    assert workflow.failure.text == "Error"
    assert isinstance(workflow.composition, SequenceComposition)
    assert isinstance(workflow.composition.children[0], ParallelComposition)
    assert isinstance(workflow.composition.children[1], ChoiceComposition)
    assert isinstance(workflow.composition.children[2], RepeatComposition)
    assert isinstance(workflow.composition.children[2].policy, NameExpr)
    assert workflow.result_alias == "accepted"


def test_repeat_accepts_an_inline_statically_bounded_policy() -> None:
    checked = _check("""def identity(value: String) -> String:
    return value
workflow replay(value: String) -> String:
    repeat refinement_policy(2):
        [result: identity]
    return result
""")

    workflow = checked.program.declarations[1]
    assert isinstance(workflow, WorkflowDecl)
    assert isinstance(workflow.composition, RepeatComposition)
    assert isinstance(workflow.composition.policy, CallExpr)


def test_repeat_carries_a_compatible_binding_between_iterations() -> None:
    executable = compile(
        elaborate(
            _check("""type State:
    value: String
def initial() -> State:
    return State(value = "initial")
def revise(state: State) -> State:
    return State(value = "revised")
workflow refinement() -> State:
    sequence:
        [state: initial()]
        repeat refinement_policy(2):
            [state: revise(state)]
    return state
def main() -> State:
    return solve refinement()
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result == RecordValue("State", {"value": "revised"})


def test_repeat_stops_when_the_terminal_boolean_field_is_true() -> None:
    executable = compile(
        elaborate(
            _check("""type State:
    attempt: Int
    Finished: Bool
def initial() -> State:
    return State(attempt = 0, Finished = False)
def revise(state: State) -> State:
    return State(attempt = state.attempt + 1, Finished = state.attempt + 1 == 2)
workflow refinement() -> State:
    sequence:
        [state: initial()]
        repeat refinement_policy(5, until = state.Finished):
            [state: revise(state)]
    return state
def main() -> State:
    return solve refinement()
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result == RecordValue("State", {"attempt": 2, "Finished": True})


def test_repeat_terminal_expression_must_reference_a_known_value() -> None:
    with pytest.raises(PrismTypeError, match="unknown name `missing`"):
        _check("""type State:
    Finished: Bool
def revise() -> State:
    return State(Finished = True)
workflow refinement() -> State:
    repeat refinement_policy(2, until = missing.Finished):
        [state: revise()]
    return state
""")


def test_repeat_terminal_expression_must_be_boolean() -> None:
    with pytest.raises(
        PrismTypeError,
        match="repeat terminal condition expects Bool, got Int",
    ):
        _check("""type State:
    attempt: Int
def revise() -> State:
    return State(attempt = 1)
workflow refinement() -> State:
    repeat refinement_policy(2, until = state.attempt):
        [state: revise()]
    return state
""")


def test_repeat_rejects_a_string_terminal_selector() -> None:
    with pytest.raises(
        PrismTypeError,
        match="repeat terminal condition expects Bool, got String",
    ):
        _check("""type State:
    Finished: Bool
def revise() -> State:
    return State(Finished = True)
workflow refinement() -> State:
    repeat refinement_policy(2, until = "state.Finished"):
        [state: revise()]
    return state
""")


def test_reasoning_switch_receives_explicit_operational_inputs() -> None:
    executable = compile(
        elaborate(
            _check("""type Status:
    value: String
    switched: Bool
type ParentMethod = String -> Status
type ChildMethod = Status -> Status
reasoning Child(handoff: Status) -> Status:
    [status: ChildMethod(handoff)]
    return status
reasoning Parent(value: String) -> Status:
    [status: ParentMethod(value)]
    on status.switched => switch @Child
    return status
def begin(value: String) -> Status:
    return Status(value = value, switched = True)
def finish(handoff: Status, suffix: String) -> Status:
    return Status(value = suffix, switched = False)
child = Child(status = finish)
parent = Parent(status = begin, Child = child)
def execute(value: String, suffix: String) -> Status:
    return solve Parent(value) using parent(value, suffix = suffix)
def main() -> Status:
    return execute("initial", "switched")
""")
        )
    )

    output = run(executable, handler=FakeEffectHandler())
    assert output.result == RecordValue(
        "Status", {"value": "switched", "switched": False}
    )


def test_repeat_inline_policy_rejects_a_nonpositive_bound() -> None:
    with pytest.raises(
        PrismTypeError,
        match="refinement_policy requires a positive static iteration bound",
    ):
        _check("""def identity(value: String) -> String:
    return value
workflow replay(value: String) -> String:
    repeat refinement_policy(0):
        [result: identity]
    return result
""")


def test_choice_requires_an_exhaustive_closed_sum_router() -> None:
    source = """type Route:
    | Static
    | Dynamic
def choose_route(route: Route) -> Route:
    return route
def static_review(route: Route) -> String:
    return "static"
def dynamic_review(route: Route) -> String:
    return "dynamic"
workflow route_review(route: Route) -> String:
    choice [selected: choose_route]:
        case Static:
            [result: static_review]
        case Dynamic:
            [result: dynamic_review]
    return result
"""
    _check(source)

    with pytest.raises(PrismTypeError, match="not exhaustive; missing cases: Dynamic"):
        _check(
            source.replace(
                "        case Dynamic:\n            [result: dynamic_review]\n", ""
            )
        )


@pytest.mark.parametrize(
    "legacy",
    [
        'workflow old() -> String:\n    step prepare:\n        return "x"\n',
        "workflow old() -> String:\n    sequence:\n        [work]\n    after work\n",
        "workflow old() -> String:\n    value = work()\n",
        "workflow old.stage() -> String:\n    [work]\n",
    ],
)
def test_statement_bodied_workflows_are_removed(legacy: str) -> None:
    with pytest.raises(PrismSyntaxError):
        parse_source(legacy)


def test_reasoning_method_declarations_are_removed() -> None:
    with pytest.raises(PrismSyntaxError, match="descriptive `type` declaration"):
        parse_source("reasoning_method Deductive[A](state: A)\n")


def test_validated_requires_an_exact_value_and_specification() -> None:
    with pytest.raises(PrismTypeError, match="requires an exact value binder"):
        _check("""def unchecked(value: String) -> Validated[String]:
    return value
""")


def test_validated_values_have_no_public_constructor() -> None:
    with pytest.raises(PrismTypeError, match="only be produced by `validate`"):
        _check("""def Accepted(value: String) -> Prop
def unchecked(value: String) -> Validated[value: String, Accepted(value)]:
    return Validated(value)
""")


def test_verified_value_projection_preserves_the_value_type() -> None:
    checked = _check("""def Accepted(value: String) -> Prop
def unwrap(
    verified: Verified[value: String, Accepted(value)],
) -> String:
    return verified.value
""")

    assert checked.callable_contracts["unwrap"].result.render() == "String"


def test_resolution_requires_a_workflow_value() -> None:
    with pytest.raises(PrismTypeError, match="requires a bound Workflow value"):
        _check('def main() -> String:\n    return solve "not a workflow"\n')


def test_workflow_call_constructs_a_pure_first_class_value() -> None:
    checked = _check("""def build(value: String) -> String:
    return value

workflow pipeline(value: String) -> String:
    [result: build]
    return result

flow: Workflow[String, Never] = pipeline("ready")
""")
    assert checked.expression_types


def test_solve_checks_reasoning_materialization_output() -> None:
    source = """type Produce = String -> String
reasoning Review(repository: String) -> String:
    [result: Produce(repository)]
    return result
def produce(repository: String) -> String:
    return repository
def wrong(repository: String) -> Bool:
    return True
configured = Review(result = produce)
workflow incompatible(repository: String) -> Bool:
    [result: wrong]
def main() -> String:
    return solve Review("repo") using incompatible("repo")
"""
    with pytest.raises(
        PrismTypeError,
        match="reasoning materialization output expects String, got Bool",
    ):
        _check(source)


def test_solve_using_requires_reasoning_on_the_left() -> None:
    source = """def identity(value: String) -> String:
    return value
workflow flow(value: String) -> String:
    [result: identity]
def main() -> String:
    return solve identity("value") using flow("value")
"""
    with pytest.raises(PrismTypeError, match="is not a reasoning declaration"):
        _check(source)


def test_workflow_ports_match_exact_names() -> None:
    source = """def inspect(repository: String, access: FileRead) -> String ! {File.Read}:
    return repository

workflow audit(repository: String) -> String ! {File.Read}:
    [inspect]
"""
    with pytest.raises(PrismTypeError, match="unavailable input `access`"):
        _check(source)


def test_workflow_failure_and_effect_surfaces_cover_nodes() -> None:
    source = """def generate_report(model: Model, model_access: ModelGenerate) -> Result[String, ModelFailure] ! {AI.Generate}:
    return generate[String]("report", model, model_access)

workflow report(model: Model, model_access: ModelGenerate) -> String:
    [generated: generate_report]
"""
    with pytest.raises(PrismTypeError, match="must include failure `ModelFailure`"):
        _check(source)


def test_compile_uses_only_def_main_as_entry() -> None:
    executable = compile(
        elaborate(
            _check("""def produce(value: String) -> String:
    return value

workflow internal(value: String) -> String:
    [result: produce]

def main() -> String:
    return solve internal("done")
""")
        )
    )
    assert executable.entry_callable == "main"
    assert executable.ir_version == "10"


def test_sequence_executes_nodes() -> None:
    executable = compile(
        elaborate(
            _check("""type Message:
    text: String

def draft(text: String) -> Message:
    return Message(text = text)

def finish(draft: Message) -> Message:
    return draft

workflow publishing(text: String) -> Message:
    sequence:
        [draft]
        [published: finish]
    return published

def main() -> Message:
    return solve publishing("hello")
""")
        )
    )
    output = run(executable, handler=FakeEffectHandler())
    assert output.result == RecordValue("Message", {"text": "hello"})
    assert [event.name for event in output.trace if event.kind == "workflow-node"] == [
        "draft",
        "published",
    ]
