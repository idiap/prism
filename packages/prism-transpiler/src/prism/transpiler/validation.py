# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Validate Open Agent Skill manifests and native hook configurations."""

from __future__ import annotations

import re
from typing import Literal


class BuildError(ValueError):
    """The external artifact cannot be represented by a complete typed module."""


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


def _validate_skill_manifest(metadata: dict[str, object], directory_name: str) -> None:
    if not metadata:
        raise BuildError("SKILL.md must start with YAML frontmatter")
    unknown = sorted(set(metadata) - _SKILL_FIELDS)
    if unknown:
        raise BuildError("unsupported Open Agent Skill fields: " + ", ".join(unknown))
    _validate_skill_name(metadata.get("name"), directory_name)
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
            _validate_hook_group(provider, event, group, group_index)


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
    _validate_claude_event(provider, event, kind, value)
    if "once" in value:
        raise BuildError("`once` is valid only in Claude skill-frontmatter hooks")
    _validate_hook_fields(provider, event, value, index, str(kind))
    _validate_hook_scalar_fields(event, value, index)
    if provider == "codex" and value.get("async"):
        raise BuildError("Codex parses asynchronous hooks but does not support them")
    if (
        provider == "claude"
        and kind != "command"
        and any(field in value for field in ("async", "asyncRewake"))
    ):
        raise BuildError("Claude `async` and `asyncRewake` require a command hook")
    _validate_hook_payload(value)


def _validate_skill_name(name: object, directory_name: str) -> None:
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


def _validate_hook_group(
    provider: HookProvider, event: str, group: object, group_index: int
) -> None:
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
        raise BuildError(f"Claude hook event `{event}` does not support a matcher")
    if (
        provider == "codex"
        and event not in _CODEX_MATCHER_EVENTS
        and matcher is not None
    ):
        raise BuildError(f"Codex hook event `{event}` does not support a matcher")
    handlers = group.get("hooks")
    if not isinstance(handlers, list) or not handlers:
        raise BuildError(f"hook event `{event}` group {group_index} has no handlers")
    for handler_index, handler in enumerate(handlers, 1):
        _validate_hook_handler(provider, event, handler, handler_index)


def _validate_hook_fields(
    provider: HookProvider, event: str, value: dict, index: int, kind: str
) -> None:
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


def _validate_hook_scalar_fields(event: str, value: dict, index: int) -> None:
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


def _validate_hook_payload(value: dict) -> None:
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


def _validate_claude_event(
    provider: HookProvider, event: str, kind: object, value: dict
) -> None:
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
