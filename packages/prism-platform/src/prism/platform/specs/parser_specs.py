# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed schema model for parser specifications."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParserSpec(BaseModel):
    """Declarative spec describing one parser entrypoint and schema."""

    model_config = ConfigDict(extra="forbid")

    spec_id: str
    version: str
    name: str
    schema_definition: dict[str, Any] = Field(default_factory=dict, alias="schema")
