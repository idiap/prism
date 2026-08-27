# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform event-record models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventRecord(BaseModel):
    """A single append-only event emitted during a solver run."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    run_id: str
    event_type: str
    actor: str
    timestamp: str
    causation_id: str | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
