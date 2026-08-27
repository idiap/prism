# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Capability loading and typed lookup helpers for all PRISM specs."""

from __future__ import annotations

# Platform-only capability schemas.
from pathlib import Path
from typing import Literal, Sequence, TypeVar

from prism.platform.libraries import PrismLibraryManifest, iter_project_libraries
from prism.platform.specs.agent_contracts import (
    AgentContractSpec,
    CapabilityContractSpec,
    critic_agent_id,
    resolve_critic_agent_contract,
    resolve_environment_agent_contract,
    resolve_skill_capability_contract,
)
from prism.platform.specs.aggregator_specs import AggregatorSpec
from prism.platform.specs.compatibility import (
    ensure_aggregator_spec,
    ensure_capability_agent_coherence,
    ensure_critic_agent_contract,
    ensure_environment_agent_contract,
    ensure_imported_skill_contract,
    ensure_required_output_fields,
    ensure_skill_capability_contract,
)
from prism.platform.specs.critic_specs import CriticSpec
from prism.platform.specs.environment_agent_specs import EnvironmentAgentSpec
from prism.platform.specs.imported_skillset_specs import ImportedSkillSpec
from prism.platform.specs.loaders import iter_yaml_files, load_yaml
from prism.platform.specs.parser_specs import ParserSpec
from prism.platform.specs.reference_kb_specs import ReferenceKBSpec
from prism.platform.specs.scheme_specs import SchemeSpec
from prism.platform.specs.semantic_types import (
    PortCompatibilityIssue,
    SkillCompositionReport,
    SkillTypeSpec,
    semantic_type_compatible,
)
from prism.platform.specs.skill_contract_profiles import (
    SkillContractProfileSpec,
    resolve_skill_contract_profile,
)
from prism.platform.specs.skill_specs import SkillSpec
from prism.platform.specs.skill_summaries import (
    imported_skill_summary,
    native_skill_summary,
)
from prism.platform.specs.tactic_bindings import CapabilityTacticBinding
from pydantic import BaseModel, ConfigDict, Field


class ResolvedAgentRef(BaseModel):
    """Normalized description of a resolved agent identifier."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_kind: Literal[
        "solver-success-critic",
        "environment-maintenance",
        "planner",
        "diagrammatic-workflow",
    ]
    name: str
    spec_id: str | None = None
    workflow_diagram: str | None = None


class ResolvedSkillRef(BaseModel):
    """Summary-only reference to a skill, separate from agent identity."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    version: str
    capability_type: str
    content_hash: str
    source_ecosystem: str


