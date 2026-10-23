# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime agents operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Mapping

from prism.language.core import (
    CoreType,
)
from prism.language.kernel import (
    Term,
)
from prism.language.workflows import (
    ExecutionScope,
    ExecutionScopeKind,
)
from prism.runtime.replay import jsonable
from prism.runtime.results import TraceEvent

if TYPE_CHECKING:
    from .execution import _Engine


def _call_agent(
    self: _Engine,
    callee: Any,
    positional: tuple[Any, ...],
    named: Mapping[str, Any],
    env: Mapping[str, Any],
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    local = {key: named[key] for key in ("tools", "skills", "hooks") if key in named}
    invocation_named = {key: value for key, value in named.items() if key not in local}
    values = self._bind_arguments(
        callee.definition.parameters, positional, invocation_named
    )
    persistent = {
        "tools": (
            self._eval(callee.definition.tools, self.global_env)
            if callee.definition.tools is not None
            else []
        ),
        "skills": (
            self._eval(callee.definition.skills, self.global_env)
            if callee.definition.skills is not None
            else []
        ),
        "hooks": (
            self._eval(callee.definition.hooks, self.global_env)
            if callee.definition.hooks is not None
            else None
        ),
    }
    tools = [*persistent["tools"], *local.get("tools", [])]
    skills = [*persistent["skills"], *local.get("skills", [])]
    hooks = tuple(
        item for item in (persistent["hooks"], local.get("hooks")) if item is not None
    )
    self.trace.append(
        TraceEvent(
            "agent-invoked",
            callee.definition.name,
            assurance="typed-callable",
            metadata={
                "tools": tuple(item.name for item in tools),
                "skills": tuple(item.skill_id for item in skills),
                "hooks": tuple(item.provider for item in hooks),
            },
        )
    )
    scope = ExecutionScope(ExecutionScopeKind.AGENT, callee.definition.name)
    self._scope_stack.append(scope)
    try:
        prompt = json.dumps(
            jsonable(
                {
                    "agent": callee.definition.name,
                    "arguments": values,
                    "skills": [
                        {
                            "instructions": item.instructions,
                            "resources": json.loads(item.resources),
                        }
                        for item in skills
                    ],
                }
            ),
            sort_keys=True,
        )
        return self._invoke_effect(
            "generate",
            (prompt,),
            {
                "tools": tuple(item.name for item in tools),
                "hooks": tuple((item.provider, item.configuration) for item in hooks),
            },
            result_type or callee.definition.result_type,
            callee.definition.effects,
        )
    finally:
        self._scope_stack.pop()
