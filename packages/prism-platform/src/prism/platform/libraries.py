# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Platform manifest and runtime-provider helpers for Prism libraries."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from prism.platform.project_layout import PrismProjectLayout
from prism.platform.specs.loaders import load_yaml


@dataclass(frozen=True, slots=True)
class PrismLibraryManifest:
    """Loaded `libs/<domain>/library.yaml` descriptor."""

    root: Path
    domain: str
    package: str
    python_module: str
    capability_roots: tuple[str, ...] = field(default_factory=tuple)
    module_roots: tuple[str, ...] = field(default_factory=tuple)
    workflow_roots: tuple[str, ...] = field(default_factory=tuple)
    reference_kb_roots: tuple[str, ...] = field(default_factory=tuple)
    runtime_provider: str | None = None

    @classmethod
    def load(cls, path: Path) -> "PrismLibraryManifest":
        """Load and validate one library manifest."""
        payload = load_yaml(path)
        return cls(
            root=path.parent.resolve(),
            domain=str(payload["domain"]),
            package=str(payload["package"]),
            python_module=str(payload["python_module"]),
            capability_roots=tuple(
                str(item) for item in payload.get("capability_roots", [])
            ),
            module_roots=tuple(str(item) for item in payload.get("module_roots", [])),
            workflow_roots=tuple(
                str(item) for item in payload.get("workflow_roots", [])
            ),
            reference_kb_roots=tuple(
                str(item) for item in payload.get("reference_kb_roots", [])
            ),
            runtime_provider=(
                str(payload["runtime_provider"])
                if payload.get("runtime_provider")
                else None
            ),
        )

    def resolve_roots(self, entries: tuple[str, ...]) -> list[Path]:
        """Resolve relative root entries against this library root."""
        roots: list[Path] = []
        for entry in entries:
            root = (self.root / entry).resolve()
            if root not in roots:
                roots.append(root)
        return roots


def iter_project_libraries(
    project_root: Path, *, domains: set[str] | None = None
) -> list[PrismLibraryManifest]:
    """Load project library manifests in deterministic order."""
    layout = PrismProjectLayout(project_root)
    manifests: list[PrismLibraryManifest] = []
    for path in layout.iter_library_manifests():
        manifest = PrismLibraryManifest.load(path)
        if domains is not None and manifest.domain not in domains:
            continue
        manifests.append(manifest)
    return manifests


class LibraryRuntimeRegistry:
    """Runtime provider registry loaded from `libs/*/library.yaml` manifests."""

    def __init__(self, *, manifests: list[PrismLibraryManifest]) -> None:
        self.manifests = manifests
        self._providers: dict[str, Any] | None = None

    @classmethod
    def load(
        cls, project_root: Path, *, domains: list[str] | None = None
    ) -> "LibraryRuntimeRegistry":
        """Load runtime providers from a project root."""
        selected = set(domains) if domains is not None else None
        return cls(manifests=iter_project_libraries(project_root, domains=selected))

    def providers(self) -> dict[str, Any]:
        """Return loaded runtime provider objects keyed by domain."""
        if self._providers is not None:
            return self._providers
        providers: dict[str, Any] = {}
        for manifest in self.manifests:
            if not manifest.runtime_provider:
                continue
            providers[manifest.domain] = _load_provider(manifest.runtime_provider)
        self._providers = providers
        return providers

    def tool_registry(self, *, project_root: Path) -> dict[str, Callable[..., Any]]:
        """Merge workflow tool registrations exposed by library providers."""
        tools: dict[str, Callable[..., Any]] = {}
        for provider in self.providers().values():
            hook = getattr(provider, "tool_registry", None)
            if hook is None:
                continue
            for name, callable_obj in hook(project_root=project_root).items():
                if name in tools:
                    raise ValueError(f"Duplicate workflow tool registration `{name}`.")
                tools[name] = callable_obj
        return tools

    def first_hook(self, hook_name: str) -> Callable[..., Any]:
        """Return the first provider hook with the requested name."""
        for provider in self.providers().values():
            hook = getattr(provider, hook_name, None)
            if hook is not None:
                return hook
        raise ValueError(f"No library runtime provider exposes `{hook_name}`.")


def _load_provider(provider_ref: str) -> Any:
    module_name, sep, attr_name = provider_ref.partition(":")
    if not sep or not module_name or not attr_name:
        raise ValueError(f"Invalid runtime provider reference `{provider_ref}`.")
    module = import_module(module_name)
    provider = getattr(module, attr_name)
    return provider() if callable(provider) else provider
