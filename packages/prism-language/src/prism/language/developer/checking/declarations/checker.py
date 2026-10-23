# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Checker state and ordered declaration-checking phases."""

from __future__ import annotations

from prism.language.core import (
    BUILTIN_TYPES,
    BindingScope,
    CallableContract,
    CoreType,
    ModuleLoader,
    RecordContract,
)
from prism.language.effects import SUPPORTED_EFFECTS
from prism.language.kernel import Declaration as KernelDeclaration
from prism.language.kernel import Term as KernelTerm
from prism.language.kernel import (
    check_module,
    prelude_environment,
    prelude_module,
)
from prism.language.verification import ProofGoal

from ...api import CheckedProgram, _builtin_bindings, _builtin_callable_contracts
from ...syntax.ast import (
    AgentDecl,
    Binding,
    FunctionDecl,
    Program,
    ReasoningDecl,
    TheoremDecl,
    ToolDecl,
    TypeDecl,
    WorkflowDecl,
)
from ..expressions import _ExpressionCheckingMixin
from ..types import _TypeCheckingMixin
from ..workflows import _WorkflowCheckingMixin
from .admission import _CoreAdmissionMixin
from .callables import _CallableDeclarationMixin
from .imports import _ImportCheckingMixin
from .types import _TypeDeclarationMixin


class _Checker(
    _ImportCheckingMixin,
    _TypeDeclarationMixin,
    _CallableDeclarationMixin,
    _CoreAdmissionMixin,
    _WorkflowCheckingMixin,
    _ExpressionCheckingMixin,
    _TypeCheckingMixin,
):
    def __init__(
        self,
        program: Program,
        module_loader: ModuleLoader | None,
        import_stack: tuple[str, ...] = (),
    ) -> None:
        self.program = program
        self.module_loader = module_loader
        self.import_stack = import_stack
        intrinsic_callables = _builtin_callable_contracts()
        self.scope = BindingScope(_builtin_bindings(intrinsic_callables))
        self.callables: dict[str, CallableContract] = dict(intrinsic_callables)
        self.callable_origins: dict[str, str | None] = {
            name: None for name in intrinsic_callables
        }
        self.records: dict[str, RecordContract] = {}
        self.aliases: dict[str, CoreType] = {}
        self.type_parameters: dict[str, tuple[str, ...]] = {}
        self.variants: dict[str, tuple[str, ...]] = {}
        self.module_members: dict[str, dict[str, CoreType]] = {}
        self.expression_types: dict[int, CoreType] = {}
        self.occurrence_contracts = {}
        self.method_classifications = {}
        self.structural_helpers = {}
        self.workflow_outputs: dict[str, dict[str, CoreType]] = {}
        self.reasoning_outputs: dict[str, dict[str, CoreType]] = {}
        self.reasoning_methods: dict[str, dict[str, CoreType]] = {}
        self.repeat_rebindable: list[dict[str, CoreType]] = []
        self.proof_goals: list[ProofGoal] = []
        self.module_hashes: dict[str, str] = {}
        self.kernel_environment = prelude_environment()
        self.native_names: dict[str, str] = {}
        self.kernel_declarations: list[KernelDeclaration] = []
        self.expression_terms: dict[int, KernelTerm] = {}
        self.expression_proof_bindings = {}
        self.kernel_type_aliases = {
            declaration.name: declaration.alias
            for declaration in self.program.declarations
            if isinstance(declaration, TypeDecl) and declaration.alias is not None
        }
        self.known_types = set(BUILTIN_TYPES) | {
            "DataRead",
            "FileRead",
            "GraphSource",
            "ClockRead",
            "ContextDisclose",
            "MCPCall",
            "Markdown",
            "Model",
            "ModelGenerate",
            "ModelFailure",
            "NetworkRequest",
            "ProcessRun",
            "PythonCall",
            "PythonError",
            "ProofError",
            "SourceError",
            "ToolCall",
            "ToolError",
            "ValidationError",
            *SUPPORTED_EFFECTS,
        }
        # Imported contracts need their private types for unification, but only
        # explicitly imported or module-qualified type names are source-visible.
        self.visible_types = set(self.known_types)

    def run(self) -> CheckedProgram:
        self._load_imports()
        self._declare_types()
        self._declare_callables_and_agents()
        self._check_relation_declarations()
        self._admit_core_definitions()
        self._check_declaration_bodies()
        from ..reasoning_purity import audit_structural_helpers

        audit_structural_helpers(self)
        from ..occurrences import occurrence_contracts

        self.occurrence_contracts = occurrence_contracts(self)
        checked_module = check_module(
            self.program.path or "Main",
            (prelude_module(),),
            tuple(self.kernel_declarations),
        )
        module_hashes = {
            imported.name: imported.content_hash for imported in checked_module.imports
        }
        module_hashes.update(self.module_hashes)
        return CheckedProgram(
            self.program,
            self.scope.snapshot(),
            dict(self.callables),
            dict(self.records),
            dict(self.aliases),
            dict(self.type_parameters),
            dict(self.variants),
            {name: dict(outputs) for name, outputs in self.reasoning_outputs.items()},
            {name: dict(methods) for name, methods in self.reasoning_methods.items()},
            dict(self.callable_origins),
            dict(self.expression_types),
            tuple(self.proof_goals),
            module_hashes,
            checked_module,
            dict(self.expression_terms),
            dict(self.expression_proof_bindings),
            dict(self.occurrence_contracts),
            dict(self.method_classifications),
        )

    def _check_declaration_bodies(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(declaration, ReasoningDecl):
                self._check_reasoning(declaration)
        for declaration in self.program.declarations:
            if isinstance(declaration, Binding):
                self._check_binding(declaration, self.scope, None)
            elif isinstance(declaration, ToolDecl):
                self._check_tool(declaration)
            elif isinstance(declaration, AgentDecl):
                self._check_agent(declaration)
        self._check_workflow_and_callable_bodies()

    def _check_workflow_and_callable_bodies(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(declaration, WorkflowDecl):
                self._check_workflow(declaration)
        for declaration in self.program.declarations:
            if isinstance(declaration, FunctionDecl):
                self._check_callable(declaration)
            elif isinstance(declaration, TheoremDecl):
                self._check_theorem(declaration)
