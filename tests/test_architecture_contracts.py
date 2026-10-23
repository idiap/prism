# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Exercise the real contracts against isolated, deliberately invalid packages."""

import json
import os
import subprocess
import sys
import tomllib
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

import grimp
import pytest

from tests.architecture import (
    distribution_dependencies,
    function_scoped_import_lines,
    language_facade_imports,
    private_language_imports,
)

REPO = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["importlinter"]


def _write_module(root: Path, name: str, source: str) -> None:
    path = root.joinpath(*name.split("."))
    path = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


@pytest.fixture
def fixture_workspace(tmp_path: Path) -> Path:
    # Leave prism, prism.adapters and prism.tooling as implicit namespaces.
    # Each concrete fixture portion takes precedence over the installed workspace.
    layers = next(
        c["layers"] for c in CONFIG["contracts"] if c["id"] == "language-layers"
    )
    for name in [
        *CONFIG["root_packages"],
        *(f"prism.language.{layer}" for layer in layers),
    ]:
        path = tmp_path.joinpath(*name.split("."))
        path.mkdir(parents=True, exist_ok=True)
        (path / "__init__.py").write_text("")
    for module, source in {
        "prism.tooling.ide_server": "def workbench():\n    import prism.tooling.workbench.service\n",
        "prism.tooling.workbench.service": "",
        "prism.sdk.workspace": "def knowledge():\n    import prism.runtime.knowledge\n",
        "prism.runtime.knowledge": "",
    }.items():
        _write_module(tmp_path, module, source)
    (tmp_path / "pyproject.toml").write_text((REPO / "pyproject.toml").read_text())
    return tmp_path


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    "modules,broken",
    [
        (
            {
                "prism.language.developer.consumer": "from ..core import model\n",
                "prism.language.core.model": "",
            },
            None,
        ),
        (
            {"prism.language.core.consumer": "import prism.language.developer\n"},
            "Language layers only depend downward",
        ),
        (
            {"prism.language.core.consumer": "from .. import developer\n"},
            "Language layers only depend downward",
        ),
        (
            {
                "prism.language.core.consumer": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import prism.language.developer\n"
            },
            "Language layers only depend downward",
        ),
        (
            {"prism.language.consumer": "from prism import runtime\n"},
            "Language is independent of execution and tooling",
        ),
        (
            {"prism.transpiler.consumer": "import prism.sdk\n"},
            "Transpiler is independent of execution and tooling",
        ),
        (
            {"prism.runtime.consumer": "import prism.adapters.python\n"},
            "Runtime is independent of providers and applications",
        ),
        (
            {"prism.adapters.python": "import prism.sdk\n"},
            "Adapters are independent of applications",
        ),
        (
            {"prism.sdk.consumer": "import prism.platform\n"},
            "SDK is independent of providers and applications",
        ),
        (
            {"prism.platform.consumer": "import prism.tooling.cli\n"},
            "Platform is independent of providers and frontends",
        ),
        (
            {
                "prism.tooling.lsp": "import prism.sdk.helper\n",
                "prism.sdk.helper": "import prism.runtime\n",
            },
            "Language server does not require optional execution packages",
        ),
        (
            {"prism.language.core.consumer": "import pydantic.fields\n"},
            "Language does not import provider dependencies",
        ),
        (
            {"prism.runtime.consumer": "import prism_stdlib\n"},
            "Runtime is independent of providers and applications",
        ),
        ({"prism.language.new_layer": ""}, "Language layers only depend downward"),
    ],
)
def test_import_contracts(
    fixture_workspace: Path, modules: dict[str, str], broken: str | None
) -> None:
    for name, source in modules.items():
        _write_module(fixture_workspace, name, source)
    result = _run(
        fixture_workspace,
        "-c",
        "from importlinter.cli import lint_imports; raise SystemExit(lint_imports(no_cache=True, no_logo=True))",
    )
    output = result.stdout + result.stderr
    assert result.returncode == (1 if broken else 0), output
    assert f"{broken} BROKEN" in output if broken else "0 broken" in output


def _fixture_graph(root: Path) -> grimp.ImportGraph:
    result = _run(
        root,
        "-c",
        "import grimp, json, tomllib; "
        "config = tomllib.load(open('pyproject.toml', 'rb'))['tool']['importlinter']; "
        "g = grimp.build_graph(*config['root_packages'], cache_dir=None); "
        "print(json.dumps({m: sorted(g.find_modules_directly_imported_by(m)) for m in sorted(g.modules)}))",
    )
    assert result.returncode == 0, result.stderr
    imports = json.loads(result.stdout)
    graph = grimp.ImportGraph()
    for module in imports:
        graph.add_module(module)
    for module, targets in imports.items():
        for target in targets:
            graph.add_import(importer=module, imported=target)
    return graph


@pytest.mark.parametrize(
    "consumer",
    ["from prism.language import core\n", "from prism.language.core import private\n"],
)
def test_public_facade_allows_indirect_but_not_direct_private_imports(
    fixture_workspace: Path, consumer: str
) -> None:
    _write_module(
        fixture_workspace, "prism.language.core", "from .private import Value\n"
    )
    _write_module(
        fixture_workspace, "prism.language.core.private", "class Value: pass\n"
    )
    _write_module(fixture_workspace, "prism.runtime", consumer)
    violations = private_language_imports(
        _fixture_graph(fixture_workspace), {"prism.language.core"}
    )
    expected = (
        [("prism.runtime", "prism.language.core.private")]
        if "private" in consumer
        else []
    )
    assert violations == expected


def test_relative_import_of_language_facade_is_rejected(
    fixture_workspace: Path,
) -> None:
    _write_module(fixture_workspace, "prism.language", "VALUE = 1\n")
    _write_module(fixture_workspace, "prism.language.core", "from .. import VALUE\n")
    assert language_facade_imports(_fixture_graph(fixture_workspace)) == [
        ("prism.language.core", "prism.language")
    ]


@pytest.mark.parametrize("cycle", [False, True])
def test_distribution_cycles_include_all_portions_of_one_owner(
    fixture_workspace: Path, cycle: bool
) -> None:
    _write_module(fixture_workspace, "prism.tooling.cli", "import prism.tooling.lsp\n")
    _write_module(
        fixture_workspace, "prism.tooling.lsp", "import prism.tooling.protocol\n"
    )
    _write_module(
        fixture_workspace,
        "prism.tooling.protocol",
        "import prism.tooling.cli\n" if cycle else "import prism.tooling.lsp\n",
    )
    dependencies = distribution_dependencies(
        _fixture_graph(fixture_workspace),
        {
            "prism.tooling.cli": "cli",
            "prism.tooling.lsp": "lsp",
            "prism.tooling.protocol": "lsp",
        },
    )
    if cycle:
        with pytest.raises(CycleError):
            TopologicalSorter(dependencies).prepare()
    else:
        TopologicalSorter(dependencies).prepare()


@pytest.mark.parametrize(
    "source,expected",
    [
        ("import prism.runtime\n", set()),
        ("if True:\n    import prism.runtime\n", set()),
        ("def run():\n    import prism.runtime\n", {2}),
        (
            "class Server:\n    async def run(self):\n        from prism import runtime\n",
            {3},
        ),
    ],
)
def test_optional_imports_must_remain_function_scoped(
    source: str, expected: set[int]
) -> None:
    assert function_scoped_import_lines(source) == expected
