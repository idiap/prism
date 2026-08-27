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
from typing import Literal

import yaml
from prism.language import check, parse_source
from prism.language.core import ModuleLoader

from .discovery import (
    DiscoveredSkill,
    discover_skills,
    load_configuration,
    parse_frontmatter,
)

HookProvider = Literal["codex", "claude"]

_SKILL_FIELDS = frozenset(
    {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
)
_CODEX_EVENTS = frozenset(
    {
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PreCompact",
        "PostCompact",
        "UserPromptSubmit",
        "SubagentStop",
        "Stop",
        "SessionStart",
        "SubagentStart",
        "SessionEnd",
    }
)
_CLAUDE_EVENTS = frozenset(
    {
        "SessionStart",
        "Setup",
        "InstructionsLoaded",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "MessageDisplay",
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "PermissionDenied",
        "Notification",
        "SubagentStart",
        "SubagentStop",
        "TaskCreated",
        "TaskCompleted",
        "Stop",
        "StopFailure",
        "TeammateIdle",
        "ConfigChange",
        "CwdChanged",
        "DirectoryAdded",
        "FileChanged",
        "WorktreeCreate",
        "WorktreeRemove",
        "PreCompact",
        "PostCompact",
        "SessionEnd",
        "Elicitation",
        "ElicitationResult",
    }
)
_CLAUDE_ALL_HANDLER_EVENTS = frozenset(
    {
        "PermissionDenied",
        "PermissionRequest",
        "PostToolBatch",
        "PostToolUse",
        "PostToolUseFailure",
        "PreToolUse",
        "Stop",
        "SubagentStop",
        "TaskCompleted",
        "TaskCreated",
        "TeammateIdle",
        "UserPromptExpansion",
        "UserPromptSubmit",
    }
)
_CLAUDE_NO_MATCHER_EVENTS = frozenset(
    {
        "UserPromptSubmit",
        "PostToolBatch",
        "Stop",
        "TeammateIdle",
        "TaskCreated",
        "TaskCompleted",
        "WorktreeCreate",
        "WorktreeRemove",
        "MessageDisplay",
    }
)
_TOOL_EVENTS = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "PermissionRequest",
        "PermissionDenied",
    }
)
_CODEX_MATCHER_EVENTS = frozenset(
    {
        "PermissionRequest",
        "PostToolUse",
        "PostCompact",
        "PreCompact",
        "PreToolUse",
        "SessionEnd",
    }
)


class BuildError(ValueError):
    """The external artifact cannot be represented by a complete typed module."""


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


def _validate_skill_manifest(metadata: dict[str, object], directory_name: str) -> None:
    if not metadata:
        raise BuildError("SKILL.md must start with YAML frontmatter")
    unknown = sorted(set(metadata) - _SKILL_FIELDS)
    if unknown:
        raise BuildError("unsupported Open Agent Skill fields: " + ", ".join(unknown))
    name = metadata.get("name")
    if (
        not isinstance(name, str)
        or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None
    ):
        raise BuildError(
            "skill `name` must use 1-64 lowercase letters, numbers, and hyphens"
        )
    if len(name) > 64:
        raise BuildError("skill `name` must contain at most 64 characters")
    if name != directory_name:
        raise BuildError("skill `name` must match the directory containing SKILL.md")
    description = metadata.get("description")
    if not isinstance(description, str) or not description or len(description) > 1024:
        raise BuildError("skill `description` must contain 1-1024 characters")
    compatibility = metadata.get("compatibility")
    if compatibility is not None and (
        not isinstance(compatibility, str)
        or not compatibility
        or len(compatibility) > 500
    ):
        raise BuildError("skill `compatibility` must contain 1-500 characters")
    for field in ("license", "allowed-tools"):
        value = metadata.get(field)
        if value is not None and not isinstance(value, str):
            raise BuildError(f"skill `{field}` must be a string")
    extra = metadata.get("metadata")
    if extra is not None and (
        not isinstance(extra, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in extra.items()
        )
    ):
        raise BuildError("skill `metadata` must map strings to strings")


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


def _validate_hooks(provider: HookProvider, value: object) -> None:
    if not isinstance(value, dict) or not value:
        raise BuildError("native `hooks` must be a non-empty event mapping")
    events = _CODEX_EVENTS if provider == "codex" else _CLAUDE_EVENTS
    for event, raw_groups in value.items():
        if event not in events:
            raise BuildError(f"unsupported {provider} hook event `{event}`")
        if not isinstance(raw_groups, list) or not raw_groups:
            raise BuildError(f"hook event `{event}` must contain matcher groups")
        for group_index, group in enumerate(raw_groups, 1):
            if not isinstance(group, dict) or set(group) - {"matcher", "hooks"}:
                raise BuildError(
                    f"hook event `{event}` group {group_index} has unsupported fields"
                )
            matcher = group.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise BuildError(f"hook event `{event}` matcher must be a string")
            if (
                provider == "claude"
                and event in _CLAUDE_NO_MATCHER_EVENTS
                and matcher is not None
            ):
                raise BuildError(
                    f"Claude hook event `{event}` does not support a matcher"
                )
            if (
                provider == "codex"
                and event not in _CODEX_MATCHER_EVENTS
                and matcher is not None
            ):
                raise BuildError(
                    f"Codex hook event `{event}` does not support a matcher"
                )
            handlers = group.get("hooks")
            if not isinstance(handlers, list) or not handlers:
                raise BuildError(
                    f"hook event `{event}` group {group_index} has no handlers"
                )
            for handler_index, handler in enumerate(handlers, 1):
                _validate_hook_handler(provider, event, handler, handler_index)


