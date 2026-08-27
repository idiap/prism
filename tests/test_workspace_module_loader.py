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
