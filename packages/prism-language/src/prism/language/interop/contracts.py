# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed runtime references to external resources and providers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceReference:
    locator: str
    type_name: str
    content: bytes | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if self.content is None:
            if self.content_hash is not None:
                raise ValueError(
                    "external resource reference cannot declare inline hash"
                )
            return
        computed = f"sha256:{hashlib.sha256(self.content).hexdigest()}"
        if self.content_hash is not None and self.content_hash != computed:
            raise ValueError("inline resource hash does not match content")
        object.__setattr__(self, "content_hash", computed)


@dataclass(frozen=True, slots=True)
class SourceReference:
    logical_name: str
    schema: str | None = None
    graph: bool = False
    adapter_id: str | None = None

    @property
    def source_id(self) -> str:
        return self.logical_name

    @property
    def schema_id(self) -> str | None:
        return self.schema


@dataclass(frozen=True, slots=True)
class ConnectionReference:
    logical_name: str
    interface: str
