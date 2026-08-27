# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.tooling.lsp.service import PrismLanguageService

ROOT = Path(__file__).resolve().parents[1]
REFINEMENT_REASONING = ROOT / "examples/language/refinement_loop/reasoning.prism"
DEDUCTIVE_METHOD = ROOT / "libs/prism/reasoning/methods/deductive.prism"


def test_reasoning_occurrence_alias_has_a_compiler_type_span() -> None:
    result = PrismLanguageService(project_root=ROOT).check_document(
        document_path=REFINEMENT_REASONING
    )

    assert result.status == "valid"
    candidate = next(
        item
        for item in result.type_spans
        if item.kind == "ReasoningOccurrence" and item.name == "candidate"
    )
    assert candidate.type_text == (
        "Validated[value: Computed[PlanHypothesis], PlanWellFormed(value)]"
    )
    source = REFINEMENT_REASONING.read_text(encoding="utf-8")
    expected_line, expected_character = _position_of(source, "[candidate:", "candidate")
    assert (candidate.span.line, candidate.span.character) == (
        expected_line,
        expected_character,
    )


def test_generic_type_parameter_references_navigate_to_their_binder() -> None:
    service = PrismLanguageService(project_root=ROOT)
    source = DEDUCTIVE_METHOD.read_text(encoding="utf-8")
    line, character = _position_of(
        source,
        "source: DeductionInput[Premises]",
        "Premises",
    )
    target_line, target_character = _position_of(
        source,
        "type Deductive[Conclusion, Premises]",
        "Premises",
    )

    result = service.definition_at(
        document_path=DEDUCTIVE_METHOD,
        document_text=source,
        line=line,
        character=character,
    )

    assert result is not None
    assert len(result.targets) == 1
    assert Path(result.targets[0].definition_path) == DEDUCTIVE_METHOD
    assert (result.targets[0].span.line, result.targets[0].span.character) == (
        target_line,
        target_character,
    )


def test_language_service_discovers_nested_generated_project(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "mathformer-prism"
    project = workspace / "projects" / "artifact_acceptance_loop" / "prism_project"
    project.mkdir(parents=True)
    (project / "runtime.json").write_text(
        '{"handler": "fake", "workspace": "."}\n', encoding="utf-8"
    )
    (project / "artifact_acceptance_loop.prism").write_text(
        "type ArtifactAcceptanceCase:\n    name: String\n", encoding="utf-8"
    )
    reasoning = project / "reasoning.prism"
    reasoning.write_text(
        "from artifact_acceptance_loop import ArtifactAcceptanceCase\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PRISM_PROJECT_ROOT", raising=False)

    result = PrismLanguageService(project_root=workspace).check_document(
        document_path=reasoning
    )

    assert result.status == "valid"
    assert not result.diagnostics


def test_language_service_resolves_stdlib_for_hidden_project(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "mathformer"
    materialization = workspace / ".prism" / "hille_yosida" / "materialization.prism"
    materialization.parent.mkdir(parents=True)
    materialization.write_text(
        "from prism.reasoning.methods.abductive import AbductionInput\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PRISM_PROJECT_ROOT", raising=False)

    result = PrismLanguageService(project_root=workspace).check_document(
        document_path=materialization
    )

    assert result.status == "valid"
    assert not result.diagnostics


def _position_of(source: str, occurrence: str, name: str) -> tuple[int, int]:
    offset = source.index(occurrence) + occurrence.index(name)
    before = source[:offset]
    return before.count("\n"), offset - (before.rfind("\n") + 1)
