# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workflow and reasoning composition symbols."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from prism.language.developer.syntax import (
    ChoiceComposition,
    NodeOccurrence,
    ParallelComposition,
    RepeatComposition,
    SequenceComposition,
)
from prism.tooling.protocol import PrismIdeSymbol

from .expressions import surface_expression_name
from .spans import symbol


def workflow_symbols(
    composition: Any, occurrence_contracts=None
) -> list[PrismIdeSymbol]:
    if isinstance(composition, NodeOccurrence):
        component = surface_expression_name(composition.component)
        name = composition.alias or component.rsplit(".", 1)[-1]
        return [
            symbol(
                name,
                "WorkflowNode",
                composition.span,
                detail=component,
                metadata={
                    "component": component,
                    "node_id": name,
                    **(
                        {
                            "declared_contract": asdict(
                                occurrence_contracts[id(composition)]
                            )
                        }
                        if occurrence_contracts
                        and id(composition) in occurrence_contracts
                        else {}
                    ),
                },
            )
        ]
    if isinstance(composition, SequenceComposition | ParallelComposition):
        return [
            symbol
            for child in composition.children
            for symbol in workflow_symbols(child, occurrence_contracts)
        ]
    if isinstance(composition, ChoiceComposition):
        return [
            *workflow_symbols(composition.router, occurrence_contracts),
            *(
                symbol
                for arm in composition.arms
                for child in arm.children
                for symbol in workflow_symbols(child, occurrence_contracts)
            ),
        ]
    if isinstance(composition, RepeatComposition):
        return [
            symbol
            for child in composition.children
            for symbol in workflow_symbols(child, occurrence_contracts)
        ]
    return []
