# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Checker orchestration, imports, and declaration admission."""

from __future__ import annotations

import hashlib
import re

from prism.language.core import (
    BUILTIN_TYPES,
    BindingScope,
    CallableContract,
    CoreType,
    ModuleLoader,
    RecordContract,
)
from prism.language.core import Binding as CoreBinding
from prism.language.core import Parameter as CoreParameter
from prism.language.effects import SUPPORTED_EFFECTS
from prism.language.kernel import PROP as KERNEL_PROP
from prism.language.kernel import Declaration as KernelDeclaration
from prism.language.kernel import (
    KernelError,
    check_declaration,
    check_module,
    prelude_environment,
    prelude_module,
)
from prism.language.kernel import Lam as KernelLam
from prism.language.kernel import Pi as KernelPi
from prism.language.kernel import Term as KernelTerm
from prism.language.verification import ProofGoal

from ..api import CheckedProgram, _builtin_bindings, _builtin_callable_contracts
from ..core_elaboration import CoreLocal, elaborate_type_text
from ..core_elaboration import elaborate_expression as elaborate_core_expression
from ..syntax.ast import (
    AgentDecl,
    Binding,
    FunctionDecl,
    ImportDecl,
    ModuleImportDecl,
    NameExpr,
    Program,
    ReasoningDecl,
    RelationDecl,
    Return,
    TheoremDecl,
    ToolDecl,
    TypeDecl,
    TypeExpr,
    WorkflowDecl,
)
from ..syntax.parser import parse_source
from ..type_syntax import _find_top_level, _split_top_level
from .expressions import _ExpressionCheckingMixin
from .helpers import _binding_value_dependencies
from .types import _TypeCheckingMixin
from .workflows import _WorkflowCheckingMixin


