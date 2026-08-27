# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Validation helpers for typed agent coordination contracts."""

from __future__ import annotations

# Platform-only capability schemas.
from typing import TYPE_CHECKING

from prism.platform.specs.agent_contracts import (
    AgentContractSpec,
    CapabilityContractSpec,
    critic_agent_id,
    resolve_critic_agent_contract,
    resolve_environment_agent_contract,
    resolve_skill_capability_contract,
)
from prism.platform.specs.aggregator_specs import AggregatorSpec
from prism.platform.specs.critic_specs import CriticSpec
from prism.platform.specs.environment_agent_specs import EnvironmentAgentSpec
from prism.platform.specs.imported_skillset_specs import ImportedSkillSpec
from prism.platform.specs.semantic_types import semantic_type_compatible
from prism.platform.specs.skill_contract_profiles import resolve_skill_contract_profile
from prism.platform.specs.skill_specs import SkillSpec

if TYPE_CHECKING:
    from prism.platform.specs.capability_index import CapabilityIndex


def ensure_required_output_fields(skill_spec: SkillSpec) -> None:
    """Ensure skill contract-required fields are declared in the output schema."""
    required = set(skill_spec.contract.get("required_fields", []))
    declared = set(skill_spec.output_schema.get("required", []))
    missing = required.difference(declared)
    if missing:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} requires undeclared output fields: {sorted(missing)}"
        )


def ensure_skill_capability_contract(skill_spec: SkillSpec) -> None:
    """Validate the normalized exported capability contract for one skill."""
    contract = resolve_skill_capability_contract(skill_spec)
    _ensure_contract_shape(
        contract=contract, label=f"skill spec {skill_spec.spec_id}@{skill_spec.version}"
    )
    if contract.invocation.mode not in {"planner-routed", "manual"}:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} must use a planner-routed or manual invocation mode, "
            f"not `{contract.invocation.mode}`"
        )
    analysis_output = _find_output(
        contract=contract, port_id="analysis_artifact", label=skill_spec.spec_id
    )
    declared = set(skill_spec.output_schema.get("required", []))
    contract_required = set(analysis_output.json_schema.get("required", []))
    missing = declared.difference(contract_required)
    if missing:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares required output fields missing from the "
            f"typed contract: {sorted(missing)}"
        )
    if skill_spec.spec_id in contract.coordination.companion_capability_ids:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} cannot list itself as a companion skill"
        )
    _ensure_skill_type_alignment(skill_spec=skill_spec, contract=contract)
    _ensure_skill_contract_profile_alignment(skill_spec=skill_spec, contract=contract)


def ensure_aggregator_spec(aggregator_spec: AggregatorSpec) -> None:
    """Validate a typed aggregator policy before it enters the live capability index."""
    source_ids = [
        item.source_id.strip()
        for item in aggregator_spec.inputs
        if item.source_id.strip()
    ]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError(
            f"Aggregator spec {aggregator_spec.spec_id}@{aggregator_spec.version} declares duplicate input sources"
        )
    if aggregator_spec.policy.mode == "arbitrate":
        judge_policy = aggregator_spec.policy.judge_policy
        if judge_policy is None or not judge_policy.judge_ids:
            raise ValueError(
                f"Aggregator spec {aggregator_spec.spec_id}@{aggregator_spec.version} uses `arbitrate` mode "
                "without any configured judge ids"
            )
    if aggregator_spec.policy.contradiction_resolution == "prefer-judge":
        judge_policy = aggregator_spec.policy.judge_policy
        if judge_policy is None or not judge_policy.judge_ids:
            raise ValueError(
                f"Aggregator spec {aggregator_spec.spec_id}@{aggregator_spec.version} prefers a judge-based "
                "contradiction policy but does not declare a judge policy"
            )


def ensure_environment_agent_contract(agent_spec: EnvironmentAgentSpec) -> None:
    """Validate the normalized coordination contract for one maintenance agent."""
    contract = resolve_environment_agent_contract(agent_spec)
    _ensure_contract_shape(
        contract=contract,
        label=f"environment agent {agent_spec.agent_id}@{agent_spec.version}",
    )
    if contract.invocation.mode not in {
        "task-hook",
        "task-threshold",
        "macro-task-threshold",
    }:
        raise ValueError(
            f"Environment agent {agent_spec.agent_id}@{agent_spec.version} must use a task or macro-task trigger mode, "
            f"not `{contract.invocation.mode}`"
        )
    output_port_ids = {port.port_id for port in contract.outputs}
    if "reasoning_log" not in output_port_ids:
        raise ValueError(
            f"Environment agent {agent_spec.agent_id}@{agent_spec.version} must emit a reasoning_log sidecar"
        )


