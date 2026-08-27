# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Stable public facade for the canonical Prism language."""

from prism.language.core import (
    InMemoryModuleLoader,
    ModuleLoader,
    ModuleSource,
    TypedModule,
)
from prism.language.developer import (
    CheckedProgram,
    PrismSyntaxError,
    PrismTypeError,
    check,
    compile,
    elaborate,
    parse_source,
)
from prism.language.developer.syntax import Program
from prism.language.effects import ExecutableProgram

__all__ = [
    "CheckedProgram",
    "ExecutableProgram",
    "InMemoryModuleLoader",
    "ModuleLoader",
    "ModuleSource",
    "PrismSyntaxError",
    "PrismTypeError",
    "Program",
    "TypedModule",
    "check",
    "compile",
    "elaborate",
    "parse_source",
]
