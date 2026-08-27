# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Typed specs for externally imported skill sets cataloged alongside PRISM agents."""

from __future__ import annotations

# Platform-only capability schemas.
import shlex
from pathlib import Path
from typing import Any, Literal

from prism.platform.specs.agent_contracts import CapabilityContractSpec
from pydantic import BaseModel, ConfigDict, Field


class ImportedBackendProfileSpec(BaseModel):
    """One backend or runtime dependency exposed by an imported skill."""

    model_config = ConfigDict(extra="forbid")

    backend_id: str
    kind: Literal["llm", "theorem-prover", "script-runner", "library-index", "hybrid"]
    target: str
    invocation_hint: str = ""
    notes: str = ""


class ImportedAssetSpec(BaseModel):
    """One preserved asset copied from the upstream skill set."""

    model_config = ConfigDict(extra="forbid")

    relative_path: str
    asset_kind: Literal["skill_doc", "script", "reference", "agent_config"]
    description: str


class ImportedWorkspaceMountSpec(BaseModel):
    """Typed execution mount expected by one imported runtime."""

    model_config = ConfigDict(extra="forbid")

    mount_id: str
    mount_kind: Literal[
        "problem-workspace", "library-clone-set", "project-subtree", "workspace-root"
    ]
    root_strategy: Literal[
        "problem-context-parent", "kb-parent", "local-root", "project-root"
    ]
    required_relative_paths: list[str] = Field(default_factory=list)
    ensure_relative_dirs: list[str] = Field(default_factory=list)
    writable: bool = False
    notes: str = ""


class ImportedRuntimeArgumentSpec(BaseModel):
    """One normalized argument binding for an imported local runtime adapter."""

    model_config = ConfigDict(extra="forbid")

    flag: str
    source_kind: Literal[
        "problem_context",
        "supporting_artifact",
        "task_config",
        "runtime_config",
        "generated",
        "fixed",
        "input_binding",
    ]
    source_key: str | None = None
    value: str | None = None
    required: bool = True
    repeatable: bool = False


