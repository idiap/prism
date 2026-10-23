# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from dataclasses import replace
from pathlib import Path

import pytest
from prism.language import check, elaborate, parse_source
from prism.language.core import Binding, CallableContract, CoreType, TypedModule
from prism.language.developer import SourceSpan
from prism.language.developer.syntax import Program
from prism.tooling.lsp.symbols import build_symbol_index, build_type_index
from prism.tooling.lsp.symbols.spans import NameLocator


def test_declaration_symbols_preserve_order_and_metadata() -> None:
    program = parse_source("""type Task:
    request: String
type PrepareWorkflow = Task -> Workflow[Task, Never]
def prepare(task: Task) -> Task:
    return task
workflow preflight(task: Task) -> Task:
    sequence:
        [prepared: prepare(task)]
    return prepared
tool preflight_tool: Tool[PrepareWorkflow] = preflight
""")
    checked = check(program)
    symbols = build_symbol_index(
        program, checked.globals, callable_contracts={}, project_root=Path.cwd()
    )

    assert [(item.name, item.kind) for item in symbols] == [
        ("Task", "Type"),
        ("PrepareWorkflow", "Type"),
        ("prepare", "Function"),
        ("preflight", "Workflow"),
        ("prepared", "WorkflowNode"),
        ("preflight_tool", "Tool"),
    ]
    assert symbols[0].metadata == {"fields": {"request": "String"}, "variants": ()}
    assert symbols[1].detail == "Task -> Workflow[Task, Never]"
    assert symbols[2].detail == "(task: Task) -> Task"
    assert symbols[3].metadata == {
        "effects": (),
        "failure": "Never",
        "assurance": "Task",
    }
    assert symbols[4].metadata == {"component": "", "node_id": "prepared"}
    assert symbols[5].detail == "Tool[PrepareWorkflow]"


def test_type_index_locates_declarations_fields_parameters_and_bindings() -> None:
    program = parse_source("""type Label = String
type Task:
    label: Label
def read(task: Task) -> Label:
    value = task.label
    return value
agent writer(label: Label) -> String ! {AI.Generate}:
""")
    spans = build_type_index(program, elaborate(check(program)))
    selected = {
        (item.kind, item.name): (item.span.line, item.span.character, item.type_text)
        for item in spans
        if item.kind in {"Field", "Parameter", "Binding", "FunctionDecl", "Agent"}
    }
    assert selected == {
        ("Field", "label"): (2, 4, "String"),
        ("FunctionDecl", "read"): (3, 4, "(task: Task) -> String"),
        ("Parameter", "task"): (3, 9, "Task"),
        ("Binding", "value"): (4, 4, "String"),
        ("Agent", "writer"): (6, 6, "(label: String) -> String ! {AI.Generate}"),
        ("Parameter", "label"): (6, 13, "String"),
    }
    positions = [(item.span.line, item.span.character) for item in spans]
    assert positions == sorted(positions)
    duplicated = replace(program, declarations=program.declarations * 2)
    assert build_type_index(duplicated, elaborate(check(program))) == spans


def test_import_type_spans_select_local_aliases() -> None:
    program = parse_source(
        "from library import thing as local, other\nimport library as module\n"
    )
    checked = TypedModule(
        path=None,
        source=program.source,
        declarations=program.declarations,
        globals={
            name: Binding(name, CoreType("String"))
            for name in ("local", "other", "module")
        },
        callable_contracts={},
        record_contracts={},
    )
    spans = build_type_index(program, checked)
    assert [
        (item.name, item.kind, item.span.line, item.span.character) for item in spans
    ] == [
        ("local", "Import", 0, 29),
        ("other", "Import", 0, 36),
        ("module", "ModuleImport", 1, 18),
    ]
    assert build_type_index(program, replace(checked, globals={})) == []


def test_expression_types_fall_back_to_callable_and_record_contracts() -> None:
    program = parse_source("""type Task:
    label: String
def make(label: String) -> Task:
    return Task(label = label)
factory = make
""")
    checked = replace(elaborate(check(program)), expression_types={})
    spans = build_type_index(program, checked)
    references = {
        item.name: item.type_text for item in spans if item.kind == "NameExpr"
    }
    assert references == {
        "Task": "(label: String) -> Task",
        "make": "(label: String) -> Task",
    }


def test_intrinsic_symbols_point_to_their_definition_names() -> None:
    contracts = {
        name: CallableContract(name, (), CoreType("Int"), kind=kind)
        for name, kind in (
            ("length", "intrinsic"),
            ("missing_intrinsic", "intrinsic"),
            ("compute", "def"),
        )
    }
    symbols = build_symbol_index(
        Program((), ""), {}, callable_contracts=contracts, project_root=Path.cwd()
    )
    assert len(symbols) == 1
    intrinsic = symbols[0]
    assert (intrinsic.name, intrinsic.kind, intrinsic.source_ref) == (
        "length",
        "Intrinsic",
        "compiler-intrinsic",
    )
    assert intrinsic.definition_path is not None
    line = Path(intrinsic.definition_path).read_text().splitlines()[intrinsic.span.line]
    assert line[intrinsic.span.character : intrinsic.span.end_character] == "length"


@pytest.mark.parametrize("trailing", ["(", "\n    nested\n  incomplete"])
def test_name_lookup_retains_tokens_before_incomplete_syntax(trailing: str) -> None:
    locator = NameLocator('"name" # name\nname name' + trailing)
    within = SourceSpan(2, 1, 2, 10)
    first = SourceSpan(2, 1, 2, 5)
    last = SourceSpan(2, 6, 2, 10)

    assert locator.find("name", within) == first
    assert locator.find("name", within, reverse=True) == last
    assert locator.find("name", within, used={(2, 1)}) == last
    assert locator.find("name", SourceSpan(2, 5, 2, 6)) is None
    assert locator.find("name", within, used={(2, 1), (2, 6)}) is None
