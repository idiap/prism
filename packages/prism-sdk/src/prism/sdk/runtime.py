# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Optional runtime integration helpers for Prism workspaces."""

from prism.sdk.workspace import (
    LocalResourceResolver,
    load_workspace_knowledge,
)

__all__ = [
    "LocalResourceResolver",
    "load_workspace_knowledge",
]
