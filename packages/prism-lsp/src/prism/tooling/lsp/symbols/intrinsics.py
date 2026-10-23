# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Navigable definitions for compiler intrinsics."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from prism.language.core import CallableContract
from prism.language.developer import api as developer_api
from prism.tooling.protocol import PrismIdeSymbol, PrismIdeSymbolSpan


def intrinsic_symbols(
    callable_contracts: Mapping[str, CallableContract],
) -> list[PrismIdeSymbol]:
    """Expose compiler intrinsics as navigable definitions for editor clients."""

    definition_path = Path(developer_api.__file__).resolve()
    lines = definition_path.read_text(encoding="utf-8").splitlines()
    result: list[PrismIdeSymbol] = []
    for name, contract in callable_contracts.items():
        if contract.kind != "intrinsic":
            continue
        needle = f'"{name}": ('
        location = next(
            (
                (line, text.index(needle) + 1)
                for line, text in enumerate(lines)
                if needle in text
            ),
            None,
        )
        if location is None:
            continue
        line, character = location
        result.append(
            PrismIdeSymbol(
                name=name,
                kind="Intrinsic",
                span=PrismIdeSymbolSpan(
                    line=line,
                    character=character,
                    end_line=line,
                    end_character=character + len(name),
                ),
                detail=contract.type.render(),
                definition_path=str(definition_path),
                source_ref="compiler-intrinsic",
            )
        )
    return result
