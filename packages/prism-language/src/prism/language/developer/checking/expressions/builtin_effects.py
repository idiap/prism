# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in effects operations."""

from __future__ import annotations

from prism.language.core import CoreType

from ..base import _CheckerPhase
from .builtin_context import _BuiltinCall


class _BuiltinEffectsMixin(_CheckerPhase):
    def _builtin_generate(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "`generate` requires one explicit output type, for example "
                "`generate[Assessment](request, model, model_access)`",
                call.expression.span,
                "type-generate-output",
            )
        call.require_positional(3)
        if call.named:
            self.fail(
                f"`generate` has unknown named arguments: {', '.join(sorted(call.named))}",
                call.expression.span,
                "type-builtin-argument",
            )
        call.expect_argument(1, CoreType("Model"), "generation model")
        call.expect_argument(2, CoreType("ModelGenerate"), "generation permission")
        value = self._type(call.expression.type_arguments[0])
        protected = self._protected_type(value)
        if protected is not None:
            self.fail(
                f"`generate` payloads cannot contain protected type `{protected}`",
                call.expression.span,
                "type-generate-protected-payload",
            )
        return CoreType(
            "Result", (CoreType("Generated", (value,)), CoreType("ModelFailure"))
        ), ("AI.Generate",)

    def _builtin_query(self, call: _BuiltinCall) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(4)
        source = (
            call.positional[0]
            if call.positional
            else CoreType("Source", (CoreType("Any"),))
        )
        if source.name not in {"Source", "GraphSource"}:
            self.fail(
                "query requires a Source or GraphSource",
                call.expression.span,
                "type-source-input",
            )
        call.expect_argument(2, CoreType("DataRead"), "source read permission")
        call.expect_argument(3, CoreType("ClockRead"), "source clock permission")
        payload = source.arguments[0] if source.arguments else CoreType("Any")
        return CoreType(
            "Result", (CoreType("Evidence", (payload,)), CoreType("SourceError"))
        ), ("Data.Read", "Clock.Read")

    def _builtin_resource_evidence(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(3)
        resource = (
            call.positional[0]
            if call.positional
            else CoreType("Resource", (CoreType("Any"),))
        )
        if resource.name != "Resource":
            self.fail(
                "resource_evidence requires a Resource",
                call.expression.span,
                "type-resource-input",
            )
        call.expect_argument(1, CoreType("FileRead"), "resource read permission")
        call.expect_argument(2, CoreType("ClockRead"), "resource clock permission")
        payload = resource.arguments[0] if resource.arguments else CoreType("Any")
        return CoreType(
            "Result", (CoreType("Evidence", (payload,)), CoreType("SourceError"))
        ), ("File.Read", "Clock.Read")

    def _builtin_python_call(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(3)
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "python_call requires one result type argument",
                call.expression.span,
                "type-python-call-result",
            )
        call.expect_argument(0, CoreType("String"), "Python operation")
        call.expect_argument(2, CoreType("PythonCall"), "Python permission")
        result = self._type(call.expression.type_arguments[0])
        protected = self._protected_type(result)
        if protected is not None:
            self.fail(
                "`python_call` cannot produce protected type "
                f"`{protected}`; use its typed introduction operation",
                call.expression.span,
                "type-python-call-protected",
            )
        return CoreType("Result", (result, CoreType("PythonError"))), ("Python.Call",)

    def _builtin_tool_call(
        self, call: _BuiltinCall
    ) -> tuple[CoreType, tuple[str, ...]]:
        call.require_positional(4)
        if len(call.expression.type_arguments) != 1:
            self.fail(
                "tool_call requires one result type argument",
                call.expression.span,
                "type-tool-call-result",
            )
        call.expect_argument(0, CoreType("String"), "tool operation")
        if call.positional[2].name != "Connection":
            self.fail(
                "tool_call requires a typed Connection",
                call.expression.span,
                "type-tool-call-connection",
            )
        call.expect_argument(3, CoreType("ToolCall"), "tool permission")
        result = self._type(call.expression.type_arguments[0])
        protected = self._protected_type(result)
        if protected is not None:
            self.fail(
                "`tool_call` cannot produce protected type "
                f"`{protected}`; use its typed introduction operation",
                call.expression.span,
                "type-tool-call-protected",
            )
        return CoreType("Result", (result, CoreType("ToolError"))), ("Tool.Call",)
