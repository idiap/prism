# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Declaration checks over small resolved-import fixtures."""

from typing import Any

import grimp
import pytest

from tests.architecture import declared_dependencies, undeclared_dependencies


def _graph(*edges: tuple[str, str]) -> grimp.ImportGraph:
    graph = grimp.ImportGraph()
    for module in sorted({module for edge in edges for module in edge}):
        graph.add_module(module)
    for importer, imported in edges:
        graph.add_import(importer=importer, imported=imported)
    return graph


@pytest.mark.parametrize(
    "project,missing",
    [
        ({"dependencies": ["pyyaml>=6.0"]}, False),
        ({"optional-dependencies": {"yaml": ["PyYAML>=6.0"]}}, False),
        # Presence is checked across platforms, without evaluating markers.
        ({"dependencies": ["PyYAML[feature]>=6; sys_platform == 'win32'"]}, False),
        ({}, True),
        ({"dependencies": ["python-dotenv"]}, True),
    ],
)
def test_external_dependency_declarations(
    project: dict[str, Any], missing: bool
) -> None:
    graph = _graph(("prism.runtime.knowledge", "yaml"))
    violations = undeclared_dependencies(
        graph,
        {"prism.runtime": "prism-runtime"},
        {"prism-runtime": declared_dependencies(project)},
        {"yaml": "PyYAML"},
    )
    assert violations == (
        [
            "prism-runtime: prism.runtime.knowledge imports yaml, but does not declare PyYAML"
        ]
        if missing
        else []
    )


@pytest.mark.parametrize("direct", [False, True])
def test_transitive_dependency_does_not_satisfy_direct_import(direct: bool) -> None:
    graph = _graph(
        ("prism.adapters.python", "prism.language.effects"),
        ("prism.runtime", "prism.language.effects"),
    )
    adapter_requirements = ["prism-runtime==1.0.0"]
    if direct:
        adapter_requirements.append("Prism_Language==1.0.0")
    violations = undeclared_dependencies(
        graph,
        {
            "prism.adapters.python": "prism-adapter-python",
            "prism.runtime": "prism-runtime",
            "prism.language": "prism-language",
        },
        {
            "prism-adapter-python": declared_dependencies(
                {"dependencies": adapter_requirements}
            ),
            "prism-runtime": {"prism-language"},
            "prism-language": set(),
        },
        {},
    )
    assert violations == (
        []
        if direct
        else [
            "prism-adapter-python: prism.adapters.python imports prism.language.effects, "
            "but does not declare prism-language"
        ]
    )


def test_unknown_external_module_requires_ownership_even_if_name_is_declared() -> None:
    violations = undeclared_dependencies(
        _graph(("prism.runtime", "new_provider")),
        {"prism.runtime": "prism-runtime"},
        {"prism-runtime": {"new-provider"}},
        {},
    )
    assert violations == [
        "prism.runtime imports new_provider, whose distribution is unknown; "
        "add its namespace or external module ownership mapping"
    ]


def test_same_distribution_and_standard_library_need_no_declarations() -> None:
    graph = _graph(
        ("prism.tooling.lsp", "prism.tooling.protocol"),
        ("prism.tooling.protocol", "json"),
    )
    assert (
        undeclared_dependencies(
            graph,
            {"prism.tooling.lsp": "prism-lsp", "prism.tooling.protocol": "prism-lsp"},
            {"prism-lsp": set()},
            {},
        )
        == []
    )
