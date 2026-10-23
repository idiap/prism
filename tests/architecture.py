# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Repository-specific checks over resolved Python imports."""

import ast
import sys
from typing import Any

from grimp import ImportGraph
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def function_scoped_import_lines(source: str) -> set[int]:
    return {
        node.lineno
        for function in ast.walk(ast.parse(source))
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Import | ast.ImportFrom)
    }


def language_facade_imports(graph: ImportGraph) -> list[tuple[str, str]]:
    return sorted(
        (module, "prism.language")
        for module in graph.modules
        if module.startswith("prism.language.")
        and "prism.language" in graph.find_modules_directly_imported_by(module)
    )


def private_language_imports(
    graph: ImportGraph, public_namespaces: set[str]
) -> list[tuple[str, str]]:
    return sorted(
        (module, imported)
        for module in graph.modules
        if module != "prism.language" and not module.startswith("prism.language.")
        for imported in graph.find_modules_directly_imported_by(module)
        if imported.startswith("prism.language.") and imported not in public_namespaces
    )


def distribution_dependencies(
    graph: ImportGraph, namespaces: dict[str, str]
) -> dict[str, tuple[str, ...]]:
    owners = {
        module: owner
        for module in graph.modules
        for namespace, owner in namespaces.items()
        if module == namespace or module.startswith(f"{namespace}.")
    }
    dependencies: dict[str, set[str]] = {
        owner: set() for owner in sorted(set(namespaces.values()))
    }
    for module, owner in owners.items():
        for imported in graph.find_modules_directly_imported_by(module):
            target = owners.get(imported)
            if target is not None and target != owner:
                dependencies[owner].add(target)
    return {owner: tuple(sorted(targets)) for owner, targets in dependencies.items()}


def declared_dependencies(project: dict[str, Any]) -> set[str]:
    # Check declaration presence across all extras and platforms, not activation.
    requirements = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        requirements.extend(extra)
    return {canonicalize_name(Requirement(value).name) for value in requirements}


def undeclared_dependencies(
    graph: ImportGraph,
    namespaces: dict[str, str],
    declarations: dict[str, set[str]],
    external_modules: dict[str, str],
) -> list[str]:
    owners = {
        module: owner
        for module in graph.modules
        for namespace, owner in namespaces.items()
        if module == namespace or module.startswith(f"{namespace}.")
    }
    violations: list[str] = []
    for module, owner in owners.items():
        for imported in graph.find_modules_directly_imported_by(module):
            root = imported.partition(".")[0]
            if root in sys.stdlib_module_names:
                continue
            target = owners.get(imported) or external_modules.get(root)
            if target is None:
                violations.append(
                    f"{module} imports {imported}, whose distribution is unknown; "
                    "add its namespace or external module ownership mapping"
                )
            elif (
                target != owner and canonicalize_name(target) not in declarations[owner]
            ):
                violations.append(
                    f"{owner}: {module} imports {imported}, but does not declare {target}"
                )
    return sorted(violations)
