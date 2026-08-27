# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 7: interoperability contracts."""

from .contracts import (
    ConnectionReference,
    ResourceReference,
    SourceReference,
)

__all__ = [
    "ConnectionReference",
    "ResourceReference",
    "SourceReference",
]
