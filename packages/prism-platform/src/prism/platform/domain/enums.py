# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform string enums for tasks, artifacts, and debts."""

from __future__ import annotations

from enum import StrEnum


class ArtifactStatus(StrEnum):
    """Lifecycle states for versioned artifacts."""

    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class DebtStatus(StrEnum):
    """Statuses for unresolved debt records."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    WAIVED = "waived"


class DebtSeverity(StrEnum):
    """Priority levels for unresolved debt."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DecisionKind(StrEnum):
    """Kinds of critic decisions that alter solver state."""

    ACCEPT = "accept"
    OPEN = "open"
    REPAIR = "repair"
    REVISE_SPEC = "revise_spec"
    REPLAN = "replan"
    DEFEAT = "defeat"
    DEFER = "defer"
