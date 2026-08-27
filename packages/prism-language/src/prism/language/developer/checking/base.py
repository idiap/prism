# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Shared typing boundary for cooperative checker phases."""

from typing import Any, NoReturn

from ..diagnostics import SourceSpan


class _CheckerPhase:
    """Let phase mixins call methods supplied by the composed checker."""

    def fail(self, message: str, span: SourceSpan, code: str) -> NoReturn:
        """Abort checking; implemented by the composed checker's type phase."""

        raise NotImplementedError

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)
