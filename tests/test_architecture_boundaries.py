# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Executable dependency rules for the Prism distribution graph."""

from __future__ import annotations

import tomllib
from graphlib import TopologicalSorter
from pathlib import Path

import grimp
import pytest

from tests.architecture import (
    declared_dependencies,
    distribution_dependencies,
    function_scoped_import_lines,
    language_facade_imports,
    private_language_imports,
    undeclared_dependencies,
)

REPO = Path(__file__).resolve().parents[1]

CORE_SOURCE_ROOTS = {
    "language": REPO / "packages" / "prism-language" / "src",
    "transpiler": REPO / "packages" / "prism-transpiler" / "src",
    "runtime": REPO / "packages" / "prism-runtime" / "src",
    "sdk": REPO / "packages" / "prism-sdk" / "src",
    "adapter-codex": REPO / "packages" / "prism-adapter-codex" / "src",
    "adapter-litellm": REPO / "packages" / "prism-adapter-litellm" / "src",
    "adapter-python": REPO / "packages" / "prism-adapter-python" / "src",
    "platform": REPO / "packages" / "prism-platform" / "src",
    "cli": REPO / "packages" / "prism-cli" / "src",
    "lsp": REPO / "packages" / "prism-lsp" / "src",
}

OWNED_NAMESPACES = {
    "prism.language": "language",
    "prism.transpiler": "transpiler",
    "prism.runtime": "runtime",
    "prism.sdk": "sdk",
    "prism.adapters.codex": "adapter-codex",
    "prism.adapters.litellm": "adapter-litellm",
    "prism.adapters.python": "adapter-python",
    "prism.platform": "platform",
    "prism.tooling.cli": "cli",
    "prism.tooling.lsp": "lsp",
    "prism.tooling.protocol": "lsp",
    "prism.tooling.ide_server": "lsp",
    "prism.tooling.workbench": "lsp",
}

LANGUAGE_LAYERS = {
    "kernel": 1,
    "core": 2,
    "verification": 3,
    "effects": 4,
    "evidence": 5,
    "workflows": 6,
    "interop": 7,
    "developer": 8,
}


@pytest.fixture(scope="module")
def import_graph() -> grimp.ImportGraph:
    config = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"][
        "importlinter"
    ]
    assert set(config["root_packages"]) == {*OWNED_NAMESPACES, "prism_stdlib"}
    return grimp.build_graph(
        *config["root_packages"],
        include_external_packages=config["include_external_packages"],
        exclude_type_checking_imports=config["exclude_type_checking_imports"],
        cache_dir=None,
    )


def test_language_internals_do_not_import_root_facade(
    import_graph: grimp.ImportGraph,
) -> None:
    assert language_facade_imports(import_graph) == []


def test_import_graph_covers_all_workspace_sources(
    import_graph: grimp.ImportGraph,
) -> None:
    missing: list[str] = []
    for root in (*CORE_SOURCE_ROOTS.values(), REPO / "libs" / "prism" / "src"):
        for path in root.rglob("*.py"):
            parts = path.relative_to(root).with_suffix("").parts
            module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
            if module not in import_graph.modules:
                missing.append(str(path.relative_to(REPO)))
    assert sorted(missing) == [], "Add untracked namespaces to the architecture roots"


def test_other_distributions_import_only_public_language_contracts(
    import_graph: grimp.ImportGraph,
) -> None:
    public_namespaces = {
        "prism.language",
        *(f"prism.language.{layer}" for layer in LANGUAGE_LAYERS),
        "prism.language.developer.syntax",
    }
    # Existing go-to-definition support reads intrinsic locations from api.py.
    # Remove this exact exception once the public API exposes those locations.
    # Equality also fails when the exception becomes obsolete.
    assert private_language_imports(import_graph, public_namespaces) == [
        ("prism.tooling.lsp.symbols.intrinsics", "prism.language.developer.api"),
    ]


def test_distributions_are_acyclic(import_graph: grimp.ImportGraph) -> None:
    owners = {**OWNED_NAMESPACES, "prism_stdlib": "stdlib"}
    dependencies = distribution_dependencies(import_graph, owners)
    TopologicalSorter(dependencies).prepare()


def test_imported_dependencies_are_declared(import_graph: grimp.ImportGraph) -> None:
    manifests = {
        owner: root.parent / "pyproject.toml"
        for owner, root in CORE_SOURCE_ROOTS.items()
    }
    manifests["stdlib"] = REPO / "libs" / "prism" / "pyproject.toml"
    projects = {
        owner: tomllib.loads(path.read_text())["project"]
        for owner, path in manifests.items()
    }
    namespaces = {
        namespace: projects[owner]["name"]
        for namespace, owner in {**OWNED_NAMESPACES, "prism_stdlib": "stdlib"}.items()
    }
    declarations = {
        project["name"]: declared_dependencies(project) for project in projects.values()
    }
    external_modules = {
        "dotenv": "python-dotenv",
        "litellm": "litellm",
        "neo4j": "neo4j",
        "pydantic": "pydantic",
        "typer": "typer",
        "yaml": "PyYAML",
    }
    violations = undeclared_dependencies(
        import_graph, namespaces, declarations, external_modules
    )
    assert violations == [], "\n".join(violations)


