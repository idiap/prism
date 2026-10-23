# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Statement and expression checking, composed from focused checker phases."""

from __future__ import annotations

from .arguments import _ArgumentCheckingMixin
from .builtins import _BuiltinCheckingMixin
from .calls import _CallCheckingMixin
from .collections import _CollectionInferenceMixin
from .compatibility import _TypeCompatibilityMixin
from .inference import _InferenceMixin
from .reasoning import _ReasoningCheckingMixin
from .resolution import _ResolutionCheckingMixin
from .statements import _StatementCheckingMixin


class _ExpressionCheckingMixin(
    _StatementCheckingMixin,
    _InferenceMixin,
    _CollectionInferenceMixin,
    _CallCheckingMixin,
    _BuiltinCheckingMixin,
    _ResolutionCheckingMixin,
    _ReasoningCheckingMixin,
    _ArgumentCheckingMixin,
    _TypeCompatibilityMixin,
):
    """Preserve the expression phase's interface for the composed checker."""
