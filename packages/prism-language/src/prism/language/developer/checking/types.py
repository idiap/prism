# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Type validation, unification, effects, and capability checks."""

from __future__ import annotations

import re
from typing import NoReturn

from prism.language.core import (
    PROTECTED_TYPES,
    BindingError,
    CoreType,
)
from prism.language.core import Binding as CoreBinding
from prism.language.effects import (
    SUPPORTED_EFFECTS,
    require_effects,
)
from prism.language.kernel import Term as KernelTerm

from ..core_elaboration import (
    CoreLocal,
    elaborate_type_text,
)
from ..diagnostics import Diagnostic, PrismTypeError, SourceSpan
from ..syntax.ast import (
    FunctionDecl,
    TheoremDecl,
    TypeExpr,
    WorkflowDecl,
)
from .base import _CheckerPhase
from .helpers import _dependent_assurance_binding


class _TypeCheckingMixin(_CheckerPhase):
    def _elaborate_kernel_type(
        self,
        syntax: TypeExpr,
        locals_: tuple[CoreLocal, ...] = (),
        seen: frozenset[str] = frozenset(),
    ) -> KernelTerm:
        """Elaborate source type syntax without rendering a nominal type back to text."""

        name = syntax.text.strip()
        if name.startswith("Proof[") and name.endswith("]"):
            return self._elaborate_kernel_type(
                TypeExpr(name[6:-1], syntax.span),
                locals_,
                seen,
            )
        alias = self.kernel_type_aliases.get(name)
        if alias is not None:
            if name in seen:
                raise ValueError(f"recursive kernel type alias `{name}`")
            return self._elaborate_kernel_type(alias, locals_, seen | {name})
        return elaborate_type_text(name, self.kernel_environment, locals_)

    def _protected_type(
        self,
        type_: CoreType,
        seen: frozenset[str] = frozenset(),
    ) -> str | None:
        """Find protected provenance or assurance inside an external payload."""

        if type_.name in PROTECTED_TYPES:
            return type_.name
        for argument in type_.arguments:
            protected = self._protected_type(argument, seen)
            if protected is not None:
                return protected
        for _, parameter in type_.parameters:
            protected = self._protected_type(parameter, seen)
            if protected is not None:
                return protected
        if type_.result is not None:
            protected = self._protected_type(type_.result, seen)
            if protected is not None:
                return protected
        if type_.name in seen:
            return None
        next_seen = seen | {type_.name}
        alias = self.aliases.get(type_.name)
        if alias is not None:
            protected = self._protected_type(alias, next_seen)
            if protected is not None:
                return protected
        record = self.records.get(type_.name)
        if record is not None:
            for field in record.fields:
                protected = self._protected_type(field.type, next_seen)
                if protected is not None:
                    return protected
        return None

    def _validate_type(
        self,
        type_: CoreType,
        span: SourceSpan,
        local_names: set[str],
    ) -> None:
        dependent = _dependent_assurance_binding(type_)
        if dependent is not None:
            binder, value_type, proposition = dependent
            self._validate_type(value_type, span, local_names)
            self._validate_type(proposition, span, local_names | {binder})
            return
        if type_.name == "Validated":
            self.fail(
                "Validated requires an exact value binder and specification, for "
                "example `Validated[value: A, Accepted(value)]`",
                span,
                "type-validated-dependent",
            )
        if type_.name == "Any":
            self.fail(
                "`Any` is not a Prism source type; declare a concrete type or "
                "preserve the type with a generic parameter",
                span,
                "type-any-forbidden",
            )
        if type_.is_function:
            unknown_effects = set(type_.effects) - SUPPORTED_EFFECTS
            if unknown_effects:
                self.fail(
                    f"unknown effects: {', '.join(sorted(unknown_effects))}",
                    span,
                    "type-unknown-effect",
                )
            for _, item in type_.parameters:
                self._validate_type(item, span, local_names)
            if type_.result:
                self._validate_type(type_.result, span, local_names)
            return
        declared_parameters = self.type_parameters.get(type_.name)
        if declared_parameters is not None and len(type_.arguments) != len(
            declared_parameters
        ):
            self.fail(
                f"type `{type_.name}` expects {len(declared_parameters)} type "
                f"arguments, got {len(type_.arguments)}",
                span,
                "type-arity",
            )
        if type_.name not in self.visible_types and type_.name not in local_names:
            callable_contract = self.callables.get(type_.name)
            if callable_contract is not None and (
                callable_contract.kind in {"reasoning", "relation"}
                or (
                    callable_contract.kind == "def"
                    and callable_contract.result is not None
                    and callable_contract.result.name == "Prop"
                    and not callable_contract.effects
                )
            ):
                pass
            elif type_.name.startswith("forall "):
                pass
            elif "(" in type_.name and type_.name.endswith(")"):
                base = type_.name.split("(", 1)[0]
                declared_callables = {
                    item.name
                    for item in self.program.declarations
                    if isinstance(
                        item,
                        FunctionDecl | WorkflowDecl | TheoremDecl,
                    )
                }
                if (
                    base not in self.callables
                    and base not in declared_callables
                    and base not in local_names
                ):
                    self.fail(
                        f"unknown proposition `{base}`",
                        span,
                        "type-unknown-proposition",
                    )
            else:
                self.fail(f"unknown type `{type_.name}`", span, "type-unknown-type")
        for item in type_.arguments:
            self._validate_type(item, span, local_names)

    def _validate_type_parameter_declarations(
        self, parameters: tuple[str, ...], span: SourceSpan, owner: str
    ) -> None:
        seen: set[str] = set()
        for parameter in parameters:
            if not re.fullmatch(r"[A-Za-z_]\w*", parameter):
                self.fail(
                    f"`{owner}` has invalid type parameter `{parameter}`",
                    span,
                    "type-parameter-declaration",
                )
            if parameter in seen:
                self.fail(
                    f"`{owner}` declares duplicate type parameter `{parameter}`",
                    span,
                    "type-parameter-duplicate",
                )
            if parameter in self.visible_types:
                self.fail(
                    f"type parameter `{parameter}` in `{owner}` shadows a declared type",
                    span,
                    "type-parameter-shadow",
                )
            seen.add(parameter)

    def _require_effects(self, declared, required, owner, span):
        try:
            require_effects(declared, required, owner)
        except ValueError as exc:
            self.fail(str(exc), span, "type-missing-effect")

    def _require_capabilities(
        self, parameters, effects, owner, scope=None, local_names=None
    ):
        capability_names = {
            self._type(item.type, local_names or set()).name for item in parameters
        }
        if scope is not None:
            capability_names.update(
                binding.type.name for binding in scope.snapshot().values()
            )
        mapping = {
            "AI.Generate": "ModelGenerate",
            "Context.Disclose": "ContextDisclose",
            "Data.Read": "DataRead",
            "File.Read": "FileRead",
            "Clock.Read": "ClockRead",
            "MCP.Call": "MCPCall",
            "Network.Request": "NetworkRequest",
            "Process.Run": "ProcessRun",
            "Python.Call": "PythonCall",
            "Tool.Call": "ToolCall",
        }
        for effect in effects:
            requirement = mapping.get(effect)
            if requirement and requirement not in capability_names:
                span = parameters[0].span if parameters else SourceSpan(1)
                self.fail(
                    f"`{owner}` declares {effect} but has no explicit {requirement} permission parameter",
                    span,
                    "type-missing-permission",
                )

    def _bind(self, name, type_, value, span):
        try:
            self.scope.bind(CoreBinding(name, type_, value))
        except BindingError as exc:
            self.fail(str(exc), span, "type-duplicate-binding")

    def _bind_local(self, scope, name, type_, span, value=None):
        try:
            scope.bind(CoreBinding(name, type_, value))
        except BindingError as exc:
            self.fail(str(exc), span, "type-duplicate-binding")

    def fail(self, message: str, span: SourceSpan, code: str) -> NoReturn:
        raise PrismTypeError(Diagnostic(message, span, code), self.program.path)
