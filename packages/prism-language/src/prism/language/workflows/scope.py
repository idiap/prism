# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Execution scopes shared by workflow and lifecycle-hook runtime events."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExecutionScopeKind(StrEnum):
    SESSION = "session"
    AGENT = "agent"
    WORKFLOW = "workflow"


@dataclass(frozen=True, slots=True)
class ExecutionScope:
    kind: ExecutionScopeKind
    scope_id: str


__all__ = ["ExecutionScope", "ExecutionScopeKind"]