class CapabilityIndex(BaseModel):
    """In-memory index of loaded skills, critics, tactics, schemes, and agents."""

    model_config = ConfigDict(extra="forbid")

    skills: dict[str, SkillSpec] = Field(default_factory=dict)
    critics: dict[str, CriticSpec] = Field(default_factory=dict)
    tactics: dict[str, CapabilityTacticBinding] = Field(default_factory=dict)
    schemes: dict[str, SchemeSpec] = Field(default_factory=dict)
    aggregators: dict[str, AggregatorSpec] = Field(default_factory=dict)
    parsers: dict[str, ParserSpec] = Field(default_factory=dict)
    environment_agents: dict[str, EnvironmentAgentSpec] = Field(default_factory=dict)
    imported_skills: dict[str, ImportedSkillSpec] = Field(default_factory=dict)
    reference_kbs: dict[str, ReferenceKBSpec] = Field(default_factory=dict)

    @classmethod
    def load(cls, root: str | Path) -> "CapabilityIndex":
        """Load and validate one explicit capability root."""
        index = cls()
        cls._load_root_into(index, Path(root).resolve())
        ensure_capability_agent_coherence(index)
        return index

    @classmethod
    def load_many(cls, roots: Sequence[str | Path]) -> "CapabilityIndex":
        """Load and merge multiple explicit capability roots."""
        index = cls()
        for root in roots:
            cls._load_root_into(index, Path(root).resolve())
        ensure_capability_agent_coherence(index)
        return index

    @classmethod
    def load_project(
        cls, project_root: str | Path, domains: list[str] | None = None
    ) -> "CapabilityIndex":
        """Load capabilities from root-level `libs/*` manifests."""
        selected = set(domains) if domains is not None else None
        roots: list[Path] = []
        for manifest in iter_project_libraries(Path(project_root), domains=selected):
            roots.extend(manifest.resolve_roots(manifest.capability_roots))
        return cls.load_many(roots)

    @classmethod
    def _load_root_into(cls, index: "CapabilityIndex", base: Path) -> None:
        if (base / "library.yaml").is_file():
            manifest = PrismLibraryManifest.load(base / "library.yaml")
            for root in manifest.resolve_roots(manifest.capability_roots):
                if root == base:
                    cls._load_explicit_tree_into(index, root)
                else:
                    cls._load_root_into(index, root)
            return
        cls._load_explicit_tree_into(index, base)

    @classmethod
    def _load_explicit_tree_into(cls, index: "CapabilityIndex", base: Path) -> None:
        for path in iter_yaml_files(base / "skills"):
            skill = SkillSpec.model_validate(load_yaml(path))
            ensure_required_output_fields(skill)
            ensure_skill_capability_contract(skill)
            _put_unique(index.skills, skill.spec_id, skill, path)
        for skill in index.skills.values():
            tactic_id = _derived_tactic_id(skill)
            if tactic_id not in index.tactics:
                index.tactics[tactic_id] = _derived_tactic_from_skill(skill)
        for path in iter_yaml_files(base / "critics"):
            critic = CriticSpec.model_validate(load_yaml(path))
            ensure_critic_agent_contract(critic)
            _put_unique(index.critics, critic.spec_id, critic, path)
        for path in iter_yaml_files(base / "schemes"):
            scheme = SchemeSpec.model_validate(load_yaml(path))
            _put_unique(index.schemes, scheme.scheme_id, scheme, path)
        for path in iter_yaml_files(base / "aggregators"):
            aggregator = AggregatorSpec.model_validate(load_yaml(path))
            ensure_aggregator_spec(aggregator)
            _put_unique(index.aggregators, aggregator.spec_id, aggregator, path)
        for path in iter_yaml_files(base / "parsers"):
            parser = ParserSpec.model_validate(load_yaml(path))
            _put_unique(index.parsers, parser.spec_id, parser, path)
        for path in iter_yaml_files(base / "environment_agents"):
            agent = EnvironmentAgentSpec.model_validate(load_yaml(path))
            ensure_environment_agent_contract(agent)
            _put_unique(index.environment_agents, agent.agent_id, agent, path)
        for path in iter_yaml_files(base / "imported_skillsets"):
            imported = ImportedSkillSpec.model_validate(load_yaml(path))
            ensure_imported_skill_contract(imported)
            _put_unique(index.imported_skills, imported.import_id, imported, path)
        for path in iter_yaml_files(base / "reference_kbs"):
            reference_kb = ReferenceKBSpec.model_validate(load_yaml(path))
            _put_unique(index.reference_kbs, reference_kb.kb_id, reference_kb, path)

    def skill(self, spec_id: str) -> SkillSpec:
        """Return a skill spec by identifier."""
        return self.skills[spec_id]

    def skill_capability_contract(self, spec_id: str) -> CapabilityContractSpec:
        """Return the typed exported capability contract for a skill spec."""
        return resolve_skill_capability_contract(self.skill(spec_id))

    def skill_type_spec(self, spec_id: str) -> SkillTypeSpec | None:
        """Return the optional semantic/effect type spec for a skill."""
        return self.skill(spec_id).skill_type

    def skill_contract_profile(self, spec_id: str) -> SkillContractProfileSpec:
        """Return the explicit or derived contract profile for a skill."""
        return resolve_skill_contract_profile(self.skill(spec_id))

    def critic(self, spec_id: str) -> CriticSpec:
        """Return a critic spec by identifier."""
        return self.critics[spec_id]

    def critic_agent_contract(self, spec_id: str) -> AgentContractSpec:
        """Return the normalized agent contract for a critic spec."""
        return resolve_critic_agent_contract(self.critic(spec_id))

    def scheme(self, scheme_id: str) -> SchemeSpec:
        """Return a scheme spec by identifier."""
        return self.schemes[scheme_id]

    def tactic_for_objective(
        self, objective_kind: str
    ) -> CapabilityTacticBinding | None:
        """Return the first tactic registered for the requested objective kind."""
        for tactic in self.tactics.values():
            for skill_id in tactic.skills:
                skill = self.skills.get(skill_id)
                if skill is not None and objective_kind in skill.objective_kinds:
                    return tactic
        return None

    def environment_agent(self, agent_id: str) -> EnvironmentAgentSpec:
        """Return an environment-maintenance agent by identifier."""
        return self.environment_agents[agent_id]

    def environment_agent_contract(self, agent_id: str) -> AgentContractSpec:
        """Return the normalized agent contract for an environment agent."""
        return resolve_environment_agent_contract(self.environment_agent(agent_id))

    def imported_skill(self, import_id: str) -> ImportedSkillSpec:
        """Return an imported-skill spec by import identifier."""
        return self.imported_skills[import_id]

    def has_imported_skill(self, import_id: str) -> bool:
        """Return whether the capability index contains the requested imported-skill id."""
        return import_id in self.imported_skills

    def imported_skill_contract(self, import_id: str) -> CapabilityContractSpec:
        """Return the typed exported capability contract for an imported skill."""
        return self.imported_skill(import_id).capability_contract

    def reference_kb(self, kb_id: str) -> ReferenceKBSpec:
        """Return a reference KB spec by identifier."""
        return self.reference_kbs[kb_id]

    def skill_contract_for_spec(self, spec_id: str) -> CapabilityContractSpec:
        """Return the typed contract for either a native or imported skill."""
        if spec_id in self.skills:
            return self.skill_capability_contract(spec_id)
        if spec_id in self.imported_skills:
            return self.imported_skill_contract(spec_id)
        raise KeyError(spec_id)

    def spec_version(self, spec_id: str) -> str:
        """Return the version string for either a native or imported executable spec."""
        if spec_id in self.skills:
            return self.skill(spec_id).version
        if spec_id in self.imported_skills:
            return self.imported_skill(spec_id).version
        raise KeyError(spec_id)

    def spec_name(self, spec_id: str) -> str:
        """Return the display name for either a native or imported executable spec."""
        if spec_id in self.skills:
            return self.skill(spec_id).name
        if spec_id in self.imported_skills:
            return self.imported_skill(spec_id).name
        raise KeyError(spec_id)

    def all_agent_ids(self) -> list[str]:
        """Return every agent id exposed through the loaded capability surface."""
        return [
            "planner",
            *sorted(self.environment_agents),
            *[critic_agent_id(critic_id) for critic_id in sorted(self.critics)],
        ]

    def all_skill_ids(self) -> list[str]:
        """Return native and imported skill ids without manufacturing agent ids."""

        return [*sorted(self.skills), *sorted(self.imported_skills)]

    def resolve_skill(self, skill_id: str) -> ResolvedSkillRef:
        """Resolve a skill through its canonical summary, never as an agent."""

        if skill_id in self.skills:
            summary = native_skill_summary(self.skill(skill_id))
        elif skill_id in self.imported_skills:
            summary = imported_skill_summary(self.imported_skill(skill_id))
        else:
            raise KeyError(skill_id)
        return ResolvedSkillRef(
            skill_id=summary.skill_id,
            name=summary.name,
            version=summary.version,
            capability_type=summary.capability_type,
            content_hash=summary.content_hash,
            source_ecosystem=summary.source_ecosystem,
        )

    def assess_skill_composition(
        self, upstream_skill_id: str, downstream_skill_id: str
    ) -> SkillCompositionReport:
        """Assess whether one skill's outputs can feed another skill's typed inputs."""
        upstream = self.skill_capability_contract(upstream_skill_id)
        downstream = self.skill_capability_contract(downstream_skill_id)
        report = SkillCompositionReport(
            upstream_skill_id=upstream_skill_id,
            downstream_skill_id=downstream_skill_id,
        )
        downstream_inputs = {port.port_id: port for port in downstream.inputs}
        candidate_outputs = [
            port
            for port in upstream.outputs
            if port.port_id != "reasoning_log" and port.transport != "sidecar"
        ]
        for port_id, downstream_port in downstream_inputs.items():
            if (
                port_id in {"objective_context", "context_artifacts"}
                or not downstream_port.required
            ):
                continue
            matched = next(
                (
                    upstream_port
                    for upstream_port in candidate_outputs
                    if semantic_type_compatible(
                        upstream_port.semantic_type, downstream_port.semantic_type
                    )
                ),
                None,
            )
            if matched is not None:
                continue
            if downstream_port.semantic_type is None:
                report.notes.append(
                    f"Downstream port `{port_id}` does not declare a semantic type, so composition remains permissive."
                )
                continue
            report.compatible = False
            report.issues.append(
                PortCompatibilityIssue(
                    upstream_port_id="*",
                    downstream_port_id=port_id,
                    reason=(
                        "No upstream output advertises a compatible semantic type for "
                        f"`{downstream_port.semantic_type.type_id}`."
                    ),
                )
            )
        upstream_skill_type = self.skill_type_spec(upstream_skill_id)
        downstream_skill_type = self.skill_type_spec(downstream_skill_id)
        upstream_effects = upstream_skill_type.effects if upstream_skill_type else None
        downstream_effects = (
            downstream_skill_type.effects if downstream_skill_type else None
        )
        if (
            upstream_effects
            and downstream_effects
            and upstream_effects.parallel_safe
            and downstream_effects.requires_ordering
        ):
            report.notes.append(
                "The upstream skill is parallel-safe, but the downstream skill requests ordered execution. "
                "Compose them through an explicit dependency edge."
            )
        if not report.notes and report.compatible:
            report.notes.append(
                "Typed composition is admissible under the currently declared semantic contracts."
            )
        return report

    def compatible_downstream_skills(self, upstream_skill_id: str) -> list[str]:
        """Return downstream skills whose declared inputs remain compatible with the given skill."""
        compatible: list[str] = []
        for downstream_skill_id in sorted(self.skills):
            if downstream_skill_id == upstream_skill_id:
                continue
            if self.assess_skill_composition(
                upstream_skill_id, downstream_skill_id
            ).compatible:
                compatible.append(downstream_skill_id)
        return compatible

    def resolve_agent(self, agent_id: str) -> ResolvedAgentRef:
        """Resolve any supported agent id into a normalized agent reference."""
        if agent_id == "planner":
            return ResolvedAgentRef(
                agent_id="planner", agent_kind="planner", name="Planner"
            )
        if agent_id in self.environment_agents:
            agent = self.environment_agent(agent_id)
            return ResolvedAgentRef(
                agent_id=agent.agent_id,
                agent_kind="environment-maintenance",
                name=agent.name,
                spec_id=agent.agent_id,
            )
        if agent_id in self.critics:
            critic = self.critic(agent_id)
            return ResolvedAgentRef(
                agent_id=critic_agent_id(critic.spec_id),
                agent_kind="solver-success-critic",
                name=critic.name,
                spec_id=critic.spec_id,
            )
        for critic_id, critic in self.critics.items():
            if critic_agent_id(critic_id) == agent_id:
                return ResolvedAgentRef(
                    agent_id=agent_id,
                    agent_kind="solver-success-critic",
                    name=critic.name,
                    spec_id=critic_id,
                )
        raise KeyError(agent_id)


def _derived_tactic_from_skill(skill: SkillSpec) -> CapabilityTacticBinding:
    behavior = skill.tactic
    return CapabilityTacticBinding(
        version=skill.version,
        name=f"{skill.name} Tactic",
        skills=[skill.spec_id],
        preconditions=list(behavior.preconditions),
        expansion_rule=dict(behavior.expansion_rule),
        stopping_rule=dict(behavior.stopping_rule),
    )


def _derived_tactic_id(skill: SkillSpec) -> str:
    return f"{skill.spec_id}-tactic"


CapabilityValue = TypeVar("CapabilityValue")


def _put_unique(
    target: dict[str, CapabilityValue],
    key: str,
    value: CapabilityValue,
    path: Path,
) -> None:
    if key in target:
        raise ValueError(f"Duplicate capability id `{key}` while loading `{path}`.")
    target[key] = value
