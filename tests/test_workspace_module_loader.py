# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from pathlib import Path

from prism.sdk.workspace import WorkspaceModuleLoader, resolve_project_root


def test_load_module_from_hidden_prism_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / ".prism"
    source_root.mkdir()
    module = source_root / "materialization_support.prism"
    module.write_text("type Support = String\n", encoding="utf-8")

    loaded = WorkspaceModuleLoader(
        project_root=tmp_path, entry_points=False
    ).load_module("materialization_support")

    assert loaded.source == "type Support = String\n"
    assert loaded.origin == str(module)


def test_load_installed_standard_library_module_outside_checkout(
    tmp_path: Path,
) -> None:
    loaded = WorkspaceModuleLoader(project_root=tmp_path).load_module(
        "prism.reasoning.methods.abductive"
    )

    assert "type Abductive" in loaded.source
    assert loaded.origin is not None
    assert Path(loaded.origin).name == "abductive.prism"


def test_resolve_project_root_from_nearest_runtime_workspace(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "review" / "prism_project"
    source = project / "nested" / "reasoning.prism"
    source.parent.mkdir(parents=True)
    source.write_text("type Review = String\n", encoding="utf-8")
    (project / "runtime.json").write_text(
        '{"handler": "fake", "workspace": "."}\n', encoding="utf-8"
    )

    assert resolve_project_root(source, fallback=tmp_path) == project


def test_resolve_project_root_from_hidden_prism_directory(tmp_path: Path) -> None:
    project = tmp_path / "mathformer"
    source = project / ".prism" / "hille_yosida" / "materialization.prism"
    source.parent.mkdir(parents=True)
    source.write_text("type Phase = String\n", encoding="utf-8")

    assert resolve_project_root(source, fallback=tmp_path) == project


def test_configured_project_root_overrides_document_discovery(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    configured = tmp_path / "configured"
    configured.mkdir()
    source = project / "reasoning.prism"
    (project / "runtime.json").write_text('{"workspace": "."}\n', encoding="utf-8")
    monkeypatch.setenv("PRISM_PROJECT_ROOT", str(configured))

    assert resolve_project_root(source, fallback=tmp_path) == configured


def test_method_metadata_survives_import_aliases_and_compilation(
    tmp_path: Path,
) -> None:
    from prism.language import check, compile, elaborate, parse_source
    from prism.language.core import InMemoryModuleLoader, TaxonomySource
    from prism.language.workflows.ir import (
        NodeOccurrence,
        ReasoningDefinition,
        Sequence,
    )

    root = Path(__file__).resolve().parents[1]
    taxonomy = TaxonomySource(
        "prism-workflow-component-taxonomy",
        "0.6.0",
        (root / "taxonomy/taxonomy.json").read_text(),
    )
    source = """type First[A] = A -> A with:
    taxonomy = "prism-workflow-component-taxonomy@0.6.0"
    primary_family = core_reasoning
    reasoning_archetypes = [deductive]
type Alias[A] = First[A]
type Second[A] = A -> A with:
    taxonomy = "prism-workflow-component-taxonomy@0.6.0"
    primary_family = information_and_evidence_operation
    reasoning_archetypes = not_applicable
    operational_roles = [transformation]
"""
    checked = check(
        parse_source("""from methods import Alias as Renamed, Second
reasoning Plan(value: Int) -> Int:
    sequence:
        [first: Renamed(value)]
        [second: Second(first)]
    return second
"""),
        module_loader=InMemoryModuleLoader({"methods": source}, taxonomies=(taxonomy,)),
    )
    contracts = tuple(checked.occurrence_contracts.values())
    assert {c.method_identity for c in contracts} == {
        "memory:methods::First",
        "memory:methods::Second",
    }
    first, second = contracts
    assert first.classification.archetype_state == "applicable"
    assert second.classification.archetype_state == "not_applicable"
    assert any(
        r.taxon == "transformation" and r.status == "provisional"
        for r in second.classification.references
    )
    assert (
        first.requirements[0].assurance.kind
        == second.requirements[0].assurance.kind
        == "unchecked"
    )
    typed = elaborate(checked)
    assert typed.method_classifications == checked.method_classifications
    executable = compile(typed)
    plan = next(
        item
        for item in executable.declarations
        if isinstance(item, ReasoningDefinition) and item.name == "Plan"
    )
    assert isinstance(plan.composition, Sequence)
    nodes = plan.composition.children
    assert all(isinstance(node, NodeOccurrence) for node in nodes)
    assert tuple(node.contract for node in nodes) == contracts


def test_packaged_taxonomy_is_pinned_and_available_outside_checkout(
    tmp_path: Path,
) -> None:
    from prism.language import check, parse_source

    root = Path(__file__).resolve().parents[1]
    assert (root / "libs/prism/reasoning/taxonomy.json").read_bytes() == (
        root / "taxonomy/taxonomy.json"
    ).read_bytes()
    loader = WorkspaceModuleLoader(project_root=tmp_path)
    taxonomy = loader.load_taxonomy("prism-workflow-component-taxonomy", "0.6.0")
    assert taxonomy.identity == "prism-workflow-component-taxonomy"
    source = loader.load_module("prism.reasoning.methods.evidential")
    checked = check(parse_source(source.source, source.origin), module_loader=loader)
    classification = next(iter(checked.method_classifications.values()))
    assert any(r.taxon == "evidential_assessment" for r in classification.references)


def test_invalid_method_metadata_receives_diagnostics(tmp_path: Path) -> None:
    import pytest
    from prism.language import check, parse_source
    from prism.language.developer.diagnostics import PrismSyntaxError, PrismTypeError

    root = Path(__file__).resolve().parents[1]
    loader = WorkspaceModuleLoader(project_root=root, entry_points=False)
    source = """type Step = Int -> Int with:
    taxonomy = "prism-workflow-component-taxonomy@0.6.0"
    primary_family = core_reasoning
    reasoning_archetypes = [deductive]
"""
    cases = [
        (
            source.replace("[deductive]", "[unknown_taxon]"),
            "unknown taxonomy reference",
        ),
        (source.replace("[deductive]", "[evidential]"), "deprecated"),
        (
            source.replace("core_reasoning", "unknown_family"),
            "unknown taxonomy reference",
        ),
        (
            source.replace("core_reasoning", "information_and_evidence_operation"),
            "reasoning archetypes require",
        ),
        (source.replace("[deductive]", "not_applicable"), "core_reasoning requires"),
        (
            source.replace(
                "core_reasoning", "[core_reasoning, evaluation_and_judgment]"
            ),
            "cardinality",
        ),
        (
            source.replace("[deductive]", "[deductive, deductive]"),
            "duplicate taxonomy reference",
        ),
        (source.replace("0.6.0", "99.0.0"), "unknown taxonomy"),
        (
            source.replace("    primary_family = core_reasoning\n", ""),
            "exactly one primary_family",
        ),
        (
            source.replace("    reasoning_archetypes = [deductive]\n", ""),
            "explicit not_applicable",
        ),
        (source.replace("primary_family", "unknown_facet"), "unknown taxonomy facet"),
        (source + "    primary_family = core_reasoning\n", "duplicate metadata field"),
        (
            source.replace(
                '"prism-workflow-component-taxonomy@0.6.0"',
                '"prism-workflow-component-taxonomy"',
            ),
            "pinned",
        ),
    ]
    for invalid, message in cases:
        with pytest.raises((PrismSyntaxError, PrismTypeError), match=message):
            check(parse_source(invalid), module_loader=loader)