class ImportedRuntimeAdapterSpec(BaseModel):
    """Structured local-runtime adapter for one imported skill."""

    model_config = ConfigDict(extra="forbid")

    adapter_kind: Literal[
        "python-script",
        "python-module",
        "python-function",
        "prompt-contract",
        "hybrid-workflow",
    ]
    workdir: str
    script_path: str | None = None
    module: str | None = None
    function_name: str | None = None
    entry_subcommand: list[str] = Field(default_factory=list)
    prompt_asset_path: str | None = None
    pythonpath: list[str] = Field(default_factory=list)
    argv: list[ImportedRuntimeArgumentSpec] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    workspace_mounts: list[ImportedWorkspaceMountSpec] = Field(default_factory=list)
    route_registry_path: str | None = None
    capability_source_paths: list[str] = Field(default_factory=list)
    reasoning_log_mode: Literal["normalized", "upstream", "normalized+upstream"] = (
        "normalized+upstream"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImportedSkillSpec(BaseModel):
    """Catalog record for one imported external skill set."""

    model_config = ConfigDict(extra="forbid")

    import_id: str
    version: str
    name: str
    description: str
    source_project: str
    source_archive: str
    source_skill_path: str
    local_root: str
    semantic_folder: str
    semantic_tags: list[str] = Field(default_factory=list)
    reference_kb_ids: list[str] = Field(default_factory=list)
    runtime_dependencies: list[str] = Field(default_factory=list)
    backend_profiles: list[ImportedBackendProfileSpec] = Field(default_factory=list)
    preserved_assets: list[ImportedAssetSpec] = Field(default_factory=list)
    capability_contract: CapabilityContractSpec
    runtime_adapter: ImportedRuntimeAdapterSpec | None = None

    def resolved_local_root(
        self, *, install_root: Path | None = None, project_root: Path | None = None
    ) -> Path:
        """Resolve the preserved imported runtime root inside the PRISM installation tree."""
        root = Path(self.local_root)
        if root.is_absolute():
            return root
        install_base = self._resolve_install_root(
            install_root=install_root, project_root=project_root
        )
        return (install_base / root).resolve()

    def normalized_runtime_adapter(
        self,
        *,
        install_root: Path | None = None,
        project_root: Path | None = None,
    ) -> ImportedRuntimeAdapterSpec:
        """Return the explicit or inferred imported-runtime adapter."""
        if self.runtime_adapter is not None:
            return self.runtime_adapter

        install_base = self._resolve_install_root(
            install_root=install_root, project_root=project_root
        )
        local_root = self.resolved_local_root(install_root=install_base)
        primary_entrypoint = (
            self.capability_contract.invocation.primary_entrypoint or ""
        )
        execution_entrypoint = (
            self.capability_contract.invocation.execution_entrypoint or ""
        )
        prompt_asset_path = self._prompt_asset_path(
            local_root=local_root,
            install_root=install_base,
            primary_entrypoint=primary_entrypoint,
        )
        workspace_mounts = self._default_workspace_mounts()
        route_registry_path = self._route_registry_path(local_root)
        capability_sources = self._capability_source_paths(local_root)

        # The first harmonized AlgebraicJulia path uses the preserved local Python
        # surface directly, then writes a PRISM-managed solver-program artifact.
        if self.source_project == "AlgebraicJulia Agent" and self.import_id in {
            "algebraicjulia-yaml-program",
            "algebraicjulia-categorical-solver",
        }:
            return ImportedRuntimeAdapterSpec(
                adapter_kind="python-function",
                workdir=str(local_root),
                module="algebraicjulia_agent.nl_solver",
                function_name="solve_nl_request",
                prompt_asset_path=prompt_asset_path,
                pythonpath=[str(local_root / "src")],
                workspace_mounts=workspace_mounts,
                route_registry_path=route_registry_path,
                capability_source_paths=capability_sources,
                metadata={
                    "function_adapter": self.import_id,
                    "result_writer": "solver-program-yaml",
                },
            )

        if execution_entrypoint:
            adapter = self._adapter_from_execution_entrypoint(
                execution_entrypoint=execution_entrypoint,
                local_root=local_root,
                install_root=install_base,
                prompt_asset_path=prompt_asset_path,
                workspace_mounts=workspace_mounts,
                route_registry_path=route_registry_path,
                capability_sources=capability_sources,
            )
            if adapter is not None:
                return adapter

        return ImportedRuntimeAdapterSpec(
            adapter_kind="prompt-contract",
            workdir=str(local_root),
            prompt_asset_path=prompt_asset_path,
            workspace_mounts=workspace_mounts,
            route_registry_path=route_registry_path,
            capability_source_paths=capability_sources,
            metadata={"function_adapter": "prompt-normalization"},
        )

    def _adapter_from_execution_entrypoint(
        self,
        *,
        execution_entrypoint: str,
        local_root: Path,
        install_root: Path,
        prompt_asset_path: str | None,
        workspace_mounts: list[ImportedWorkspaceMountSpec],
        route_registry_path: str | None,
        capability_sources: list[str],
    ) -> ImportedRuntimeAdapterSpec | None:
        tokens = shlex.split(execution_entrypoint, posix=True)
        if not tokens:
            return None

        python_invokers = {"python", "python3", "py", "python.exe"}
        if Path(tokens[0]).name.lower() not in python_invokers:
            return None

        script_path: str | None = None
        module: str | None = None
        entry_subcommand: list[str] = []
        pythonpath: list[str] = []

        remainder = tokens[1:]
        if len(remainder) >= 2 and remainder[0] == "-m":
            module = remainder[1]
            entry_subcommand = remainder[2:]
        elif remainder:
            candidate = Path(remainder[0])
            if not candidate.is_absolute():
                candidate = install_root / candidate
            script_path = str(candidate.resolve())
            entry_subcommand = remainder[1:]
        else:
            return None

        adapter_kind: Literal[
            "python-script",
            "python-module",
            "python-function",
            "prompt-contract",
            "hybrid-workflow",
        ]
        adapter_kind = "python-module" if module is not None else "python-script"
        metadata: dict[str, Any] = {}
        argv: list[ImportedRuntimeArgumentSpec] = []

        if self.source_project == "AlgebraicJulia Agent":
            pythonpath = [str(local_root / "src")]

        if self.source_project == "Adaptive Symbolic Reasoning":
            metadata["script_adapter"] = "adaptive_symbolic_reasoning"
            argv = self._adaptive_symbolic_argv(import_id=self.import_id)

        if self.source_project == "Paper Drafting":
            metadata["script_adapter"] = "paper_drafting"
            argv = self._paper_drafting_argv(import_id=self.import_id)

        if self.import_id == "abducer-kb-entrypoint-finder":
            metadata["script_adapter"] = "abducer_kb_entrypoint_finder"
            argv = [
                ImportedRuntimeArgumentSpec(
                    flag="--kb", source_kind="problem_context", required=True
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--concept",
                    source_kind="supporting_artifact",
                    source_key="concept_evolution",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--analysis",
                    source_kind="supporting_artifact",
                    source_key="connector_analysis",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--phyp",
                    source_kind="supporting_artifact",
                    source_key="proof_hypotheses",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--coherence-report",
                    source_kind="supporting_artifact",
                    source_key="coherence_report",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--output-json",
                    source_kind="generated",
                    source_key="primary_output_json",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--output-md",
                    source_kind="generated",
                    source_key="primary_output_markdown",
                    required=True,
                ),
            ]

        return ImportedRuntimeAdapterSpec(
            adapter_kind=adapter_kind,
            workdir=str(local_root),
            script_path=script_path,
            module=module,
            entry_subcommand=entry_subcommand,
            prompt_asset_path=prompt_asset_path,
            pythonpath=pythonpath,
            argv=argv,
            workspace_mounts=workspace_mounts,
            route_registry_path=route_registry_path,
            capability_source_paths=capability_sources,
            metadata=metadata,
        )

    def _paper_drafting_argv(
        self, *, import_id: str
    ) -> list[ImportedRuntimeArgumentSpec]:
        common = [
            ImportedRuntimeArgumentSpec(
                flag="--primary-output-json",
                source_kind="generated",
                source_key="primary_output_json",
                required=True,
            ),
        ]
        if import_id in {
            "systematic-review-bootstrap",
            "systematic-review-synthesis",
            "paper-contribution-box",
        }:
            return [
                ImportedRuntimeArgumentSpec(
                    flag="--problem-context",
                    source_kind="problem_context",
                    required=True,
                ),
                *common,
            ]
        return common

    def _adaptive_symbolic_argv(
        self, *, import_id: str
    ) -> list[ImportedRuntimeArgumentSpec]:
        common_runtime = [
            ImportedRuntimeArgumentSpec(
                flag="--model-path",
                source_kind="runtime_config",
                source_key="model_path",
                required=True,
            ),
            ImportedRuntimeArgumentSpec(
                flag="--model-key",
                source_kind="runtime_config",
                source_key="model_key",
                required=False,
            ),
            ImportedRuntimeArgumentSpec(
                flag="--huggingface-api-key",
                source_kind="runtime_config",
                source_key="huggingface_api_key",
                required=False,
            ),
            ImportedRuntimeArgumentSpec(
                flag="--lora-path",
                source_kind="runtime_config",
                source_key="lora_path",
                required=False,
            ),
            ImportedRuntimeArgumentSpec(
                flag="--config-path",
                source_kind="runtime_config",
                source_key="config_path",
                required=False,
            ),
        ]
        if import_id == "adaptive-symbolic-router-planner":
            return [
                *common_runtime,
                ImportedRuntimeArgumentSpec(
                    flag="--problem",
                    source_kind="input_binding",
                    source_key="problem_record.problem",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--output-path",
                    source_kind="generated",
                    source_key="primary_output_json",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--minizinc-path",
                    source_kind="runtime_config",
                    source_key="minizinc_path",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--prover9-path",
                    source_kind="runtime_config",
                    source_key="prover9_path",
                    required=False,
                ),
            ]
        if import_id in {"adaptive-symbolic-fol-solver", "adaptive-symbolic-lp-solver"}:
            stage_specific: list[ImportedRuntimeArgumentSpec] = [
                ImportedRuntimeArgumentSpec(
                    flag="--premise",
                    source_kind="input_binding",
                    source_key="reasoning_case.premise",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--hypothesis",
                    source_kind="input_binding",
                    source_key="reasoning_case.hypothesis",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--explanation",
                    source_kind="input_binding",
                    source_key="reasoning_case.explanation",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--option",
                    source_kind="input_binding",
                    source_key="reasoning_case.options",
                    required=False,
                    repeatable=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--output-path",
                    source_kind="generated",
                    source_key="primary_output_json",
                    required=True,
                ),
            ]
            if import_id == "adaptive-symbolic-fol-solver":
                stage_specific.append(
                    ImportedRuntimeArgumentSpec(
                        flag="--prover9-path",
                        source_kind="runtime_config",
                        source_key="prover9_path",
                        required=False,
                    )
                )
            return [*common_runtime, *stage_specific]
        if import_id in {
            "adaptive-symbolic-csp-solver",
            "adaptive-symbolic-smt-solver",
            "adaptive-symbolic-ilp-solver",
        }:
            stage_specific = [
                ImportedRuntimeArgumentSpec(
                    flag="--problem",
                    source_kind="input_binding",
                    source_key="problem_record.problem",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--output-path",
                    source_kind="generated",
                    source_key="primary_output_json",
                    required=True,
                ),
            ]
            if import_id == "adaptive-symbolic-csp-solver":
                stage_specific.append(
                    ImportedRuntimeArgumentSpec(
                        flag="--minizinc-path",
                        source_kind="runtime_config",
                        source_key="minizinc_path",
                        required=False,
                    )
                )
            if import_id == "adaptive-symbolic-ilp-solver":
                stage_specific.append(
                    ImportedRuntimeArgumentSpec(
                        flag="--popper-path",
                        source_kind="runtime_config",
                        source_key="popper_path",
                        required=False,
                    )
                )
            return [*common_runtime, *stage_specific]
        if import_id == "adaptive-symbolic-orchestrator":
            return [
                *common_runtime,
                ImportedRuntimeArgumentSpec(
                    flag="--problem",
                    source_kind="input_binding",
                    source_key="problem_record.problem",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--dataset-file",
                    source_kind="input_binding",
                    source_key="dataset_file.href",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--summary-path",
                    source_kind="generated",
                    source_key="primary_output_json",
                    required=True,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--minizinc-path",
                    source_kind="runtime_config",
                    source_key="minizinc_path",
                    required=False,
                ),
                ImportedRuntimeArgumentSpec(
                    flag="--prover9-path",
                    source_kind="runtime_config",
                    source_key="prover9_path",
                    required=False,
                ),
            ]
        return []

    def _prompt_asset_path(
        self,
        *,
        local_root: Path,
        install_root: Path,
        primary_entrypoint: str,
    ) -> str | None:
        if primary_entrypoint:
            candidate = Path(primary_entrypoint)
            if not candidate.is_absolute():
                candidate = install_root / candidate
            if candidate.exists():
                return str(candidate.resolve())
        for asset in self.preserved_assets:
            if asset.asset_kind != "skill_doc":
                continue
            candidate = (local_root / asset.relative_path).resolve()
            if candidate.exists():
                return str(candidate)
        fallback = local_root / "SKILL.md"
        return str(fallback.resolve()) if fallback.exists() else None

    def _default_workspace_mounts(self) -> list[ImportedWorkspaceMountSpec]:
        mounts: list[ImportedWorkspaceMountSpec] = []
        if self.source_project == "Abducer":
            mounts.append(
                ImportedWorkspaceMountSpec(
                    mount_id="abducer-problem-workspace",
                    mount_kind="problem-workspace",
                    root_strategy="kb-parent",
                    required_relative_paths=["KB"],
                    ensure_relative_dirs=["artifacts", "phyp", "MathLib"],
                    writable=True,
                    notes="Persistent KB/artifact workspace expected by the preserved Abducer scripts.",
                )
            )
        if self.source_project == "AlgebraicJulia Agent":
            mounts.append(
                ImportedWorkspaceMountSpec(
                    mount_id="algebraicjulia-clone-set",
                    mount_kind="library-clone-set",
                    root_strategy="project-root",
                    required_relative_paths=["upstream"],
                    ensure_relative_dirs=[],
                    writable=False,
                    notes="Workspace-level AlgebraicJulia clone set used for routing and capability checks.",
                )
            )
        mounts.append(
            ImportedWorkspaceMountSpec(
                mount_id="imported-runtime-root",
                mount_kind="project-subtree",
                root_strategy="local-root",
                required_relative_paths=[],
                ensure_relative_dirs=[],
                writable=False,
                notes="Preserved imported runtime subtree kept intact inside PRISM.",
            )
        )
        return mounts

    def _route_registry_path(self, local_root: Path) -> str | None:
        if self.source_project != "AlgebraicJulia Agent":
            return None
        candidate = local_root / "ALGEBRAICJULIA_NL_ROUTES.yaml"
        return str(candidate.resolve()) if candidate.exists() else None

    def _capability_source_paths(self, local_root: Path) -> list[str]:
        if self.source_project != "AlgebraicJulia Agent":
            return []
        candidates = [
            local_root / "src" / "algebraicjulia_agent" / "surfaces.py",
            local_root / "src" / "algebraicjulia_agent" / "governance.py",
        ]
        return [str(path.resolve()) for path in candidates if path.exists()]

    def _resolve_install_root(
        self, *, install_root: Path | None, project_root: Path | None
    ) -> Path:
        candidates: list[Path] = []
        for raw in [install_root, project_root, Path(__file__).resolve().parents[3]]:
            if raw is None:
                continue
            candidate = Path(raw).resolve()
            if candidate not in candidates:
                candidates.append(candidate)

        relative_root = Path(self.local_root)
        if relative_root.is_absolute():
            return relative_root
        for base in candidates:
            if (base / relative_root).exists():
                return base
        return candidates[-1]