def ensure_critic_agent_contract(critic_spec: CriticSpec) -> None:
    """Validate the normalized coordination contract for one critic agent."""
    contract = resolve_critic_agent_contract(critic_spec)
    _ensure_contract_shape(
        contract=contract,
        label=f"critic spec {critic_spec.spec_id}@{critic_spec.version}",
    )
    solver_success = "solver-success-evaluation" in critic_spec.target_kinds
    expected_mode = "scenario-evaluation" if solver_success else "task-hook"
    if contract.invocation.mode != expected_mode:
        raise ValueError(
            f"Critic spec {critic_spec.spec_id}@{critic_spec.version} must use invocation mode `{expected_mode}`, "
            f"not `{contract.invocation.mode}`"
        )
    decision_output = _find_output(
        contract=contract,
        port_id="critic_verdict" if solver_success else "critic_decision",
        label=critic_spec.spec_id,
    )
    declared = set(critic_spec.decision_schema.get("required", []))
    contract_required = set(decision_output.json_schema.get("required", []))
    missing = declared.difference(contract_required)
    if missing:
        raise ValueError(
            f"Critic spec {critic_spec.spec_id}@{critic_spec.version} declares decision fields missing from the "
            f"typed contract: {sorted(missing)}"
        )


def ensure_capability_agent_coherence(registry: CapabilityIndex) -> None:
    """Validate skill-capability and agent coordination references separately."""
    known_agent_ids = {
        *registry.environment_agents.keys(),
        *(critic_agent_id(critic_id) for critic_id in registry.critics),
    }
    known_skill_ids = {*registry.skills, *registry.imported_skills}
    for skill in registry.skills.values():
        _ensure_companion_capabilities(
            label=f"skill spec {skill.spec_id}@{skill.version}",
            companion_capability_ids=resolve_skill_capability_contract(
                skill
            ).coordination.companion_capability_ids,
            known_skill_ids=known_skill_ids,
        )
        _ensure_profile_dependencies_exist(
            label=f"skill spec {skill.spec_id}@{skill.version}",
            skill_spec=skill,
            registry=registry,
        )
    for agent in registry.environment_agents.values():
        _ensure_companions_exist(
            label=f"environment agent {agent.agent_id}@{agent.version}",
            companion_agent_ids=resolve_environment_agent_contract(
                agent
            ).coordination.companion_agent_ids,
            known_agent_ids=known_agent_ids,
        )
    for critic in registry.critics.values():
        _ensure_companions_exist(
            label=f"critic spec {critic.spec_id}@{critic.version}",
            companion_agent_ids=resolve_critic_agent_contract(
                critic
            ).coordination.companion_agent_ids,
            known_agent_ids=known_agent_ids,
        )
    for imported in registry.imported_skills.values():
        ensure_imported_skill_contract(imported)
        _ensure_companion_capabilities(
            label=f"imported skill {imported.import_id}@{imported.version}",
            companion_capability_ids=imported.capability_contract.coordination.companion_capability_ids,
            known_skill_ids=known_skill_ids,
        )


def ensure_imported_skill_contract(imported_spec: ImportedSkillSpec) -> None:
    """Validate the typed coordination contract for one imported skill."""
    contract = imported_spec.capability_contract
    _ensure_contract_shape(
        contract=contract,
        label=f"imported skill {imported_spec.import_id}@{imported_spec.version}",
    )
    if contract.invocation.mode != "manual":
        raise ValueError(
            f"Imported skill {imported_spec.import_id}@{imported_spec.version} must use manual invocation mode, "
            f"not `{contract.invocation.mode}`"
        )


