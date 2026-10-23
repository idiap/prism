# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Codex native hook configuration validation and merging."""

from __future__ import annotations

import json
from typing import Any


class CodexConfigurationError(RuntimeError):
    pass


def _codex_hooks(value: Any) -> tuple[dict[str, Any], ...]:
    if value in (None, (), []):
        return ()
    if not isinstance(value, tuple | list):
        raise CodexConfigurationError("agent hooks must be typed native hook artifacts")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, tuple | list) or len(item) != 2:
            raise CodexConfigurationError("invalid native hook artifact")
        provider, configuration = item
        if provider != "Codex":
            raise CodexConfigurationError(
                f"Codex execution cannot activate Hooks[{provider}]"
            )
        try:
            parsed = json.loads(configuration)
        except (TypeError, json.JSONDecodeError) as exc:
            raise CodexConfigurationError(
                "invalid built Codex hook configuration"
            ) from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("hooks"), dict):
            raise CodexConfigurationError("invalid built Codex hook configuration")
        result.append(parsed)
    return tuple(result)


def _merge_hooks(configurations: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    merged: dict[str, Any] = {"hooks": {}}
    for configuration in configurations:
        for event, groups in configuration["hooks"].items():
            merged["hooks"].setdefault(event, []).extend(groups)
    return merged
