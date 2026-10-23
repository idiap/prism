# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 8: canonical frontend and developer APIs."""

from .api import CheckedProgram, check, compile, elaborate, parse_source, parse_type
from .core_elaboration import (
    CoreLocal,
    elaborate_proof_source,
    elaborate_type_text,
    reify_runtime_value,
)
from .diagnostics import (
    Diagnostic,
    PrismDiagnosticError,
    PrismSyntaxError,
    PrismTypeError,
    SourceSpan,
)

__all__ = [
    "CheckedProgram",
    "CoreLocal",
    "Diagnostic",
    "PrismDiagnosticError",
    "PrismSyntaxError",
    "PrismTypeError",
    "SourceSpan",
    "check",
    "compile",
    "elaborate",
    "elaborate_proof_source",
    "elaborate_type_text",
    "parse_source",
    "parse_type",
    "reify_runtime_value",
]