class _Checker(_WorkflowCheckingMixin, _ExpressionCheckingMixin, _TypeCheckingMixin):
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
        self.workflow_outputs: dict[str, dict[str, CoreType]] = {}
        self.reasoning_outputs: dict[str, dict[str, CoreType]] = {}
        self.reasoning_methods: dict[str, dict[str, CoreType]] = {}
        self.repeat_rebindable: list[dict[str, CoreType]] = []
        self.proof_goals: list[ProofGoal] = []
        self.module_hashes: dict[str, str] = {}
        self.kernel_environment = prelude_environment()
        self.kernel_declarations: list[KernelDeclaration] = []
        self.expression_terms: dict[int, KernelTerm] = {}
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
        for declaration in self.program.declarations:
            if isinstance(declaration, WorkflowDecl):
                self._check_workflow(declaration)
        for declaration in self.program.declarations:
            if isinstance(declaration, FunctionDecl):
                self._check_callable(declaration)
            elif isinstance(declaration, TheoremDecl):
                self._check_theorem(declaration)
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
        )

    def _check_relation_declarations(self) -> None:
        for declaration in self.program.declarations:
            if not isinstance(declaration, RelationDecl):
                continue
            contract = self.callables[declaration.name]
            if len(contract.parameters) != 2:
                self.fail(
                    f"relation `{declaration.name}` must declare exactly source and target endpoints",
                    declaration.span,
                    "type-relation-endpoints",
                )

    def _load_imports(self) -> None:
        explicit_import_names = {
            alias or exported
            for item in self.program.declarations
            if isinstance(item, ImportDecl)
            for exported, alias in item.names
        }
        for declaration in self.program.declarations:
            if not isinstance(declaration, ImportDecl | ModuleImportDecl):
                continue
            if self.module_loader is None:
                self.fail(
                    f"cannot resolve import `{declaration.module}` without a module loader",
                    declaration.span,
                    "type-import-loader",
                )
            if declaration.module in self.import_stack:
                cycle = " -> ".join((*self.import_stack, declaration.module))
                self.fail(
                    f"module import cycle: {cycle}",
                    declaration.span,
                    "type-import-cycle",
                )
            try:
                source = self.module_loader.load_module(declaration.module)
            except ValueError as exc:
                self.fail(str(exc), declaration.span, "type-import-module")
            imported_program = parse_source(source.source, source.origin)
            imported = _Checker(
                imported_program,
                self.module_loader,
                (*self.import_stack, declaration.module),
            )
            imported_checked = imported.run()
            self.expression_terms.update(imported_checked.expression_terms)
            for core_declaration in imported.kernel_declarations:
                try:
                    self.kernel_environment.get(core_declaration.name)
                except KernelError:
                    self.kernel_environment = check_declaration(
                        self.kernel_environment, core_declaration
                    )
                    self.kernel_declarations.append(core_declaration)
            self.expression_types.update(imported_checked.expression_types)
            self.module_hashes.update(imported_checked.module_hashes)
            self.module_hashes[declaration.module] = hashlib.sha256(
                source.source.encode()
            ).hexdigest()
            self.known_types.update(imported.known_types)
            self.records.update(imported.records)
            self.aliases.update(imported.aliases)
            self.variants.update(imported.variants)
            imported_declarations = {
                name: item
                for item in imported_program.declarations
                if isinstance((name := getattr(item, "name", None)), str)
            }
            imported_values = {
                name: imported_checked.globals[name]
                for name, item in imported_declarations.items()
                if isinstance(item, Binding)
            }
            imported_tools = {
                name: imported_checked.globals[name]
                for name, item in imported_declarations.items()
                if isinstance(item, ToolDecl)
            }
            value_bindings: dict[str, tuple[CoreBinding, Binding]] = {
                name: (imported_checked.globals[name], item)
                for name, item in imported_declarations.items()
                if isinstance(item, Binding)
            }
            value_bindings.update(
                {
                    name: (item, item.value)
                    for name, item in imported_checked.globals.items()
                    if isinstance(item.value, Binding)
                }
            )

            def import_callable(exported: str, qualified: str) -> None:
                if qualified in self.callables:
                    return
                contract = imported.callables[exported]
                declaration_value = imported_checked.globals[exported].value
                localized_contract = CallableContract(
                    qualified,
                    contract.parameters,
                    contract.result,
                    contract.effects,
                    contract.kind,
                    contract.type_parameters,
                    contract.failure,
                )
                if exported in imported.workflow_outputs:
                    self.workflow_outputs[qualified] = imported.workflow_outputs[
                        exported
                    ]
                if exported in imported.reasoning_outputs:
                    self.reasoning_outputs[qualified] = imported.reasoning_outputs[
                        exported
                    ]
                if exported in imported.reasoning_methods:
                    self.reasoning_methods[qualified] = imported.reasoning_methods[
                        exported
                    ]
                # Bind before following dependencies so mutually recursive
                # imported callables terminate at this already-known contract.
                self.callables[qualified] = localized_contract
                self.callable_origins[qualified] = imported.callable_origins.get(
                    exported, imported.program.path
                )
                self._bind(
                    qualified,
                    localized_contract.type,
                    declaration_value,
                    declaration.span,
                )
                namespace = qualified.rpartition(".")[0]
                for dependency in _binding_value_dependencies(
                    declaration_value,
                    set(value_bindings)
                    | {
                        name
                        for name, candidate in imported.callables.items()
                        if candidate.kind != "intrinsic"
                    },
                    namespace=namespace,
                ):
                    if dependency == exported:
                        continue
                    dependency_name = (
                        dependency
                        if "." in dependency or not namespace
                        else f"{namespace}.{dependency}"
                    )
                    if dependency in value_bindings:
                        import_value(dependency, dependency_name)
                    elif dependency_name not in explicit_import_names:
                        import_callable(dependency, dependency_name)

            def import_value(exported: str, qualified: str) -> CoreBinding:
                existing = self.scope.snapshot().get(qualified)
                if existing is not None:
                    return existing
                source_binding, source_declaration = value_bindings[exported]
                namespace = qualified.rpartition(".")[0]
                for dependency in _binding_value_dependencies(
                    source_declaration.value,
                    set(value_bindings)
                    | {
                        name
                        for name, contract in imported.callables.items()
                        if contract.kind != "intrinsic"
                    },
                    namespace=namespace,
                ):
                    dependency_name = (
                        dependency
                        if "." in dependency or not namespace
                        else f"{namespace}.{dependency}"
                    )
                    if dependency in value_bindings:
                        import_value(dependency, dependency_name)
                        continue
                    if dependency_name in self.callables:
                        continue
                    if dependency_name in explicit_import_names:
                        continue
                    import_callable(dependency, dependency_name)
                localized = Binding(
                    qualified,
                    source_declaration.value,
                    source_declaration.span,
                    source_declaration.annotation,
                )
                self._bind(
                    qualified,
                    source_binding.type,
                    localized,
                    declaration.span,
                )
                return self.scope.resolve(qualified)

            if isinstance(declaration, ImportDecl):
                for exported, alias in declaration.names:
                    local = alias or exported
                    if (
                        exported in imported.callables
                        and imported.callables[exported].kind != "intrinsic"
                    ):
                        existing = self.scope.snapshot().get(local)
                        if (
                            existing is not None
                            and existing.value is imported_declarations.get(exported)
                        ):
                            continue
                        contract = imported.callables[exported]
                        localized = CallableContract(
                            local,
                            contract.parameters,
                            contract.result,
                            contract.effects,
                            contract.kind,
                            contract.type_parameters,
                            contract.failure,
                        )
                        if exported in imported.workflow_outputs:
                            self.workflow_outputs[local] = imported.workflow_outputs[
                                exported
                            ]
                        if exported in imported.reasoning_outputs:
                            self.reasoning_outputs[local] = imported.reasoning_outputs[
                                exported
                            ]
                        if exported in imported.reasoning_methods:
                            self.reasoning_methods[local] = imported.reasoning_methods[
                                exported
                            ]
                        self.callables[local] = localized
                        self.callable_origins[local] = imported.callable_origins.get(
                            exported, imported.program.path
                        )
                        self._bind(
                            local,
                            localized.type,
                            imported_declarations.get(exported),
                            declaration.span,
                        )
                        source_declaration = imported_declarations.get(exported)
                        if source_declaration is not None:
                            for dependency in _binding_value_dependencies(
                                source_declaration,
                                set(value_bindings)
                                | {
                                    name
                                    for name, candidate in imported.callables.items()
                                    if candidate.kind != "intrinsic"
                                },
                            ):
                                if dependency == exported:
                                    continue
                                if dependency in value_bindings:
                                    import_value(dependency, dependency)
                                elif (
                                    dependency not in self.callables
                                    and dependency not in explicit_import_names
                                ):
                                    import_callable(dependency, dependency)
                    elif exported in imported.records:
                        record = imported.records[exported]
                        self.records[local] = RecordContract(
                            local, record.fields, record.type_parameters
                        )
                        self.type_parameters[local] = record.type_parameters
                        self.known_types.add(local)
                        self.visible_types.add(local)
                        self._bind(local, CoreType("Type"), record, declaration.span)
                    elif exported in imported.aliases:
                        self.aliases[local] = imported.aliases[exported]
                        self.type_parameters[local] = imported.type_parameters.get(
                            exported, ()
                        )
                        if exported in imported.kernel_type_aliases:
                            self.kernel_type_aliases[local] = (
                                imported.kernel_type_aliases[exported]
                            )
                        self.known_types.add(local)
                        self.visible_types.add(local)
                        self._bind(
                            local,
                            CoreType("Type"),
                            imported.aliases[exported],
                            declaration.span,
                        )
                    elif exported in imported.variants:
                        self.variants[local] = imported.variants[exported]
                        self.type_parameters[local] = imported.type_parameters.get(
                            exported, ()
                        )
                        self.known_types.add(local)
                        self.visible_types.add(local)
                        self._bind(
                            local,
                            CoreType("Type"),
                            imported_declarations.get(exported),
                            declaration.span,
                        )
                        for constructor in imported.variants[exported]:
                            record = imported.records.get(constructor)
                            if record is None:
                                continue
                            self.records[constructor] = record
                            self.known_types.add(constructor)
                            self.visible_types.add(constructor)
                            if constructor not in self.scope.snapshot():
                                self._bind(
                                    constructor,
                                    CoreType("Type"),
                                    imported_declarations.get(exported),
                                    declaration.span,
                                )
                    elif exported in imported_tools:
                        imported_tool = imported_tools[exported]
                        self._bind(
                            local,
                            imported_tool.type,
                            imported_declarations[exported],
                            declaration.span,
                        )
                    elif exported in imported_values:
                        qualified = f"{declaration.module}.{exported}"
                        imported_value = import_value(exported, qualified)
                        alias_expression = NameExpr(qualified, declaration.span)
                        self.expression_types[id(alias_expression)] = (
                            imported_value.type
                        )
                        self._bind(
                            local,
                            imported_value.type,
                            Binding(local, alias_expression, declaration.span),
                            declaration.span,
                        )
                    else:
                        self.fail(
                            f"module `{declaration.module}` has no export `{exported}`",
                            declaration.span,
                            "type-import-export",
                        )
            else:
                members: dict[str, CoreType] = {}
                for exported, contract in imported.callables.items():
                    if contract.kind == "intrinsic":
                        continue
                    qualified = f"{declaration.alias}.{exported}"
                    localized = CallableContract(
                        qualified,
                        contract.parameters,
                        contract.result,
                        contract.effects,
                        contract.kind,
                        contract.type_parameters,
                        contract.failure,
                    )
                    if exported in imported.workflow_outputs:
                        self.workflow_outputs[qualified] = imported.workflow_outputs[
                            exported
                        ]
                    if exported in imported.reasoning_outputs:
                        self.reasoning_outputs[qualified] = imported.reasoning_outputs[
                            exported
                        ]
                    if exported in imported.reasoning_methods:
                        self.reasoning_methods[qualified] = imported.reasoning_methods[
                            exported
                        ]
                    self.callables[qualified] = localized
                    if contract.result.name == "Prop":
                        self.aliases[qualified] = CoreType(exported)
                    self.callable_origins[qualified] = imported.callable_origins.get(
                        exported, imported.program.path
                    )
                    members[exported] = localized.type
                    self._bind(
                        qualified,
                        localized.type,
                        imported_declarations.get(exported),
                        declaration.span,
                    )
                for exported, record in imported.records.items():
                    qualified = f"{declaration.alias}.{exported}"
                    self.records[qualified] = RecordContract(
                        record.name, record.fields, record.type_parameters
                    )
                    self.aliases[qualified] = CoreType(
                        record.name,
                        tuple(CoreType(name) for name in record.type_parameters),
                    )
                    self.type_parameters[qualified] = record.type_parameters
                    self.known_types.add(qualified)
                    self.visible_types.add(qualified)
                    members[exported] = CoreType("Type")
                    self._bind(qualified, CoreType("Type"), record, declaration.span)
                for exported, alias_type in imported.aliases.items():
                    qualified = f"{declaration.alias}.{exported}"
                    self.aliases[qualified] = alias_type
                    self.type_parameters[qualified] = imported.type_parameters.get(
                        exported, ()
                    )
                    self.known_types.add(qualified)
                    self.visible_types.add(qualified)
                    members[exported] = CoreType("Type")
                    self._bind(
                        qualified, CoreType("Type"), alias_type, declaration.span
                    )
                for exported, alternatives in imported.variants.items():
                    qualified = f"{declaration.alias}.{exported}"
                    self.variants[qualified] = alternatives
                    parameters = imported.type_parameters.get(exported, ())
                    self.aliases[qualified] = CoreType(
                        exported,
                        tuple(CoreType(name) for name in parameters),
                    )
                    self.type_parameters[qualified] = parameters
                    self.known_types.add(qualified)
                    self.visible_types.add(qualified)
                    members[exported] = CoreType("Type")
                    self._bind(
                        qualified,
                        CoreType("Type"),
                        imported_declarations.get(exported),
                        declaration.span,
                    )
                for exported in imported_values:
                    qualified = f"{declaration.alias}.{exported}"
                    imported_value = import_value(exported, qualified)
                    members[exported] = imported_value.type
                for exported, imported_tool in imported_tools.items():
                    qualified = f"{declaration.alias}.{exported}"
                    members[exported] = imported_tool.type
                    self._bind(
                        qualified,
                        imported_tool.type,
                        imported_declarations[exported],
                        declaration.span,
                    )
                self.module_members[declaration.alias] = members
                self._bind(
                    declaration.alias,
                    CoreType("Module", (CoreType(declaration.alias),)),
                    imported,
                    declaration.span,
                )

    def _declare_types(self) -> None:
        for declaration in self.program.declarations:
            if not isinstance(declaration, TypeDecl):
                continue
            if declaration.name in self.visible_types:
                self.fail(
                    f"duplicate type `{declaration.name}`",
                    declaration.span,
                    "type-duplicate",
                )
            self._validate_type_parameter_declarations(
                declaration.type_parameters, declaration.span, declaration.name
            )
            self.known_types.add(declaration.name)
            self.visible_types.add(declaration.name)
            self.type_parameters[declaration.name] = declaration.type_parameters
            self._bind(
                declaration.name, CoreType("Type"), declaration, declaration.span
            )
        for declaration in self.program.declarations:
            if not isinstance(declaration, TypeDecl):
                continue
            if declaration.alias:
                self.aliases[declaration.name] = self._type(
                    declaration.alias, set(declaration.type_parameters)
                )
            elif declaration.fields:
                fields: list[CoreParameter] = []
                seen: set[str] = set()
                for field in declaration.fields:
                    if field.name in seen:
                        self.fail(
                            f"duplicate field `{field.name}` in `{declaration.name}`",
                            field.span,
                            "type-record-duplicate-field",
                        )
                    seen.add(field.name)
                    fields.append(
                        CoreParameter(
                            field.name,
                            self._type(
                                field.type, set(declaration.type_parameters) | seen
                            ),
                        )
                    )
                self.records[declaration.name] = RecordContract(
                    declaration.name, tuple(fields), declaration.type_parameters
                )
            elif declaration.alternatives:
                constructors: list[str] = []
                for alternative in declaration.alternatives:
                    match = re.fullmatch(r"([A-Za-z_]\w*)(?:\((.*)\))?", alternative)
                    if match is None:
                        self.fail(
                            f"invalid variant constructor `{alternative}`",
                            declaration.span,
                            "type-variant-constructor",
                        )
                    constructor = match.group(1)
                    constructors.append(constructor)
                    if match.group(2) is None and (
                        constructor in self.visible_types
                        or constructor in self.scope.snapshot()
                    ):
                        # A bare existing type is a failure-union member, not a
                        # new nullary data constructor.
                        continue
                    fields: list[CoreParameter] = []
                    if match.group(2):
                        for item in _split_top_level(match.group(2)):
                            colon = _find_top_level(item, ":")
                            if colon < 1:
                                self.fail(
                                    f"variant field `{item}` requires `name: Type`",
                                    declaration.span,
                                    "type-variant-field",
                                )
                            fields.append(
                                CoreParameter(
                                    item[:colon].strip(),
                                    self._type(
                                        TypeExpr(
                                            item[colon + 1 :].strip(),
                                            declaration.span,
                                        ),
                                        set(declaration.type_parameters),
                                    ),
                                )
                            )
                    if constructor in self.records:
                        self.fail(
                            f"duplicate constructor `{constructor}`",
                            declaration.span,
                            "type-duplicate",
                        )
                    self.records[constructor] = RecordContract(
                        constructor, tuple(fields), declaration.type_parameters
                    )
                    self.known_types.add(constructor)
                    self.visible_types.add(constructor)
                    self._bind(
                        constructor,
                        CoreType("Type"),
                        declaration,
                        declaration.span,
                    )
                self.variants[declaration.name] = tuple(constructors)

    def _declare_callables_and_agents(self) -> None:
        for declaration in self.program.declarations:
            if isinstance(
                declaration,
                FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl | AgentDecl,
            ):
                declared_effects = (
                    declaration.effects
                    if isinstance(declaration, FunctionDecl | WorkflowDecl | AgentDecl)
                    else ()
                )
                unknown_effects = set(declared_effects) - SUPPORTED_EFFECTS
                if unknown_effects:
                    self.fail(
                        f"unknown effects: {', '.join(sorted(unknown_effects))}",
                        declaration.span,
                        "type-unknown-effect",
                    )
                type_params = (
                    set(declaration.type_parameters)
                    if isinstance(
                        declaration,
                        FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl,
                    )
                    else set()
                )
                self._validate_type_parameter_declarations(
                    (
                        declaration.type_parameters
                        if isinstance(
                            declaration,
                            FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl,
                        )
                        else ()
                    ),
                    declaration.span,
                    declaration.name,
                )
                parameters = tuple(
                    CoreParameter(item.name, self._type(item.type, type_params))
                    for item in declaration.parameters
                )
                result = self._type(
                    declaration.result,
                    type_params | {item.name for item in declaration.parameters},
                )
                kind = "def"
                if isinstance(declaration, WorkflowDecl):
                    kind = "workflow"
                elif isinstance(declaration, ReasoningDecl):
                    kind = "reasoning"
                elif isinstance(declaration, RelationDecl):
                    kind = "relation"
                elif isinstance(declaration, AgentDecl):
                    kind = "agent"
                contract = CallableContract(
                    declaration.name,
                    parameters,
                    result,
                    declared_effects,
                    kind,
                    (
                        declaration.type_parameters
                        if isinstance(
                            declaration,
                            FunctionDecl | WorkflowDecl | ReasoningDecl | RelationDecl,
                        )
                        else ()
                    ),
                    (
                        self._type(declaration.failure, type_params)
                        if isinstance(declaration, WorkflowDecl)
                        else None
                    ),
                )
                self.callables[declaration.name] = contract
                self.callable_origins[declaration.name] = self.program.path
                self._bind(
                    declaration.name, contract.type, declaration, declaration.span
                )
            elif isinstance(declaration, TheoremDecl):
                parameters = tuple(
                    CoreParameter(
                        item.name,
                        self._type(item.type, {p.name for p in declaration.parameters}),
                    )
                    for item in declaration.parameters
                )
                result = CoreType("Proof", (CoreType(declaration.conclusion),))
                contract = CallableContract(
                    declaration.name, parameters, result, (), "theorem"
                )
                self.callables[declaration.name] = contract
                self.callable_origins[declaration.name] = self.program.path
                self._bind(
                    declaration.name, contract.type, declaration, declaration.span
                )
        for declaration in self.program.declarations:
            if not isinstance(declaration, ToolDecl):
                continue
            tool_type = self._type(declaration.type)
            if tool_type.name != "Tool" or len(tool_type.arguments) != 1:
                self.fail(
                    "a tool annotation must be `Tool[CallableContract]`",
                    declaration.span,
                    "type-tool-contract",
                )
            self._bind(declaration.name, tool_type, declaration, declaration.span)

    def _admit_core_definitions(self) -> None:
        """Admit the pure, total surface subset that can occur in proofs."""

        for declaration in self.program.declarations:
            if isinstance(declaration, Binding) and declaration.annotation is not None:
                try:
                    binding_type = elaborate_type_text(
                        declaration.annotation.text, self.kernel_environment
                    )
                    if declaration.annotation.text.strip() not in {"Nat", "Bool"}:
                        continue
                    binding_value = elaborate_core_expression(
                        declaration.value, self.kernel_environment
                    )
                    admitted_binding = KernelDeclaration(
                        declaration.name,
                        binding_type,
                        binding_value,
                        "definition",
                    )
                    self.kernel_environment = check_declaration(
                        self.kernel_environment, admitted_binding
                    )
                    self.kernel_declarations.append(
                        self.kernel_environment.get(declaration.name)
                    )
                    self.expression_terms[id(declaration.value)] = binding_value
                except (KernelError, ValueError):
                    continue
                continue
            if not isinstance(declaration, FunctionDecl) or declaration.effects:
                continue
            contract = self.callables[declaration.name]
            if contract.result.name not in {"Nat", "Bool", "Prop"}:
                continue
            if any(
                item.type.name not in {"Nat", "Bool"} for item in contract.parameters
            ):
                continue
            returns = [item for item in declaration.body if isinstance(item, Return)]
            if len(returns) != 1 or len(declaration.body) != 1:
                continue
            locals_: tuple[CoreLocal, ...] = ()
            parameter_terms: list[tuple[str, KernelTerm]] = []
            try:
                for parameter, source_parameter in zip(
                    contract.parameters,
                    declaration.parameters,
                    strict=True,
                ):
                    parameter_type = self._elaborate_kernel_type(
                        source_parameter.type,
                        locals_,
                    )
                    parameter_terms.append((parameter.name, parameter_type))
                    locals_ = (*locals_, CoreLocal(parameter.name, parameter_type))
                result_type = (
                    KERNEL_PROP
                    if contract.result.name == "Prop"
                    else self._elaborate_kernel_type(
                        declaration.result,
                        locals_,
                    )
                )
                value = elaborate_core_expression(
                    returns[0].value, self.kernel_environment, locals_
                )
                type_term = result_type
                value_term = value
                for name, parameter_type in reversed(parameter_terms):
                    type_term = KernelPi(name, parameter_type, type_term)
                    value_term = KernelLam(name, parameter_type, value_term)
                admitted = KernelDeclaration(
                    declaration.name,
                    type_term,
                    value_term,
                    "definition",
                    transparent=True,
                    pure=True,
                    total=True,
                )
                self.kernel_environment = check_declaration(
                    self.kernel_environment, admitted
                )
                checked = self.kernel_environment.get(declaration.name)
                self.kernel_declarations.append(checked)
                self.expression_terms[id(returns[0].value)] = value
            except (KernelError, ValueError):
                # Non-proof callables remain ordinary effect/runtime contracts.
                # A later strict declaration that references one fails closed.
                continue
