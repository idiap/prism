# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema model for argumentation-scheme specifications."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemeSpec(BaseModel):
    """Declarative spec describing one instantiated argument scheme family."""

    model_config = ConfigDict(extra="forbid")

    scheme_id: str
    version: str
    name: str
    premise_schema: dict[str, Any] = Field(default_factory=dict)
    conclusion_schema: dict[str, Any] = Field(default_factory=dict)
    critical_question_templates: list[str] = Field(default_factory=list)
    burden_policy: dict[str, Any] = Field(default_factory=dict)
