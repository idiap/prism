# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""The dependency-free native Prism dependent type-theory kernel."""

from .check import Kernel
from .context import EMPTY_CONTEXT, Context, LocalDeclaration, shift, substitute
from .declarations import check_declaration, check_module
from .diagnostics import KernelDiagnostic, KernelError, KernelResourceError
from .environment import (
    CheckedModule,
    CheckedTerm,
    Declaration,
    Environment,
    ModuleImport,
    RecursorRule,
    RecursorSpec,
)
from .equality import is_def_eq
from .inductives import Constructor, InductiveDefinition, admit_inductive
from .levels import (
    ZERO,
    Level,
    LevelMax,
    LevelSucc,
    LevelVar,
    LevelZero,
    level_from_int,
    level_leq,
    level_max,
    level_variables,
    normalize_level,
    substitute_level,
)
from .prelude import prelude_environment, prelude_module
from .reduction import ReductionBudget, whnf
from .serialization import (
    CALCULUS_VERSION,
    CORE_FORMAT_VERSION,
    deserialize_module,
    module_hash,
    serialize_module,
    term_from_data,
    term_hash,
    term_to_data,
)
from .terms import (
    PROP,
    TYPE,
    App,
    Const,
    ConstructorRef,
    InductiveRef,
    Lam,
    Let,
    Local,
    Pi,
    RecursorRef,
    Sort,
    Term,
    apps,
    instantiate_universes,
    pretty,
    unfold_apps,
    universe_variables,
)
from .typing import check, check_closed, infer

__all__ = [
    "CALCULUS_VERSION",
    "CORE_FORMAT_VERSION",
    "EMPTY_CONTEXT",
    "PROP",
    "TYPE",
    "ZERO",
    "App",
    "CheckedModule",
    "CheckedTerm",
    "Const",
    "Constructor",
    "ConstructorRef",
    "Context",
    "Declaration",
    "Environment",
    "InductiveDefinition",
    "InductiveRef",
    "Kernel",
    "KernelDiagnostic",
    "KernelError",
    "KernelResourceError",
    "Lam",
    "Let",
    "Level",
    "LevelMax",
    "LevelSucc",
    "LevelVar",
    "LevelZero",
    "Local",
    "LocalDeclaration",
    "ModuleImport",
    "Pi",
    "RecursorRef",
    "RecursorRule",
    "RecursorSpec",
    "ReductionBudget",
    "Sort",
    "Term",
    "admit_inductive",
    "apps",
    "check",
    "check_closed",
    "check_declaration",
    "check_module",
    "deserialize_module",
    "infer",
    "instantiate_universes",
    "is_def_eq",
    "level_from_int",
    "level_leq",
    "level_max",
    "level_variables",
    "module_hash",
    "normalize_level",
    "prelude_environment",
    "prelude_module",
    "pretty",
    "serialize_module",
    "shift",
    "substitute",
    "substitute_level",
    "term_from_data",
    "term_hash",
    "term_to_data",
    "unfold_apps",
    "universe_variables",
    "whnf",
]
