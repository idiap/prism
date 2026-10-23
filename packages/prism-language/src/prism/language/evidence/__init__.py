# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 5: evidence and material inference."""

from .checking import MaterialInferenceError, check_material_inference
from .ir import EvidenceTransformation, MaterialInference
from .model import (
    Assessment,
    Evidence,
    PolicyDecision,
    Provenance,
    Supported,
)
from .policies import MaterialPolicyContract

__all__ = [
    "Assessment",
    "PolicyDecision",
    "Evidence",
    "EvidenceTransformation",
    "MaterialInference",
    "MaterialInferenceError",
    "MaterialPolicyContract",
    "Provenance",
    "Supported",
    "check_material_inference",
]
