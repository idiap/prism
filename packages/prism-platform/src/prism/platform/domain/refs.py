# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Compact platform artifact references."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ArtifactRef(BaseModel):
    """A lightweight pointer to a specific artifact version."""

    model_config = ConfigDict(extra="forbid")

    oid: str
    vid: str
    kind: str
