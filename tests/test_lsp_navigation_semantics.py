# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from dataclasses import replace
from pathlib import Path

from prism.language import parse_source
from prism.sdk.workspace import WorkspaceModuleLoader
from prism.tooling.lsp.navigation import definition_at
from prism.tooling.lsp.semantic import build_semantic_index


def test_definition_navigation_resolves_each_import_alias(tmp_path: Path) -> None:
    library = tmp_path / "library.prism"
    library.write_text("type First = String\ntype Second = Int\n", encoding="utf-8")
    source = "from library import First as first, Second as second\n"
    program = parse_source(source)
    modules = WorkspaceModuleLoader(project_root=tmp_path, entry_points=False)

    for alias, target_line in (("first", 0), ("second", 1)):
        result = definition_at(
            program,
            document_path=tmp_path / "main.prism",
            modules=modules,
            line=0,
            character=source.index(alias),
        )
        assert result is not None
        assert len(result.targets) == 1
        target = result.targets[0]
        assert Path(target.definition_path) == library
        assert (target.span.line, target.span.character) == (target_line, 5)


def test_definition_navigation_prefers_binding_in_enclosing_function(
    tmp_path: Path,
) -> None:
    program = parse_source(
        "value = 1\ndef read() -> Int:\n    value = 2\n    return value\n"
    )
    result = definition_at(
        program,
        document_path=tmp_path / "main.prism",
        modules=WorkspaceModuleLoader(project_root=tmp_path, entry_points=False),
        line=3,
        character=11,
    )
    assert result is not None
    assert len(result.targets) == 1
    assert (result.targets[0].span.line, result.targets[0].span.character) == (2, 4)


def test_semantic_tokens_traverse_bodies_and_deduplicate_declarations() -> None:
    program = parse_source(
        "type Task:\n    label: String\ndef read(task: Task) -> String:\n"
        "    value = task.label\n    return value\n"
    )
    tokens = build_semantic_index(program)
    assert [
        (token.span.line, token.span.character, token.token_type) for token in tokens
    ] == [
        (0, 0, "keyword"),
        (0, 5, "type"),
        (1, 4, "property"),
        (2, 0, "keyword"),
        (2, 4, "function"),
        (2, 9, "parameter"),
        (3, 4, "variable"),
    ]
    duplicated = replace(program, declarations=program.declarations * 2)
    assert build_semantic_index(duplicated) == tokens


def test_semantic_tokens_cover_method_metadata_and_origin_constraints():
    source = """type Step = Int -> Int with:
    taxonomy = "prism-workflow-component-taxonomy@0.6.0"
    primary_family = core_reasoning
    reasoning_archetypes = [deductive]
reasoning Plan(value: Int) -> Int:
    [result: Step(value)] with:
        output.producers = [computed]
    return result
"""
    lines = source.splitlines()
    tokens = build_semantic_index(parse_source(source))
    names = {
        (
            token.span.line,
            lines[token.span.line][token.span.character : token.span.end_character],
            token.token_type,
        )
        for token in tokens
    }
    assert (0, "with", "keyword") in names
    assert (1, "taxonomy", "property") in names
    assert (2, "primary_family", "property") in names
    assert (3, "reasoning_archetypes", "property") in names
    assert (5, "with", "keyword") in names
    assert (6, "producers", "property") in names
