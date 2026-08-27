# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Build external agent artifacts into standalone typed Prism modules."""

from .builder import (
    BuildError,
    BuiltModule,
    HookProvider,
    build_hooks_module,
    build_skill_module,
)

__all__ = [
    "BuildError",
    "BuiltModule",
    "HookProvider",
    "build_hooks_module",
    "build_skill_module",
]
