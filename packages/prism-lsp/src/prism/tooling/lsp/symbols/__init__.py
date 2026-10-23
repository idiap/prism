# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Canonical-AST-backed symbol and type indexes for Prism documents."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from prism.language.core import Binding, CallableContract
from prism.language.developer.syntax import Program
from prism.tooling.protocol import PrismIdeSymbol

from .declarations import declaration_symbols
from .intrinsics import intrinsic_symbols
from .types import build_type_index

__all__ = ["build_symbol_index", "build_type_index"]


def build_symbol_index(
    program: Program,
    globals_scope: Mapping[str, Binding],
    *,
    callable_contracts: Mapping[str, CallableContract],
    project_root: Path,
    occurrence_contracts=None,
) -> list[PrismIdeSymbol]:
    symbols: list[PrismIdeSymbol] = []
    for declaration in program.declarations:
        symbols.extend(
            declaration_symbols(declaration, globals_scope, occurrence_contracts)
        )
    symbols.extend(intrinsic_symbols(callable_contracts))
    return symbols
