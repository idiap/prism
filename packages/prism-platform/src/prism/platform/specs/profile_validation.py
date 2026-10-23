# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Validate skill profile ports, confidence, checks, and dependencies."""

from __future__ import annotations

from prism.platform.specs.agent_contracts import (
    CapabilityContractSpec,
)
from prism.platform.specs.semantic_types import semantic_type_compatible
from prism.platform.specs.skill_contract_profiles import resolve_skill_contract_profile
from prism.platform.specs.skill_specs import SkillSpec


def _ensure_skill_contract_profile_alignment(
    *, skill_spec: SkillSpec, contract: CapabilityContractSpec
) -> None:
    """Validate the explicit-or-derived contract profile against the typed contract.

    The profile is an overlay, so the checks here focus on consistency rather than
    total completeness. We want enough structure to catch drift without making the
    migration brittle.
    """

    profile = resolve_skill_contract_profile(skill_spec)
    input_ports = {port.port_id: port for port in contract.inputs}
    output_ports = {port.port_id: port for port in contract.outputs}

    _ensure_profile_ports(skill_spec, profile, input_ports, output_ports)
    confidence_policy = profile.confidence_policy
    if (
        confidence_policy.required
        and confidence_policy.confidence_field
        not in skill_spec.output_schema.get("required", [])
    ):
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} requires confidence field "
            f"`{confidence_policy.confidence_field}` but does not declare it in the output schema"
        )
    if confidence_policy.required and confidence_policy.allow_absent_when_deterministic:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} cannot require confidence while also allowing it "
            "to be absent for deterministic execution"
        )

    known_critics = set(skill_spec.critic_spec_ids)
    for check in [*profile.validators, *profile.evaluators]:
        if not check.check_id.strip():
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares an empty validator or evaluator id"
            )
        if check.kind == "critic" and check.check_id not in known_critics:
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} references critic `{check.check_id}` in the "
                "skill contract profile, but that critic is not listed in `critic_spec_ids`"
            )

    _ensure_unique_dependency_refs(
        label=f"Skill spec {skill_spec.spec_id}@{skill_spec.version} upstream dependency list",
        refs=[item.ref_id for item in profile.upstream_dependencies],
    )
    _ensure_unique_dependency_refs(
        label=f"Skill spec {skill_spec.spec_id}@{skill_spec.version} downstream dependency list",
        refs=[item.ref_id for item in profile.downstream_dependencies],
    )


def _ensure_unique_dependency_refs(*, label: str, refs: list[str]) -> None:
    normalized = [item.strip() for item in refs if item.strip()]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} contains duplicate references: {sorted(normalized)}")


def _ensure_profile_ports(skill_spec, profile, input_ports, output_ports) -> None:
    for evidence in profile.input_evidence_types:
        port = input_ports.get(evidence.port_id)
        if port is None:
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares input evidence for unknown port "
                f"`{evidence.port_id}`"
            )
        for declared_type in evidence.semantic_types:
            if semantic_type_compatible(port.semantic_type, declared_type):
                continue
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares incompatible evidence type on "
                f"port `{evidence.port_id}`"
            )

    if profile.output_contract is not None:
        output = output_ports.get(profile.output_contract.port_id)
        if output is None:
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares output contract for unknown port "
                f"`{profile.output_contract.port_id}`"
            )
        required_fields = set(skill_spec.output_schema.get("required", []))
        declared_required = set(profile.output_contract.required_fields)
        missing = required_fields.difference(declared_required)
        if missing:
            raise ValueError(
                f"Skill spec {skill_spec.spec_id}@{skill_spec.version} omits required output fields from the "
                f"skill contract profile: {sorted(missing)}"
            )
