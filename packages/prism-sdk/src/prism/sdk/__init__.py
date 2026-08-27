# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Public integration SDK for Prism packages and workspaces."""

from prism.sdk.workspace import WorkspaceModuleLoader, resolve_project_root

__all__ = [
    "WorkspaceModuleLoader",
    "resolve_project_root",
]
