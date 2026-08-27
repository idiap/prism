# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime ports; implementations live outside prism-language."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from prism.language.core import CoreType


@dataclass(frozen=True, slots=True)
class EffectRequest:
    call_id: str
    symbol: str
    arguments: tuple[Any, ...]
    named_arguments: Mapping[str, Any]
    result_type: CoreType
    effects: tuple[str, ...]
    permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EffectResult:
    value: Any
    type: CoreType
    diagnostics: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = field(default_factory=dict)
    replay_artifacts: Mapping[str, Any] = field(default_factory=dict)
    executor: str | None = None


class EffectHandler(Protocol):
    def handles(self, symbol: str, effects: tuple[str, ...]) -> bool: ...

    def execute(self, request: EffectRequest) -> EffectResult: ...


class ProcessEffectHandler(EffectHandler, Protocol):
    """Port whose implementation is authorized only for ``Process.Run``."""


class NetworkEffectHandler(EffectHandler, Protocol):
    """Port whose implementation is authorized only for ``Network.Request``."""


class MCPEffectHandler(EffectHandler, Protocol):
    """Port whose implementation is authorized only for ``MCP.Call``."""


class ResourceResolver(Protocol):
    def resolve(self, logical_name: str, type_name: str) -> Any: ...


class EffectContractError(ValueError):
    pass


class ExecutionConfigurationError(ValueError):
    pass
