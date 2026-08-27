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
