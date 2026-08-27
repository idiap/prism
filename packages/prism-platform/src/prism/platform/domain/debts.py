# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform debt records for unresolved run issues."""

from __future__ import annotations

from typing import Any

from prism.platform.domain.enums import DebtSeverity, DebtStatus
from pydantic import BaseModel, ConfigDict


class DebtRecord(BaseModel):
    """A single unresolved issue that must be discharged, waived, or tracked."""

    model_config = ConfigDict(extra="forbid")

    debt_id: str
    reason: str
    scope: dict[str, Any]
    severity: DebtSeverity
    opened_at: str
    discharge_condition: dict[str, Any]
    status: DebtStatus
