# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Localization of named and namespaced exports and their dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prism.language.core import Binding as CoreBinding
from prism.language.core import (
    CallableContract,
    CoreType,
    RecordContract,
)

from ...api import CheckedProgram
from ...syntax.ast import (
    Binding,
    Declaration,
    ImportDecl,
    ModuleImportDecl,
    NameExpr,
    ToolDecl,
)
from ..base import _CheckerPhase
from ..helpers import _binding_value_dependencies

if TYPE_CHECKING:
    from .checker import _Checker


class _ModuleImports:
    """Localize one checked module's exports and their private dependencies."""

    def __init__(
        self,
        checker: _CheckerPhase,
        imported: _Checker,
        checked: CheckedProgram,
        declaration: ImportDecl | ModuleImportDecl,
        explicit_import_names: set[str],
    ) -> None:
        self.checker = checker
        self.imported = imported
        self.checked = checked
        self.declaration = declaration
        self.explicit_import_names = explicit_import_names
        self.declarations = {
            name: item
            for item in self.imported.program.declarations
            if isinstance((name := getattr(item, "name", None)), str)
        }
        self.values = {
            name: self.checked.globals[name]
            for name, item in self.declarations.items()
            if isinstance(item, Binding)
        }
        self.tools = {
            name: self.checked.globals[name]
            for name, item in self.declarations.items()
            if isinstance(item, ToolDecl)
        }
        self.value_bindings: dict[str, tuple[CoreBinding, Binding]] = {
            name: (self.checked.globals[name], item)
            for name, item in self.declarations.items()
            if isinstance(item, Binding)
        }
        self.value_bindings.update(
            {
                name: (item, item.value)
                for name, item in self.checked.globals.items()
                if isinstance(item.value, Binding)
            }
        )

        self.dependency_names = set(self.value_bindings) | {
            name
            for name, contract in imported.callables.items()
            if contract.kind != "intrinsic"
        }

    def import_callable(self, exported: str, qualified: str) -> None:
        if qualified in self.checker.callables:
            return
        declaration_value = self.checked.globals[exported].value
        self._bind_imported_callable(exported, qualified, declaration_value)
        namespace = qualified.rpartition(".")[0]
        for dependency in _binding_value_dependencies(
            declaration_value,
            self.dependency_names,
            namespace=namespace,
        ):
            if dependency == exported:
                continue
            dependency_name = (
                dependency
                if "." in dependency or not namespace
                else f"{namespace}.{dependency}"
            )
            if dependency in self.value_bindings:
                self.import_value(dependency, dependency_name)
            elif dependency_name not in self.explicit_import_names:
                self.import_callable(dependency, dependency_name)

    def _bind_imported_callable(
        self, exported: str, qualified: str, declaration_value: Declaration | None
    ) -> CallableContract:
        contract = self.imported.callables[exported]
        if exported in self.imported.native_names:
            self.checker.native_names[qualified] = self.imported.native_names[exported]
        localized_contract = CallableContract(
            qualified,
            contract.parameters,
            contract.result,
            contract.effects,
            contract.kind,
            contract.type_parameters,
            contract.failure,
            contract.structural_error,
        )
        if exported in self.imported.workflow_outputs:
            self.checker.workflow_outputs[qualified] = self.imported.workflow_outputs[
                exported
            ]
        if exported in self.imported.reasoning_outputs:
            self.checker.reasoning_outputs[qualified] = self.imported.reasoning_outputs[
                exported
            ]
        if exported in self.imported.reasoning_methods:
            self.checker.reasoning_methods[qualified] = self.imported.reasoning_methods[
                exported
            ]
        # Bind before following dependencies so mutually recursive
        # imported callables terminate at this already-known contract.
        self.checker.callables[qualified] = localized_contract
        self.checker.callable_origins[qualified] = self.imported.callable_origins.get(
            exported, self.imported.program.path
        )
        self.checker._bind(
            qualified,
            localized_contract.type,
            declaration_value,
            self.declaration.span,
            identity=self.checked.globals[exported].identity,
        )
        return localized_contract

    def import_value(self, exported: str, qualified: str) -> CoreBinding:
        existing = self.checker.scope.snapshot().get(qualified)
        if existing is not None:
            return existing
        source_binding, source_declaration = self.value_bindings[exported]
        if exported in self.imported.native_names:
            self.checker.native_names[qualified] = self.imported.native_names[exported]
        namespace = qualified.rpartition(".")[0]
        for dependency in _binding_value_dependencies(
            source_declaration.value,
            self.dependency_names,
            namespace=namespace,
        ):
            dependency_name = (
                dependency
                if "." in dependency or not namespace
                else f"{namespace}.{dependency}"
            )
            if dependency in self.value_bindings:
                self.import_value(dependency, dependency_name)
                continue
            if dependency_name in self.checker.callables:
                continue
            if dependency_name in self.explicit_import_names:
                continue
            self.import_callable(dependency, dependency_name)
        localized = Binding(
            qualified,
            source_declaration.value,
            source_declaration.span,
            source_declaration.annotation,
        )
        self.checker._bind(
            qualified,
            source_binding.type,
            localized,
            self.declaration.span,
            identity=source_binding.identity,
        )
        return self.checker.scope.resolve(qualified)

    def import_names(self, declaration: ImportDecl) -> None:
        for exported, alias in declaration.names:
            self._import_name(exported, alias or exported)

    def _import_name(self, exported: str, local: str) -> None:
        if exported not in self.checked.globals:
            self.checker.fail(
                f"module `{self.declaration.module}` has no export `{exported}`",
                self.declaration.span,
                "type-import-export",
            )
        if (
            exported in self.imported.callables
            and self.imported.callables[exported].kind != "intrinsic"
        ):
            self._import_named_callable(exported, local)
        elif exported in self.imported.records:
            self._import_record(exported, local, qualified=False)
        elif exported in self.imported.aliases:
            self._import_alias(exported, local, qualified=False)
        elif exported in self.imported.variants:
            self._import_variant(exported, local, qualified=False)
        elif exported in self.tools:
            self._import_tool(exported, local)
        elif exported in self.values:
            self._import_named_value(exported, local)
        else:
            self.checker.fail(
                f"module `{self.declaration.module}` has no export `{exported}`",
                self.declaration.span,
                "type-import-export",
            )

    def _import_named_callable(self, exported: str, local: str) -> None:
        existing = self.checker.scope.snapshot().get(local)
        if existing is not None and existing.value is self.declarations.get(exported):
            return
        self._bind_imported_callable(exported, local, self.declarations.get(exported))
        source_declaration = self.declarations.get(exported)
        if source_declaration is not None:
            for dependency in _binding_value_dependencies(
                source_declaration,
                self.dependency_names,
            ):
                if dependency == exported:
                    continue
                if dependency in self.value_bindings:
                    self.import_value(dependency, dependency)
                elif (
                    dependency not in self.checker.callables
                    and dependency not in self.explicit_import_names
                ):
                    self.import_callable(dependency, dependency)

    def _import_named_value(self, exported: str, local: str) -> None:
        qualified = f"{self.declaration.module}.{exported}"
        imported_value = self.import_value(exported, qualified)
        if exported in self.imported.native_names:
            self.checker.native_names[local] = self.imported.native_names[exported]
        existing = self.checker.scope.snapshot().get(local)
        if existing is not None and existing.identity == imported_value.identity:
            return
        alias_expression = NameExpr(qualified, self.declaration.span)
        self.checker.expression_types[id(alias_expression)] = imported_value.type
        self.checker._bind(
            local,
            imported_value.type,
            Binding(local, alias_expression, self.declaration.span),
            self.declaration.span,
        )

    def _bind_type(
        self, local: str, value: object, identity: str | None = None
    ) -> None:
        self.checker.known_types.add(local)
        self.checker.visible_types.add(local)
        self.checker._bind(
            local, CoreType("Type"), value, self.declaration.span, identity=identity
        )

    def _import_record(self, exported: str, local: str, *, qualified: bool) -> None:
        record = self.imported.records[exported]
        name = record.name if qualified else local
        self.checker.records[local] = RecordContract(
            name, record.fields, record.type_parameters, record.identity
        )
        if qualified:
            self.checker.aliases[local] = CoreType(
                record.name, tuple(CoreType(name) for name in record.type_parameters)
            )
        self.checker.type_parameters[local] = record.type_parameters
        self._bind_type(local, record, self.checked.globals[exported].identity)

    def _import_alias(self, exported: str, local: str, *, qualified: bool) -> None:
        alias_type = self.imported.aliases[exported]
        self.checker.aliases[local] = alias_type
        self.checker.type_parameters[local] = self.imported.type_parameters.get(
            exported, ()
        )
        if not qualified and exported in self.imported.kernel_type_aliases:
            self.checker.kernel_type_aliases[local] = self.imported.kernel_type_aliases[
                exported
            ]
        binding = self.checked.globals.get(exported)
        self._bind_type(
            local,
            alias_type,
            binding.identity if binding is not None else alias_type.binding_identity,
        )

    def _import_variant(self, exported: str, local: str, *, qualified: bool) -> None:
        self.checker.variants[local] = self.imported.variants[exported]
        parameters = self.imported.type_parameters.get(exported, ())
        self.checker.type_parameters[local] = parameters
        if qualified:
            self.checker.aliases[local] = CoreType(
                exported, tuple(CoreType(name) for name in parameters)
            )
        self._bind_type(
            local,
            self.declarations.get(exported),
            self.checked.globals[exported].identity,
        )
        if not qualified:
            self._import_variant_constructors(exported)

    def _import_variant_constructors(self, exported: str) -> None:
        for constructor in self.imported.variants[exported]:
            record = self.imported.records.get(constructor)
            if record is None:
                continue
            self.checker.records[constructor] = record
            self.checker.known_types.add(constructor)
            self.checker.visible_types.add(constructor)
            if constructor not in self.checker.scope.snapshot():
                self.checker._bind(
                    constructor,
                    CoreType("Type"),
                    self.declarations.get(exported),
                    self.declaration.span,
                )

    def _import_tool(self, exported: str, local: str) -> None:
        imported_tool = self.tools[exported]
        self.checker._bind(
            local,
            imported_tool.type,
            self.declarations[exported],
            self.declaration.span,
        )

    def import_namespace(self, declaration: ModuleImportDecl) -> None:
        members: dict[str, CoreType] = {}
        for exported, contract in self.imported.callables.items():
            if contract.kind == "intrinsic":
                continue
            qualified = f"{declaration.alias}.{exported}"
            localized = self._bind_imported_callable(
                exported, qualified, self.declarations.get(exported)
            )
            if contract.result.name == "Prop":
                self.checker.aliases[qualified] = CoreType(exported)
            members[exported] = localized.type
        self._import_namespace_types(declaration.alias, members)
        for exported in self.values:
            qualified = f"{declaration.alias}.{exported}"
            members[exported] = self.import_value(exported, qualified).type
        for exported, imported_tool in self.tools.items():
            qualified = f"{declaration.alias}.{exported}"
            members[exported] = imported_tool.type
            self._import_tool(exported, qualified)
        self.checker.module_members[declaration.alias] = members
        self.checker._bind(
            declaration.alias,
            CoreType("Module", (CoreType(declaration.alias),)),
            self.imported,
            declaration.span,
        )

    def _import_namespace_types(self, alias: str, members: dict[str, CoreType]) -> None:
        # Type tables include private dependencies for unification. Only names
        # bound in the source module belong to its namespace exports.
        for exported in self.imported.records:
            if exported not in self.checked.globals:
                continue
            self._import_record(exported, f"{alias}.{exported}", qualified=True)
            members[exported] = CoreType("Type")
        for exported in self.imported.aliases:
            if exported not in self.checked.globals:
                continue
            self._import_alias(exported, f"{alias}.{exported}", qualified=True)
            members[exported] = CoreType("Type")
        for exported in self.imported.variants:
            if exported not in self.checked.globals:
                continue
            self._import_variant(exported, f"{alias}.{exported}", qualified=True)
            members[exported] = CoreType("Type")
