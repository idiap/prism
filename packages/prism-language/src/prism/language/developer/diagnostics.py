# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Source diagnostics for the canonical frontend."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceSpan:
    line: int
    column: int = 1
    end_line: int | None = None
    end_column: int | None = None

    def render(self, path: str | None = None) -> str:
        location = f"{self.line}:{self.column}"
        return f"{path}:{location}" if path else location


@dataclass(frozen=True, slots=True)
class Diagnostic:
    message: str
    span: SourceSpan
    code: str


class PrismDiagnosticError(ValueError):
    def __init__(self, diagnostic: Diagnostic, path: str | None = None) -> None:
        self.diagnostic = diagnostic
        self.path = path
        super().__init__(
            f"{diagnostic.span.render(path)}: {diagnostic.message} [{diagnostic.code}]"
        )


class PrismSyntaxError(PrismDiagnosticError):
    pass


class PrismTypeError(PrismDiagnosticError):
    pass
