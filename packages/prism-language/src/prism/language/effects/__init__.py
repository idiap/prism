# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 4: typed execution and effect contracts."""

from .checking import EffectCheckError, require_effects
from .ir import (
    Binary,
    Call,
    CallArgument,
    CallExpression,
    Conditional,
    ExecutableProgram,
    Execute,
    Field,
    FunctionDefinition,
    Index,
    ListValue,
    Literal,
    MapValue,
    ReasoningInvocation,
    RecordDefinition,
    Reference,
    Return,
    Solve,
    Try,
    TupleValue,
    Unary,
    ValueBinding,
)
from .ports import (
    EffectContractError,
    EffectHandler,
    EffectRequest,
    EffectResult,
    ExecutionConfigurationError,
    MCPEffectHandler,
    NetworkEffectHandler,
    ProcessEffectHandler,
    ResourceResolver,
)
from .types import STANDARD_EFFECTS, SUPPORTED_EFFECTS

__all__ = [
    "Call",
    "CallArgument",
    "CallExpression",
    "Conditional",
    "EffectCheckError",
    "EffectContractError",
    "EffectHandler",
    "EffectRequest",
    "EffectResult",
    "ExecutableProgram",
    "Execute",
    "ExecutionConfigurationError",
    "MCPEffectHandler",
    "NetworkEffectHandler",
    "ProcessEffectHandler",
    "Field",
    "FunctionDefinition",
    "Index",
    "ListValue",
    "Literal",
    "MapValue",
    "RecordDefinition",
    "Reference",
    "ReasoningInvocation",
    "ResourceResolver",
    "Return",
    "Solve",
    "STANDARD_EFFECTS",
    "SUPPORTED_EFFECTS",
    "ValueBinding",
    "Try",
    "TupleValue",
    "Unary",
    "Binary",
    "require_effects",
]
