# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Admission of pure bindings and functions into the proof kernel."""

from __future__ import annotations

from dataclasses import replace

from prism.language.kernel import PROP as KERNEL_PROP
from prism.language.kernel import (
    Const,
    KernelError,
    check_declaration,
)
from prism.language.kernel import Declaration as KernelDeclaration
from prism.language.kernel import Lam as KernelLam
from prism.language.kernel import Pi as KernelPi
from prism.language.kernel import Term as KernelTerm

from ...core_elaboration import CoreLocal
from ...core_elaboration import elaborate_expression as elaborate_core_expression
from ...syntax.ast import (
    Binding,
    FunctionDecl,
    Return,
)
from ..base import _CheckerPhase


class _CoreAdmissionMixin(_CheckerPhase):
    def _admit_core_definitions(self) -> None:
        """Admit the pure, total surface subset that can occur in proofs."""

        for declaration in self.program.declarations:
            try:
                if isinstance(declaration, Binding):
                    self._admit_core_binding(declaration)
                elif isinstance(declaration, FunctionDecl):
                    self._admit_core_function(declaration)
            except (KernelError, ValueError):
                # Non-proof callables remain ordinary effect/runtime contracts.
                # A later strict declaration that references one fails closed.
                continue

    def _admit_core_binding(self, declaration: Binding) -> None:
        if declaration.annotation is None:
            return
        binding_type = self._elaborate_kernel_type(declaration.annotation)
        if self._type(declaration.annotation).name not in {"Nat", "Bool"}:
            return
        binding_value = elaborate_core_expression(
            declaration.value, self.kernel_environment, symbols=self.native_names
        )
        admitted_binding = KernelDeclaration(
            declaration.name,
            binding_type,
            binding_value,
            "definition",
        )
        self._admit_native_declaration(admitted_binding)
        self.expression_terms[id(declaration.value)] = binding_value

    def _admit_core_function(self, declaration: FunctionDecl) -> None:
        if declaration.effects:
            return
        contract = self.callables[declaration.name]
        if contract.result.name not in {"Nat", "Bool", "Prop"}:
            return
        if any(item.type.name not in {"Nat", "Bool"} for item in contract.parameters):
            return
        returns = [item for item in declaration.body if isinstance(item, Return)]
        if len(returns) != 1 or len(declaration.body) != 1:
            return
        locals_: tuple[CoreLocal, ...] = ()
        parameter_terms: list[tuple[str, KernelTerm]] = []
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
            returns[0].value, self.kernel_environment, locals_, self.native_names
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
        self._admit_native_declaration(admitted)
        self.expression_terms[id(returns[0].value)] = value

    def _admit_native_declaration(self, declaration):
        identity = self._symbol_identity(declaration.name)
        canonical = replace(declaration, name=identity)
        self.kernel_environment = check_declaration(self.kernel_environment, canonical)
        self.kernel_declarations.append(self.kernel_environment.get(identity))
        self.native_names[declaration.name] = identity
        try:
            self.kernel_environment.get(declaration.name)
        except KernelError:
            alias = replace(declaration, value=Const(identity))
            self.kernel_environment = check_declaration(self.kernel_environment, alias)
            self.kernel_declarations.append(
                self.kernel_environment.get(declaration.name)
            )
