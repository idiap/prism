# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Layer 2: typed core language contracts."""

from .bindings import Binding, BindingError, BindingScope
from .declarations import (
    CallableContract,
    Parameter,
    ReasoningInvocationContract,
    RecordContract,
)
from .modules import (
    InMemoryModuleLoader,
    LanguageModule,
    ModuleLoader,
    ModuleResolver,
    ModuleSource,
    TaxonomySource,
)
from .occurrences import (
    AssuranceRequirement,
    OccurrenceContract,
    OriginConstraint,
    ReasoningClassification,
    RelationContract,
    TaxonomyReference,
    ValueRequirement,
    value_requirements,
)
from .typed_ast import TypedExpression, TypedModule
from .types import (
    ASSURANCE_TYPES,
    BUILTIN_TYPES,
    PROTECTED_TYPES,
    PROVENANCE_TYPES,
    CoreType,
    substitute_type,
)
from .values import (
    ComputedValue,
    DependentPair,
    Err,
    ExecutionValue,
    GeneratedValue,
    Ok,
    ProductionActivity,
    ProvenanceGraph,
    RecordValue,
    RefinementAttemptValue,
    RefinementFailureValue,
    RefinementFeedbackValue,
    RefinementPolicyValue,
    TypedValue,
    ValidatedValue,
    ValueReference,
)

__all__ = [
    "ProductionActivity",
    "ValueReference",
    "ProvenanceGraph",
    "AssuranceRequirement",
    "OccurrenceContract",
    "OriginConstraint",
    "ReasoningClassification",
    "RelationContract",
    "TaxonomyReference",
    "ValueRequirement",
    "value_requirements",
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
    "substitute_type",
    "Err",
    "DependentPair",
    "ExecutionValue",
    "GeneratedValue",
    "InMemoryModuleLoader",
    "LanguageModule",
    "ModuleLoader",
    "ModuleResolver",
    "ModuleSource",
    "TaxonomySource",
    "Ok",
    "Parameter",
    "RecordContract",
    "ReasoningInvocationContract",
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
