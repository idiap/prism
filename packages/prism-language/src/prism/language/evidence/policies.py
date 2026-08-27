# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed material-policy contracts."""

from __future__ import annotations

from dataclasses import dataclass

from prism.language.core import CoreType


@dataclass(frozen=True, slots=True)
class MaterialPolicyContract:
    name: str
    evidence: CoreType
    proposition: CoreType
    error: CoreType
    effects: tuple[str, ...] = ()