def _ensure_contract_shape(
    *, contract: AgentContractSpec | CapabilityContractSpec, label: str
) -> None:
    if not contract.inputs:
        raise ValueError(f"{label} declares no typed inputs")
    if not contract.outputs:
        raise ValueError(f"{label} declares no typed outputs")
    if not contract.invocation.invocation_condition.strip():
        raise ValueError(f"{label} has an empty invocation condition")
    if not contract.coordination.organization_group.strip():
        raise ValueError(f"{label} has an empty organization group")
    if not contract.reasoning_log.default_root.strip():
        raise ValueError(f"{label} has an empty reasoning-log root")
    if not contract.reasoning_log.required_sections:
        raise ValueError(f"{label} has no required reasoning-log sections")
    reasoning_log_ports = [
        port for port in contract.outputs if port.payload_kind == "reasoning-log"
    ]
    if not reasoning_log_ports:
        raise ValueError(f"{label} must expose a reasoning-log output port")


def _find_output(
    *, contract: AgentContractSpec | CapabilityContractSpec, port_id: str, label: str
):
    for port in contract.outputs:
        if port.port_id == port_id:
            return port
    raise ValueError(
        f"Typed contract for `{label}` is missing required output port `{port_id}`"
    )


def _ensure_companions_exist(
    *, label: str, companion_agent_ids: list[str], known_agent_ids: set[str]
) -> None:
    normalized = [item.strip() for item in companion_agent_ids if item.strip()]
    if len(normalized) != len(set(normalized)):
        raise ValueError(
            f"{label} lists duplicate companion agents: {sorted(normalized)}"
        )
    # Companion links are advisory coordination hints rather than hard dependencies.
    # Partial registries are allowed to omit optional companion agents.


def _ensure_companion_capabilities(
    *, label: str, companion_capability_ids: list[str], known_skill_ids: set[str]
) -> None:
    normalized = [item.strip() for item in companion_capability_ids if item.strip()]
    if len(normalized) != len(set(normalized)):
        raise ValueError(
            f"{label} lists duplicate companion skills: {sorted(normalized)}"
        )
    # Companion capabilities remain advisory; partial domain registries may omit them.


def _ensure_skill_type_alignment(
    *, skill_spec: SkillSpec, contract: CapabilityContractSpec
) -> None:
    skill_type = skill_spec.skill_type
    if skill_type is None:
        return
    input_port_ids = {port.port_id for port in contract.inputs}
    output_port_ids = {port.port_id for port in contract.outputs}
    unknown_inputs = sorted(set(skill_type.input_types).difference(input_port_ids))
    unknown_outputs = sorted(set(skill_type.output_types).difference(output_port_ids))
    if unknown_inputs:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares semantic input types for unknown ports: "
            f"{unknown_inputs}"
        )
    if unknown_outputs:
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares semantic output types for unknown ports: "
            f"{unknown_outputs}"
        )
    for port in contract.inputs:
        expected = skill_type.input_types.get(port.port_id)
        if expected is None or semantic_type_compatible(port.semantic_type, expected):
            continue
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares incompatible semantic type for input "
            f"port `{port.port_id}`"
        )
    for port in contract.outputs:
        expected = skill_type.output_types.get(port.port_id)
        if expected is None or semantic_type_compatible(port.semantic_type, expected):
            continue
        raise ValueError(
            f"Skill spec {skill_spec.spec_id}@{skill_spec.version} declares incompatible semantic type for output "
            f"port `{port.port_id}`"
        )


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


def _ensure_profile_dependencies_exist(
    *, label: str, skill_spec: SkillSpec, registry: CapabilityIndex
) -> None:
    profile = resolve_skill_contract_profile(skill_spec)
    for dependency in [
        *profile.upstream_dependencies,
        *profile.downstream_dependencies,
    ]:
        ref_id = dependency.ref_id.strip()
        if not ref_id:
            continue
        if dependency.kind == "skill" and ref_id not in registry.skills:
            raise ValueError(f"{label} references unknown skill dependency `{ref_id}`")
        if dependency.kind == "critic" and ref_id not in registry.critics:
            raise ValueError(f"{label} references unknown critic dependency `{ref_id}`")
        if dependency.kind == "aggregator" and ref_id not in registry.aggregators:
            raise ValueError(
                f"{label} references unknown aggregator dependency `{ref_id}`"
            )
        if (
            dependency.kind == "environment-agent"
            and ref_id not in registry.environment_agents
        ):
            raise ValueError(
                f"{label} references unknown environment-agent dependency `{ref_id}`"
            )
