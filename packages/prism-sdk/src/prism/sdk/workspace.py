# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Workspace and installed-package discovery exposed by the Prism SDK."""

from __future__ import annotations

import base64
import json
import logging
import os
from importlib import metadata, resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

import yaml
from prism.language.core import ModuleLoader, ModuleSource
from prism.language.interop import ResourceReference

logger = logging.getLogger(__name__)


def resolve_project_root(
    document_path: Path | None = None, *, fallback: Path | None = None
) -> Path:
    """Resolve the Prism project root for a source document or process."""

    configured = os.environ.get("PRISM_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if document_path is not None:
        resolved = document_path.expanduser().resolve()
        directory = resolved if resolved.is_dir() else resolved.parent
        candidates = (directory, *directory.parents)
        for candidate in candidates:
            runtime_path = candidate / "runtime.json"
            if not runtime_path.is_file():
                continue
            try:
                runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            workspace = runtime.get("workspace") if isinstance(runtime, dict) else None
            if isinstance(workspace, str) and workspace.strip():
                return (candidate / workspace).expanduser().resolve()
        for candidate in candidates:
            if candidate.name == ".prism":
                return candidate.parent
    return (fallback or Path.cwd()).expanduser().resolve()


class WorkspaceModuleLoader(ModuleLoader):
    """Load Prism source modules from explicit roots and installed entry points."""

    def __init__(
        self,
        *,
        project_root: Path,
        search_paths: tuple[Path, ...] = (),
        entry_points: bool = True,
    ) -> None:
        self.project_root = project_root.resolve()
        self.search_paths = tuple(path.resolve() for path in search_paths)
        self.entry_point_roots = self._entry_point_roots() if entry_points else {}

    def load_module(self, name: str) -> ModuleSource:
        relative = Path(*name.split("."))
        if name.startswith("prism.reasoning."):
            relative = Path("libs", "prism", *name.split(".")[1:])
        for root in self._roots():
            for candidate in (
                root / relative.with_suffix(".prism"),
                root / relative / "__init__.prism",
            ):
                if candidate.is_file():
                    return ModuleSource(
                        name=name,
                        source=candidate.read_text(encoding="utf-8"),
                        origin=str(candidate),
                    )
        packaged = self._package_source(name)
        if packaged is not None:
            return packaged
        raise ValueError(f"unknown Prism module `{name}`")

    def iter_workspace_modules(self) -> list[str]:
        modules: list[str] = []
        libs = self.project_root / "libs"
        if not libs.is_dir():
            return modules
        source_paths = (
            *libs.glob("*/functions/**/*.prism"),
            *libs.glob("*/reasoning/**/*.prism"),
            *libs.glob("*/tactics/**/*.prism"),
        )
        for path in sorted(source_paths):
            rel = path.relative_to(self.project_root)
            parts = (
                rel.parent.parts
                if path.name == "__init__.prism"
                else rel.with_suffix("").parts
            )
            if parts[:3] == ("libs", "prism", "reasoning"):
                parts = parts[1:]
            modules.append(".".join(parts))
        return modules

    def _roots(self) -> tuple[Path, ...]:
        candidates = (
            self.project_root,
            self.project_root / "src",
            self.project_root / ".prism",
            *self.search_paths,
            *self.entry_point_roots.values(),
        )
        return tuple(dict.fromkeys(path.resolve() for path in candidates))

    def _entry_point_roots(self) -> dict[str, Path]:
        roots: dict[str, Path] = {}
        try:
            entries = metadata.entry_points(group="prism.modules")
        except Exception:
            return roots
        for entry in entries:
            try:
                value = entry.load()
                loaded: Any = value() if callable(value) else value
                if not isinstance(loaded, str | Path):
                    continue
                roots[entry.name] = Path(loaded).resolve()
            except Exception:
                logger.debug(
                    "Ignoring Prism module entry point that failed to load",
                    exc_info=True,
                )
                continue
        return roots

    def _package_source(self, name: str) -> ModuleSource | None:
        parts = name.split(".")
        for split_at in range(len(parts), 0, -1):
            package_name = ".".join(parts[:split_at])
            try:
                root = resources.files(package_name)
            except (ModuleNotFoundError, TypeError, OSError):
                continue
            candidate = _resource_candidate(root, parts[split_at:])
            if candidate is not None:
                return ModuleSource(
                    name=name,
                    source=candidate.read_text(encoding="utf-8"),
                    origin=str(candidate),
                )
        return None


class LocalResourceResolver:
    """Resolve local workspace and installed-package resources without network access."""

    def __init__(
        self, project_root: Path, *, search_paths: tuple[Path, ...] = ()
    ) -> None:
        self.project_root = project_root.resolve()
        self.search_paths = tuple(path.resolve() for path in search_paths)

    def resolve(
        self, reference: ResourceReference | str, type_name: str | None = None
    ) -> Any:
        if isinstance(reference, str):
            reference = ResourceReference(reference, type_name or "Any")
        if "://" in reference.locator:
            raise ValueError(
                f"network resource locators are not supported: `{reference.locator}`"
            )
        relative = Path(reference.locator)
        if relative.is_absolute():
            raise ValueError(
                f"resource locator must be relative: `{reference.locator}`"
            )
        roots = (self.project_root, *self.search_paths, *_installed_module_roots())
        for root in roots:
            candidate = (root / relative).resolve()
            if candidate.is_relative_to(root.resolve()) and candidate.is_file():
                payload = candidate.read_bytes()
                try:
                    return payload.decode("utf-8")
                except UnicodeDecodeError:
                    return {
                        "encoding": "base64",
                        "data": base64.b64encode(payload).decode("ascii"),
                    }
        raise ValueError(f"resource not found: `{reference.locator}`")


def _installed_module_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    try:
        entries = metadata.entry_points(group="prism.modules")
    except Exception:
        return ()
    for entry in entries:
        try:
            value = entry.load()
            loaded: Any = value() if callable(value) else value
            if not isinstance(loaded, str | Path):
                continue
            root = Path(loaded).resolve()
        except Exception:
            logger.debug(
                "Ignoring Prism module entry point that failed to load",
                exc_info=True,
            )
            continue
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def load_workspace_knowledge(project_root: Path):
    """Load stable knowledge-source configuration and built-in typed adapters."""

    from prism.runtime.knowledge import (
        KnowledgeBroker,
        KnowledgeSourceConfig,
        KnowledgeTrustProfile,
        default_knowledge_registry,
    )

    root = project_root.resolve()
    path = root / ".prism" / "kbs.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    raw_sources = payload.get("sources", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw_sources, dict):
        raise ValueError(
            f"knowledge configuration `{path}` must contain a `sources` mapping"
        )
    sources = {}
    for source_id, raw in raw_sources.items():
        if (
            not isinstance(raw, dict)
            or not isinstance(raw.get("adapter"), str)
            or not isinstance(raw.get("locator"), str)
        ):
            raise ValueError(
                f"knowledge source `{source_id}` must declare string `adapter` and `locator` fields"
            )
        raw_trust = raw.get("trust", {})
        if not isinstance(raw_trust, dict):
            raise ValueError(
                f"knowledge source `{source_id}` trust profile must be a mapping"
            )
        trust = KnowledgeTrustProfile(
            allow_offline_snapshot=bool(raw_trust.get("allow_offline_snapshot", True)),
        )
        sources[str(source_id)] = KnowledgeSourceConfig(
            source_id=str(source_id),
            adapter_id=raw["adapter"],
            locator=raw["locator"],
            schema_id=raw.get("schema"),
            options=dict(raw.get("options", {})),
            trust=trust,
        )
    registry = default_knowledge_registry(root)
    try:
        adapter_entries = metadata.entry_points(group="prism.knowledge_adapters")
    except Exception:
        adapter_entries = ()
    for entry in adapter_entries:
        loaded = entry.load()
        adapter = loaded() if isinstance(loaded, type) else loaded
        registry.register(adapter)
    return KnowledgeBroker(registry, sources, project_root=root)


def _resource_candidate(root: Traversable, parts: list[str]) -> Traversable | None:
    if parts:
        file_candidate = root.joinpath(*parts[:-1]).joinpath(f"{parts[-1]}.prism")
        package_candidate = root.joinpath(*parts).joinpath("__init__.prism")
    else:
        file_candidate = root.joinpath("__init__.prism")
        package_candidate = file_candidate
    for candidate in (file_candidate, package_candidate):
        if candidate.is_file():
            return candidate
    return None