def test_optional_execution_imports_remain_lazy(
    import_graph: grimp.ImportGraph,
) -> None:
    config = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"][
        "importlinter"
    ]
    contract = next(
        c for c in config["contracts"] if c["id"] == "lightweight-language-server"
    )
    for edge in contract["ignore_imports"]:
        importer, imported = edge.split(" -> ")
        details = import_graph.get_import_details(importer=importer, imported=imported)
        namespace = next(
            n for n in OWNED_NAMESPACES if importer == n or importer.startswith(f"{n}.")
        )
        path = CORE_SOURCE_ROOTS[OWNED_NAMESPACES[namespace]].joinpath(
            *importer.split(".")
        )
        path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
        deferred_lines = function_scoped_import_lines(path.read_text())
        assert details and all(
            detail["line_number"] in deferred_lines for detail in details
        ), edge


def test_superseded_flat_language_sources_are_deleted() -> None:
    root = CORE_SOURCE_ROOTS["language"] / "prism" / "language"
    for name in (
        "api",
        "ast",
        "bindings",
        "checker",
        "ir",
        "modules",
        "parser",
        "syntax",
    ):
        assert not (root / f"{name}.py").exists()


def test_language_distribution_has_no_provider_dependencies() -> None:
    payload = tomllib.loads(
        (REPO / "packages" / "prism-language" / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert payload["project"].get("dependencies", []) == []


def test_repository_packages_do_not_mutate_python_import_paths() -> None:
    package_roots = (*CORE_SOURCE_ROOTS.values(), REPO / "libs")
    for path in (path for root in package_roots for path in root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "sys.path.insert" not in text
        assert "sys.path.append" not in text


def test_all_declared_core_distributions_have_build_metadata() -> None:
    expected = {
        "prism-language",
        "prism-transpiler",
        "prism-runtime",
        "prism-sdk",
        "prism-adapter-codex",
        "prism-adapter-litellm",
        "prism-adapter-python",
        "prism-platform",
        "prism-cli",
        "prism-lsp",
    }
    assert {
        path.parent.name for path in (REPO / "packages").glob("*/pyproject.toml")
    } == expected


def test_runtime_frontends_declare_their_effect_handlers() -> None:
    cli = tomllib.loads(
        (REPO / "packages" / "prism-cli" / "pyproject.toml").read_text(encoding="utf-8")
    )
    lsp = tomllib.loads(
        (REPO / "packages" / "prism-lsp" / "pyproject.toml").read_text(encoding="utf-8")
    )

    assert "prism-sdk[runtime]==1.0.0" in cli["project"]["dependencies"]
    assert "prism-transpiler==1.0.0" in cli["project"]["dependencies"]
    assert "prism-adapter-codex==1.0.0" in cli["project"]["dependencies"]
    assert "prism-adapter-litellm==1.0.0" in cli["project"]["dependencies"]
    assert "prism-adapter-python==1.0.0" in cli["project"]["dependencies"]
    assert (
        "prism-adapter-litellm==1.0.0"
        in lsp["project"]["optional-dependencies"]["workbench"]
    )
    assert (
        "prism-adapter-python==1.0.0"
        in lsp["project"]["optional-dependencies"]["workbench"]
    )


def test_repository_root_is_a_virtual_workspace() -> None:
    payload = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert payload["tool"]["uv"]["package"] is False
    assert "build-system" not in payload
    assert "scripts" not in payload["project"]
    assert "setuptools" not in payload["tool"]
    members = payload["tool"]["uv"]["workspace"]["members"]
    sources = payload["tool"]["uv"]["sources"]
    distribution_names = {
        tomllib.loads((REPO / member / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["name"]
        for member in members
    }
    assert set(sources) == distribution_names
    assert all(source == {"workspace": True} for source in sources.values())


def test_every_workspace_distribution_uses_current_release_version() -> None:
    root = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert root["project"]["version"] == "1.0.0"
    for member in root["tool"]["uv"]["workspace"]["members"]:
        payload = tomllib.loads(
            (REPO / member / "pyproject.toml").read_text(encoding="utf-8")
        )
        assert payload["project"]["version"] == "1.0.0", member


def test_distribution_sources_are_self_contained() -> None:
    manifests = sorted((REPO / "packages").glob("*/pyproject.toml"))
    manifests.extend(sorted((REPO / "libs").glob("*/pyproject.toml")))
    for manifest in manifests:
        payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
        source_roots = (
            payload.get("tool", {})
            .get("setuptools", {})
            .get("packages", {})
            .get("find", {})
            .get("where", [])
        )
        assert source_roots, (
            f"{manifest.relative_to(REPO)} does not declare a package source root"
        )
        for source_root in source_roots:
            assert ".." not in Path(source_root).parts, (
                f"{manifest.relative_to(REPO)} escapes its project"
            )
            resolved = (manifest.parent / source_root).resolve()
            assert resolved.is_relative_to(manifest.parent.resolve())
            assert resolved.is_dir()


def test_each_core_namespace_has_one_physical_owner() -> None:
    for namespace, owner in OWNED_NAMESPACES.items():
        relative = Path(*namespace.split("."))
        locations = [
            name
            for name, root in CORE_SOURCE_ROOTS.items()
            if (root / relative).is_dir()
        ]
        assert locations == [owner], (
            f"{namespace} is owned by {locations}, expected {owner}"
        )


def test_shared_prism_namespaces_are_implicit() -> None:
    for source_root in CORE_SOURCE_ROOTS.values():
        assert not (source_root / "prism" / "__init__.py").exists()
        assert not (source_root / "prism" / "adapters" / "__init__.py").exists()
        assert not (source_root / "prism" / "tooling" / "__init__.py").exists()
