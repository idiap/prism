# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KERNEL = ROOT / "packages/prism-language/src/prism/language/kernel"


def test_kernel_imports_only_the_standard_library_and_its_own_modules() -> None:
    for path in KERNEL.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                root = (node.module or "").partition(".")[0]
                assert root in sys.stdlib_module_names, (path, node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.partition(".")[0]
                    assert root in sys.stdlib_module_names, (path, alias.name)


def test_active_tree_has_no_legacy_native_proof_protocol() -> None:
    forbidden = (
        "Candidate" + "Proof",
        "Certificate" + "Verifier",
        "Verifier" + "Registry",
        "candidate" + "_proof",
    )
    excluded = {
        ROOT / "KERNEL_REFACTOR.md",
        ROOT / "DYNAMIC_GOALS_PLAN.md",
    }
    for path in ROOT.rglob("*"):
        if (
            not path.is_file()
            or path in excluded
            or ".git" in path.parts
            or ".prism" in path.parts
            or ".venv" in path.parts
            or ".pytest_cache" in path.parts
            or ".ruff_cache" in path.parts
            or "__pycache__" in path.parts
            or "node_modules" in path.parts
            or "dist" in path.parts
            or ("docs" in path.parts and "history" in path.parts)
            or "catalog" in path.parts
        ):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert not any(token in source for token in forbidden), path
