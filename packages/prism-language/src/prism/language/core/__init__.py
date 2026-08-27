# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 2: typed core language contracts."""

from .bindings import Binding, BindingError, BindingScope
from .declarations import CallableContract, Parameter, RecordContract
from .modules import (
    InMemoryModuleLoader,
    LanguageModule,
    ModuleLoader,
    ModuleResolver,
    ModuleSource,
)
from .typed_ast import TypedExpression, TypedModule
from .types import (
    ASSURANCE_TYPES,
    BUILTIN_TYPES,
    PROTECTED_TYPES,
    PROVENANCE_TYPES,
    CoreType,
)
from .values import (
    ComputedValue,
    DependentPair,
    Err,
    ExecutionValue,
    GeneratedValue,
    Ok,
    RecordValue,
    RefinementAttemptValue,
    RefinementFailureValue,
    RefinementFeedbackValue,
    RefinementPolicyValue,
    TypedValue,
    ValidatedValue,
)

__all__ = [
    "ASSURANCE_TYPES",
    "BUILTIN_TYPES",
    "PROTECTED_TYPES",
    "PROVENANCE_TYPES",
    "Binding",
    "BindingError",
    "BindingScope",
    "CallableContract",
    "ComputedValue",
    "CoreType",
    "Err",
    "DependentPair",
    "ExecutionValue",
    "GeneratedValue",
    "InMemoryModuleLoader",
    "LanguageModule",
    "ModuleLoader",
    "ModuleResolver",
    "ModuleSource",
    "Ok",
    "Parameter",
    "RecordContract",
    "RecordValue",
    "RefinementAttemptValue",
    "RefinementFailureValue",
    "RefinementFeedbackValue",
    "RefinementPolicyValue",
    "TypedExpression",
    "TypedModule",
    "TypedValue",
    "ValidatedValue",
]
