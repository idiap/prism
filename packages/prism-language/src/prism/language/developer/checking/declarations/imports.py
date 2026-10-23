# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Module loading, cycle detection, and imported checker state."""

from __future__ import annotations

import hashlib

from prism.language.kernel import Declaration as KernelDeclaration
from prism.language.kernel import (
    KernelError,
    check_declaration,
)

from ...syntax.ast import (
    ImportDecl,
    ModuleImportDecl,
)
from ...syntax.parser import parse_source
from ..base import _CheckerPhase
from .module_imports import _ModuleImports


class _ImportCheckingMixin(_CheckerPhase):
    def _load_imports(self) -> None:
        explicit_import_names = {
            alias or exported
            for item in self.program.declarations
            if isinstance(item, ImportDecl)
            for exported, alias in item.names
        }
        for declaration in self.program.declarations:
            if isinstance(declaration, ImportDecl | ModuleImportDecl):
                self._load_import(declaration, explicit_import_names)

    def _load_import(
        self,
        declaration: ImportDecl | ModuleImportDecl,
        explicit_import_names: set[str],
    ) -> None:
        from .checker import _Checker

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
        self.expression_proof_bindings.update(
            imported_checked.expression_proof_bindings
        )
        self._merge_imported_kernel(imported.kernel_declarations)
        self.expression_types.update(imported_checked.expression_types)
        self.occurrence_contracts.update(imported_checked.occurrence_contracts)
        self.method_classifications.update(imported_checked.method_classifications)
        self.module_hashes.update(imported_checked.module_hashes)
        self.module_hashes[declaration.module] = hashlib.sha256(
            source.source.encode()
        ).hexdigest()
        self.known_types.update(imported.known_types)
        self.records.update(imported.records)
        self.aliases.update(imported.aliases)
        self.variants.update(imported.variants)
        exports = _ModuleImports(
            self, imported, imported_checked, declaration, explicit_import_names
        )
        if isinstance(declaration, ImportDecl):
            exports.import_names(declaration)
        else:
            exports.import_namespace(declaration)

    def _merge_imported_kernel(self, declarations: list[KernelDeclaration]) -> None:
        for core_declaration in declarations:
            try:
                self.kernel_environment.get(core_declaration.name)
            except KernelError:
                self.kernel_environment = check_declaration(
                    self.kernel_environment, core_declaration
                )
                self.kernel_declarations.append(core_declaration)
