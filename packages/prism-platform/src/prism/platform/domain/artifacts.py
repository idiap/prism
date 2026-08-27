# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform artifact version models."""

from __future__ import annotations

from typing import Any

from prism.platform.domain.enums import ArtifactStatus
from prism.platform.domain.refs import ArtifactRef
from pydantic import BaseModel, ConfigDict, Field


class ArtifactOrigin(BaseModel):
    """Trace metadata describing where an artifact version came from."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str | None = None
    spec_id: str | None = None
    spec_version: str | None = None
    prompt_version: str | None = None
    frontier_id: str | None = None
    causation_id: str | None = None
    correlation_id: str | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class ArtifactVersion(BaseModel):
    """A versioned immutable artifact stored in the object layer."""

    model_config = ConfigDict(extra="forbid")

    oid: str
    vid: str
    kind: str
    payload: dict[str, Any]
    semantic_type_id: str | None = None
    semantic_parent_type_ids: list[str] = Field(default_factory=list)
    semantic_facets: dict[str, Any] = Field(default_factory=dict)
    deps: list[str] = Field(default_factory=list)
    origin: ArtifactOrigin
    status: ArtifactStatus
    created_at: str

    def ref(self) -> ArtifactRef:
        """Return the compact reference form used by downstream components."""
        return ArtifactRef(oid=self.oid, vid=self.vid, kind=self.kind)
