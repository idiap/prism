# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Executable dependency rules for the Prism distribution graph."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

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

PACKAGE_ROOTS = {
    "language": CORE_SOURCE_ROOTS["language"] / "prism" / "language",
    "transpiler": CORE_SOURCE_ROOTS["transpiler"] / "prism" / "transpiler",
    "runtime": CORE_SOURCE_ROOTS["runtime"] / "prism" / "runtime",
    "sdk": CORE_SOURCE_ROOTS["sdk"] / "prism" / "sdk",
    "adapters": CORE_SOURCE_ROOTS["adapter-litellm"] / "prism" / "adapters",
    "platform": CORE_SOURCE_ROOTS["platform"] / "prism" / "platform",
    "tooling": CORE_SOURCE_ROOTS["lsp"] / "prism" / "tooling",
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

FORBIDDEN_IMPORTS = {
    "language": {
        "prism.runtime",
        "prism.adapters",
        "prism.platform",
        "prism.sdk",
        "prism.tooling",
    },
    "transpiler": {
        "prism.runtime",
        "prism.adapters",
        "prism.platform",
        "prism.sdk",
        "prism.tooling",
    },
    "runtime": {"prism.adapters", "prism.platform", "prism.sdk", "prism.tooling"},
    "adapters": {"prism.platform", "prism.sdk", "prism.tooling"},
    "sdk": {"prism.adapters", "prism.platform", "prism.tooling"},
    "platform": {"prism.adapters", "prism.sdk", "prism.tooling"},
}

DOMAIN_PACKAGES = {
    "prism_stdlib",
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


def test_language_layers_only_depend_downward() -> None:
    violations: list[str] = []
    root = PACKAGE_ROOTS["language"]
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if len(relative.parts) == 1:
            continue
        owner = relative.parts[0]
        owner_layer = LANGUAGE_LAYERS[owner]
        for imported in _module_imports(path):
            if imported == "prism.language":
                violations.append(
                    f"{path.relative_to(REPO)} imports the root language facade"
                )
                continue
            prefix = "prism.language."
            if not imported.startswith(prefix):
                continue
            target = imported.removeprefix(prefix).split(".", 1)[0]
            target_layer = LANGUAGE_LAYERS.get(target)
            if target_layer is not None and target_layer > owner_layer:
                violations.append(
                    f"{path.relative_to(REPO)} (layer {owner_layer}) imports "
                    f"{imported} (layer {target_layer})"
                )
    assert violations == []


def test_other_distributions_import_only_public_language_contracts() -> None:
    public_namespaces = {
        "prism.language",
        *(f"prism.language.{layer}" for layer in LANGUAGE_LAYERS),
        "prism.language.developer.syntax",
    }
    violations: list[str] = []
    for source_root in CORE_SOURCE_ROOTS.values():
        if source_root == CORE_SOURCE_ROOTS["language"]:
            continue
        for path in source_root.rglob("*.py"):
            for imported in _module_imports(path):
                if (
                    imported.startswith("prism.language.")
                    and imported not in public_namespaces
                ):
                    violations.append(
                        f"{path.relative_to(REPO)} imports private language module {imported}"
                    )
    assert violations == []


def test_language_does_not_import_higher_distributions() -> None:
    forbidden = {
        "prism.adapters",
        "prism.runtime",
        "prism.sdk",
        "prism.transpiler",
        "prism.tooling",
    }
    violations: list[str] = []
    for path in PACKAGE_ROOTS["language"].rglob("*.py"):
        for imported in _module_imports(path):
            offending = _matching_forbidden(imported, forbidden)
            if offending:
                violations.append(
                    f"{path.relative_to(REPO)} imports {imported} ({offending})"
                )
    assert violations == []


def test_superseded_flat_language_sources_are_deleted() -> None:
    root = PACKAGE_ROOTS["language"]
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


def test_dependency_direction_is_enforced() -> None:
    violations: list[str] = []
    for package, forbidden in FORBIDDEN_IMPORTS.items():
        roots = [PACKAGE_ROOTS[package]]
        if package == "adapters":
            roots.extend(
                (
                    CORE_SOURCE_ROOTS["adapter-codex"] / "prism" / "adapters",
                    CORE_SOURCE_ROOTS["adapter-python"] / "prism" / "adapters",
                )
            )
        for root in roots:
            for path in root.rglob("*.py"):
                for imported in _module_imports(path):
                    offending = _matching_forbidden(
                        imported, forbidden | DOMAIN_PACKAGES
                    )
                    if offending:
                        violations.append(
                            f"{path.relative_to(REPO)} imports {imported} (forbidden by {offending})"
                        )
    assert violations == []


def test_language_distribution_has_no_provider_dependencies() -> None:
    payload = tomllib.loads(
        (REPO / "packages" / "prism-language" / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )
    assert payload["project"].get("dependencies", []) == []
    imports = set().union(
        *(_module_imports(path) for path in PACKAGE_ROOTS["language"].rglob("*.py"))
    )
    assert not imports.intersection(
        {"litellm", "pydantic", "yaml", "sympy", "typer", "dotenv"}
    )


def test_repository_packages_do_not_mutate_python_import_paths() -> None:
    package_roots = (*CORE_SOURCE_ROOTS.values(), REPO / "libs")
    for path in (path for root in package_roots for path in root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "sys.path.insert" not in text
        assert "sys.path.append" not in text


def test_language_server_does_not_import_optional_execution_packages() -> None:
    forbidden = {"prism.runtime", "prism.adapters", "prism.platform"}
    violations: list[str] = []
    for package in ("lsp", "protocol", "ide_server"):
        for path in (PACKAGE_ROOTS["tooling"] / package).rglob("*.py"):
            for imported in _module_imports(path):
                offending = _matching_forbidden(imported, forbidden)
                if offending:
                    violations.append(
                        f"{path.relative_to(REPO)} imports {imported} (optional package {offending})"
                    )
    assert violations == []


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


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return imports


def _matching_forbidden(imported: str, forbidden: set[str]) -> str | None:
    return next(
        (
            package
            for package in forbidden
            if imported == package or imported.startswith(f"{package}.")
        ),
        None,
    )
