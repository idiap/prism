# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Static assurance checks for material inference."""

from __future__ import annotations

from prism.language.core import CoreType

from .policies import MaterialPolicyContract


class MaterialInferenceError(ValueError):
    pass


def check_material_inference(
    evidence: CoreType,
    proposition: CoreType,
    policy: MaterialPolicyContract,
) -> CoreType:
    if evidence.name != "Evidence":
        raise MaterialInferenceError("left side of `|~` must be Evidence")
    expected_payload = (
        policy.evidence.arguments[0]
        if policy.evidence.name == "Evidence" and policy.evidence.arguments
        else policy.evidence
    )
    actual_payload = evidence.arguments[0] if evidence.arguments else CoreType("Any")
    if not expected_payload.is_assignable_from(actual_payload):
        raise MaterialInferenceError(
            f"material evidence payload expects {expected_payload.render()}, "
            f"got {actual_payload.render()}"
        )
    proposition_matches = policy.proposition.is_assignable_from(proposition) or (
        policy.proposition.name == "Prop"
        and (proposition.name == "Prop" or "(" in proposition.name)
    )
    if not proposition_matches:
        raise MaterialInferenceError(
            f"material proposition expects {policy.proposition.render()}, "
            f"got {proposition.render()}"
        )
    return CoreType("Result", (CoreType("Supported", (proposition,)), policy.error))
