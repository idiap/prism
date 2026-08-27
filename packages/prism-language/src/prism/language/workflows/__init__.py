# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 6: typed agents, reasoning, and deterministic workflows."""

from .ir import (
    Agent,
    Choice,
    ChoiceArm,
    GuardedExit,
    NodeOccurrence,
    Parallel,
    ReasoningDefinition,
    RelationDefinition,
    Repeat,
    Sequence,
    Tool,
    WorkflowDefinition,
)
from .scope import ExecutionScope, ExecutionScopeKind

__all__ = [
    "Agent",
    "Choice",
    "ChoiceArm",
    "ExecutionScope",
    "ExecutionScopeKind",
    "GuardedExit",
    "NodeOccurrence",
    "Parallel",
    "ReasoningDefinition",
    "RelationDefinition",
    "Repeat",
    "Sequence",
    "Tool",
    "WorkflowDefinition",
]