def _validate_hook_handler(
    provider: HookProvider, event: str, value: object, index: int
) -> None:
    if not isinstance(value, dict):
        raise BuildError(f"hook event `{event}` handler {index} must be an object")
    kind = value.get("type")
    kinds = (
        {"command"}
        if provider == "codex"
        else {"command", "http", "mcp_tool", "prompt", "agent"}
    )
    if kind not in kinds:
        raise BuildError(f"unsupported {provider} hook handler type `{kind}`")
    if provider == "claude":
        if event in {"SessionStart", "Setup"} and kind not in {"command", "mcp_tool"}:
            raise BuildError(
                f"Claude hook event `{event}` does not support `{kind}` handlers"
            )
        if kind in {"prompt", "agent"} and event not in _CLAUDE_ALL_HANDLER_EVENTS:
            raise BuildError(
                f"Claude hook event `{event}` does not support `{kind}` handlers"
            )
    if provider == "claude" and "if" in value and event not in _TOOL_EVENTS:
        raise BuildError(f"hook event `{event}` does not support handler `if`")
    if "once" in value:
        raise BuildError("`once` is valid only in Claude skill-frontmatter hooks")
    common = {"type", "timeout", "statusMessage"}
    if provider == "claude":
        common.update({"if", "once"})
    specific = {
        "command": (
            {
                "command",
                "commandWindows",
                "command_windows",
                "additionalContextLimit",
                "async",
            }
            if provider == "codex"
            else {"command", "args", "async", "asyncRewake", "shell"}
        ),
        "http": {"url", "headers", "allowedEnvVars"},
        "mcp_tool": {"server", "tool", "input"},
        "prompt": {"prompt", "model", "continueOnBlock"},
        "agent": {"prompt", "model", "continueOnBlock"},
    }[str(kind)]
    unknown = sorted(set(value) - common - specific)
    if unknown:
        raise BuildError(
            f"hook event `{event}` handler {index} has unsupported fields: "
            + ", ".join(unknown)
        )
    required = {
        "command": ("command",),
        "http": ("url",),
        "mcp_tool": ("server", "tool"),
        "prompt": ("prompt",),
        "agent": ("prompt",),
    }[str(kind)]
    if any(
        not isinstance(value.get(field), str) or not value[field] for field in required
    ):
        raise BuildError(
            f"hook event `{event}` handler {index} is missing typed fields"
        )
    timeout = value.get("timeout")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, int | float)
        or timeout <= 0
    ):
        raise BuildError(
            f"hook event `{event}` handler {index} timeout must be positive"
        )
    for field in (
        "if",
        "statusMessage",
        "commandWindows",
        "command_windows",
        "shell",
        "model",
    ):
        if field in value and not isinstance(value[field], str):
            raise BuildError(f"hook handler field `{field}` must be a string")
    for field in ("async", "asyncRewake", "continueOnBlock"):
        if field in value and not isinstance(value[field], bool):
            raise BuildError(f"hook handler field `{field}` must be a boolean")
    if provider == "codex" and value.get("async"):
        raise BuildError("Codex parses asynchronous hooks but does not support them")
    if (
        provider == "claude"
        and kind != "command"
        and any(field in value for field in ("async", "asyncRewake"))
    ):
        raise BuildError("Claude `async` and `asyncRewake` require a command hook")
    args = value.get("args")
    if args is not None and (
        not isinstance(args, list) or any(not isinstance(item, str) for item in args)
    ):
        raise BuildError("hook handler `args` must be a list of strings")
    headers = value.get("headers")
    if headers is not None and (
        not isinstance(headers, dict)
        or any(
            not isinstance(key, str) or not isinstance(item, str)
            for key, item in headers.items()
        )
    ):
        raise BuildError("HTTP hook `headers` must map strings to strings")
    allowed_environment = value.get("allowedEnvVars")
    if allowed_environment is not None and (
        not isinstance(allowed_environment, list)
        or any(not isinstance(item, str) for item in allowed_environment)
    ):
        raise BuildError("HTTP hook `allowedEnvVars` must be a list of strings")
    context_limit = value.get("additionalContextLimit")
    if context_limit is not None and (
        isinstance(context_limit, bool)
        or not isinstance(context_limit, int)
        or context_limit <= 0
    ):
        raise BuildError("Codex `additionalContextLimit` must be a positive integer")
    if value.get("shell") not in (None, "bash", "powershell"):
        raise BuildError("Claude command hook `shell` must be `bash` or `powershell`")
    if "input" in value and not isinstance(value["input"], dict):
        raise BuildError("MCP hook `input` must be an object")


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
