# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generated_catalog_indexes_have_no_machine_specific_paths() -> None:
    for path in (ROOT / "catalog" / "indexes").glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        assert "/Users/" not in text, path
        assert "/home/" not in text, path


DOCUMENTED_SOURCES = (
    ".codex/skills/prism-epistemic-reasoning/SKILL.md",
    ".codex/skills/prism-materialization/SKILL.md",
    ".codex/skills/prism-program-writing-entry-point/SKILL.md",
    "README.md",
    "examples/language/README.md",
    "notes/CORE_PRINCIPLES.md",
    "notes/SYNTAX.md",
    "notes/EPISTEMIC.md",
    "notes/EPISTEMIC_TRUST_LINK.md",
    "docs/docs/concepts/assurance-types.md",
    "docs/docs/concepts/provenance-types.md",
    "docs/docs/concepts/reasoning-types.md",
    "docs/docs/concepts/relations-materialization.md",
    "docs/docs/concepts/execution-tracing.md",
    "docs/docs/concepts/effects-failures-permissions.md",
    "docs/docs/quick-start.md",
    "docs/docs/tutorials/refinement-loop.md",
)


def test_documented_complete_programs_compile_and_run():
    import re

    from prism.language import check, compile, elaborate, parse_source
    from prism.runtime import FakeEffectHandler, run
    from prism.sdk.workspace import WorkspaceModuleLoader

    complete = 0
    executed = 0
    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    for relative in DOCUMENTED_SOURCES:
        path = ROOT / relative
        for match in re.finditer(
            r"```prism([^\n]*)\n(.*?)\n```", path.read_text(), re.S
        ):
            metadata, source = match.groups()
            reference = re.search(r'source="([^"]+)"', metadata)
            if "executable" not in metadata and reference is None:
                assert 'title="Explanatory fragment"' in metadata, (relative, source)
                continue
            complete += 1
            origin = ROOT / reference[1] if reference else path
            if reference:
                canonical = re.sub(r"\A(?:#.*\n|\n)+", "", origin.read_text())
                assert source.strip() == canonical.strip(), origin
            program = compile(
                elaborate(
                    check(parse_source(source, path=str(origin)), module_loader=loader)
                )
            )
            if program.entry_callable == "main":
                output = run(program, handler=FakeEffectHandler())
                assert output.status == "accepted", relative
                executed += 1
    assert complete >= 15
    assert executed >= 5


def test_readme_release_review_skill_matches_its_source(tmp_path: Path) -> None:
    import re

    from prism.sdk.workspace import WorkspaceModuleLoader
    from prism.transpiler import build_skill_module

    example = ROOT / "examples/language/release_review"
    built = build_skill_module(
        example / "skills/release-review",
        "examples.language.release_review.reasoning.ReviewTask",
        tmp_path / "release_review_skill.prism",
        modules=WorkspaceModuleLoader(project_root=ROOT, entry_points=False),
    )
    committed = (example / "release_review_skill.prism").read_text()
    canonical = re.sub(r"\A(?:#.*\n|\n)+", "", committed)
    assert built.path.read_text().strip() == canonical.strip()


def test_documented_examples_return_the_stated_guarantees():
    from prism.language import check, compile, elaborate, parse_source
    from prism.language.core import ComputedValue, Ok, ValidatedValue
    from prism.runtime import FakeEffectHandler, run
    from prism.sdk.workspace import WorkspaceModuleLoader

    loader = WorkspaceModuleLoader(project_root=ROOT, entry_points=False)
    for example in ("strict_inference", "refinement_loop"):
        path = ROOT / "examples/language" / example / "main.prism"
        program = compile(
            elaborate(
                check(
                    parse_source(path.read_text(), path=str(path)), module_loader=loader
                )
            )
        )
        output = run(program, handler=FakeEffectHandler())
        assert output.status == "accepted"
        if example == "strict_inference":
            assert output.result == Ok(7)
            relation = next(
                event for event in output.trace if event.kind == "reasoning-relation"
            )
            assert relation.outcome is not None
            assert relation.outcome.observed[0].assurance == "proved"
        else:
            assert isinstance(output.result.value, ValidatedValue)
            assert isinstance(output.result.value.value, ComputedValue)
            assert not any(
                event.kind == "kernel-check-accepted" for event in output.trace
            )
            assert (
                len(
                    [
                        event
                        for event in output.trace
                        if event.kind == "workflow-node" and event.name == "finding"
                    ]
                )
                == 5
            )
            assert output.provenance is not None
            assert any(
                activity.kind == "generated" and activity.synthetic
                for activity in output.provenance.activities
            )
