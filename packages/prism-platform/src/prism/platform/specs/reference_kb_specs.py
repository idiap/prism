# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed specs for managed reference knowledge bases used by PRISM skills."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReferenceKBResourceSpec(BaseModel):
    """One concrete local resource that materializes part of a reference KB."""

    model_config = ConfigDict(extra="forbid")

    resource_id: str
    kind: Literal["source-tree", "index-artifact", "documentation", "workspace-root"]
    path_hint: str
    description: str


class ReferenceKBCheckSpec(BaseModel):
    """One availability check used to validate that a reference KB is present."""

    model_config = ConfigDict(extra="forbid")

    check_id: str
    kind: Literal["path-exists", "glob-exists", "manual"]
    target: str
    description: str
    required: bool = True


class ReferenceKBSpec(BaseModel):
    """Catalog record for one managed reference KB."""

    model_config = ConfigDict(extra="forbid")

    kb_id: str
    version: str
    name: str
    description: str
    kb_kind: Literal[
        "theorem-library",
        "library-index",
        "documentation-index",
        "knowledge-graph",
        "dataset",
        "corpus",
        "law-pack",
    ]
    source_project: str
    local_root: str
    semantic_folder: str
    semantic_tags: list[str] = Field(default_factory=list)
    runtime_dependencies: list[str] = Field(default_factory=list)
    linked_backend_ids: list[str] = Field(default_factory=list)
    bootstrap_steps: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    resources: list[ReferenceKBResourceSpec] = Field(default_factory=list)
    availability_checks: list[ReferenceKBCheckSpec] = Field(default_factory=list)
