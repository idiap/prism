# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Structured failures emitted by the trusted dependent kernel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KernelDiagnostic:
    code: str
    message: str
    path: tuple[str, ...] = ()

    def render(self) -> str:
        location = f" at {'/'.join(self.path)}" if self.path else ""
        return f"[{self.code}]{location}: {self.message}"


class KernelError(ValueError):
    """A fail-closed kernel rejection."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "kernel-error",
        path: tuple[str, ...] = (),
    ) -> None:
        self.diagnostic = KernelDiagnostic(code, message, path)
        super().__init__(message)


class KernelResourceError(KernelError):
    """Reduction stopped before a decision because its deterministic limit fired."""

    def __init__(self, message: str = "kernel reduction limit exhausted") -> None:
        super().__init__(message, code="kernel-resource-limit")
