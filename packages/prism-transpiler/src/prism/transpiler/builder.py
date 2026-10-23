# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Build external skills and native hook configurations into typed Prism modules."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from prism.language import check, parse_source
from prism.language.core import ModuleLoader

from .discovery import (
    DiscoveredSkill,
    discover_skills,
    load_configuration,
    parse_frontmatter,
)
from .validation import _CLAUDE_ALL_HANDLER_EVENTS as _CLAUDE_ALL_HANDLER_EVENTS
from .validation import _CLAUDE_EVENTS as _CLAUDE_EVENTS
from .validation import _CLAUDE_NO_MATCHER_EVENTS as _CLAUDE_NO_MATCHER_EVENTS
from .validation import _CODEX_EVENTS as _CODEX_EVENTS
from .validation import _CODEX_MATCHER_EVENTS as _CODEX_MATCHER_EVENTS
from .validation import _SKILL_FIELDS as _SKILL_FIELDS
from .validation import _TOOL_EVENTS as _TOOL_EVENTS
from .validation import BuildError as BuildError
from .validation import HookProvider as HookProvider
from .validation import _validate_hook_handler as _validate_hook_handler
from .validation import _validate_hooks as _validate_hooks
from .validation import _validate_skill_manifest as _validate_skill_manifest


@dataclass(frozen=True, slots=True)
class BuiltModule:
    path: Path
    export: str
    type: str


def build_skill_module(
    source: str | Path,
    contract: str,
    output: str | Path,
    *,
    modules: ModuleLoader | None = None,
) -> BuiltModule:
    source_path = Path(source).resolve()
    instruction = source_path / "SKILL.md" if source_path.is_dir() else source_path
    if instruction.name != "SKILL.md" or not instruction.is_file():
        raise BuildError(
            "an Open Agent Skill source must be a SKILL.md file or its directory"
        )
    try:
        metadata, _ = parse_frontmatter(instruction.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError) as exc:
        raise BuildError(f"invalid Open Agent Skill manifest: {exc}") from exc
    _validate_skill_manifest(metadata, instruction.parent.name)
    discovered = discover_skills(source_path)
    if len(discovered) != 1:
        raise BuildError("skill build requires exactly one Open Agent Skill")
    module_name, separator, task_type = contract.rpartition(".")
    if not separator or not _qualified_name(module_name) or not _identifier(task_type):
        raise BuildError(
            "--contract must be a qualified Prism type such as review.ReviewTask"
        )
    skill = discovered[0]
    unsupported = list(skill.obligations)
    if unsupported:
        details = "; ".join(f"{item.element}: {item.details}" for item in unsupported)
        raise BuildError(f"skill contains untyped or unsupported content: {details}")
    export = _snake_identifier(skill.skill_id) + "_skill"
    bundle = _skill_bundle(skill)
    text = "\n".join(
        (
            f"from {module_name} import {task_type}",
            "",
            f"{export}: Skill[{task_type}] = skill_artifact[{task_type}](",
            f"    {_string(skill.skill_id)},",
            f"    {_string(skill.version)},",
            f"    {_string(skill.name)},",
            f"    {_string(skill.description)},",
            f"    {_string(skill.instructions)},",
            f"    {_string(bundle)},",
            ")",
            "",
        )
    )
    path = _module_path(output)
    try:
        check(parse_source(text, path=str(path)), modules=modules)
    except Exception as exc:
        raise BuildError(f"generated skill module does not type-check: {exc}") from exc
    _write_module(path, text)
    return BuiltModule(path, export, f"Skill[{task_type}]")


def build_hooks_module(
    provider: HookProvider,
    source: str | Path,
    output: str | Path,
) -> BuiltModule:
    if provider not in {"codex", "claude"}:
        raise BuildError("hook provider must be codex or claude")
    source_path = Path(source).resolve()
    configurations = _hook_configurations(source_path)
    if len(configurations) != 1:
        raise BuildError(
            "hooks build requires exactly one native configuration containing `hooks`"
        )
    configuration_path, configuration = configurations[0]
    if "description" in configuration and not isinstance(
        configuration["description"], str
    ):
        raise BuildError("native hook `description` must be a string")
    native_hooks = configuration.get("hooks")
    _validate_hooks(provider, native_hooks)
    provider_type = provider.capitalize()
    export = f"{provider}_hooks"
    payload_value: dict[str, object] = {"hooks": native_hooks}
    if isinstance(configuration.get("description"), str):
        payload_value["description"] = configuration["description"]
    payload = json.dumps(payload_value, sort_keys=True, separators=(",", ":"))
    text = "\n".join(
        (
            f"{export}: Hooks[{provider_type}] = hooks_artifact[{provider_type}](",
            f"    {_string(payload)},",
            ")",
            "",
        )
    )
    path = _module_path(output)
    try:
        check(parse_source(text, path=str(path)))
    except Exception as exc:
        raise BuildError(f"generated hooks module does not type-check: {exc}") from exc
    _write_module(path, text)
    return BuiltModule(path, export, f"Hooks[{provider_type}]")


def _hook_configurations(source: Path) -> list[tuple[Path, dict[str, object]]]:
    candidates = (source,) if source.is_file() else tuple(sorted(source.rglob("*")))
    found: list[tuple[Path, dict[str, object]]] = []
    for path in candidates:
        if not path.is_file() or path.suffix.lower() not in {
            ".json",
            ".toml",
            ".yaml",
            ".yml",
        }:
            continue
        value = load_configuration(path)
        if isinstance(value, dict) and "hooks" in value:
            found.append((path, value))
    return found


def _skill_bundle(skill: DiscoveredSkill) -> str:
    root = skill.root
    resources = {
        path.relative_to(root).as_posix(): base64.b64encode(path.read_bytes()).decode(
            "ascii"
        )
        for path in skill.source_files
        if path != skill.instruction_file
    }
    return json.dumps(resources, sort_keys=True, separators=(",", ":"))


def _module_path(output: str | Path) -> Path:
    path = Path(output)
    if path.suffix != ".prism":
        path = path.with_suffix(".prism")
    return path.resolve()


def _write_module(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _identifier(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z_]\w*", value) is not None


def _qualified_name(value: str) -> bool:
    return bool(value) and all(_identifier(item) for item in value.split("."))


def _snake_identifier(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "skill"
    return f"skill_{result}" if result[0].isdigit() else result


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


__all__ = [
    "BuildError",
    "BuiltModule",
    "HookProvider",
    "build_hooks_module",
    "build_skill_module",
]
