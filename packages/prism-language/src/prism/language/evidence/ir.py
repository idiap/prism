# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Evidence and material-policy execution IR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MaterialInference:
    evidence: Any
    policy: str
    proposition: Any
    target: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceTransformation:
    target: str
    inputs: tuple[Any, ...]
    transformation: str
