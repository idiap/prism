# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Provider-free document checking service for Prism tooling."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from prism.language import check, elaborate, parse_source
from prism.language.developer import (
    PrismDiagnosticError,
    PrismSyntaxError,
    PrismTypeError,
)
from prism.language.developer.syntax import (
    CallExpr,
    FieldExpr,
    NameExpr,
    NodeOccurrence,
    ReasoningDecl,
)
from prism.sdk.workspace import WorkspaceModuleLoader, resolve_project_root
from prism.tooling.lsp.navigation import definition_at
from prism.tooling.lsp.semantic import build_semantic_index
from prism.tooling.lsp.symbols import build_symbol_index, build_type_index
from prism.tooling.protocol import (
    PrismIdeCheckResult,
    PrismIdeCompletionItem,
    PrismIdeDiagnostic,
)


class PrismLanguageService:
    def __init__(self, *, project_root: Path | None = None) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.modules = WorkspaceModuleLoader(project_root=self.project_root)
        self._module_loaders = {self.project_root: self.modules}

    def workspace_for(self, document_path: Path) -> tuple[Path, WorkspaceModuleLoader]:
        root = resolve_project_root(document_path, fallback=self.project_root)
        modules = self._module_loaders.get(root)
        if modules is None:
            modules = WorkspaceModuleLoader(project_root=root)
            self._module_loaders[root] = modules
        return root, modules

    def check_document(
        self, *, document_path: Path, document_text: str | None = None
    ) -> PrismIdeCheckResult:
        source = (
            document_text
            if document_text is not None
            else document_path.read_text(encoding="utf-8")
        )
        if document_path.suffix == ".prism-layout":
            error = ValueError(
                "`.prism-layout` is a document-layout file, not a Prism language program"
            )
            return PrismIdeCheckResult(
                status="invalid",
                document_path=str(document_path),
                diagnostics=[self.diagnostic(error, source)],
            )
        try:
            root, modules = self.workspace_for(document_path)
            program = parse_source(source, path=str(document_path))
            checked = check(program, modules=modules)
        except (PrismSyntaxError, PrismTypeError, ValueError) as exc:
            return PrismIdeCheckResult(
                status="invalid",
                document_path=str(document_path),
                diagnostics=[self.diagnostic(exc, source)],
            )
        return PrismIdeCheckResult(
            status="valid",
            document_path=str(document_path),
            symbols=build_symbol_index(
                program,
                checked.globals,
                callable_contracts=checked.callable_contracts,
                project_root=root,
            ),
            type_spans=build_type_index(program, elaborate(checked)),
            semantic_tokens=build_semantic_index(program),
            core_module={
                "format": checked.checked_module.core_format_version,
                "calculus": checked.checked_module.calculus_version,
                "hash": checked.checked_module.content_hash,
                "axioms": {
                    name: sorted(axioms)
                    for name, axioms in checked.checked_module.axiom_dependencies.items()
                },
            },
        )

    def checked_document(
        self, *, document_path: Path, document_text: str | None = None
    ):
        source = (
            document_text
            if document_text is not None
            else document_path.read_text(encoding="utf-8")
        )
        _, modules = self.workspace_for(document_path)
        program = parse_source(source, path=str(document_path))
        return check(program, modules=modules)

    def definition_at(
        self,
        *,
        document_path: Path,
        line: int,
        character: int,
        document_text: str | None = None,
    ):
        source = (
            document_text
            if document_text is not None
            else document_path.read_text(encoding="utf-8")
        )
        root, modules = self.workspace_for(document_path)
        program = parse_source(source, path=str(document_path))
        try:
            checked = check(program, modules=modules)
        except (PrismTypeError, ValueError):
            checked = None
            symbols = ()
        else:
            symbols = build_symbol_index(
                program,
                checked.globals,
                callable_contracts=checked.callable_contracts,
                project_root=root,
            )
        return definition_at(
            program,
            document_path=document_path,
            modules=modules,
            line=line,
            character=character,
            intrinsic_symbols=symbols,
            variants=checked.variants if checked is not None else None,
            reasoning_outputs=(
                checked.reasoning_outputs if checked is not None else None
            ),
            aliases=checked.aliases if checked is not None else None,
        )

    def completion_at(
        self,
        *,
        document_path: Path,
        line: int,
        character: int,
        document_text: str | None = None,
    ) -> list[PrismIdeCompletionItem]:
        source = (
            document_text
            if document_text is not None
            else document_path.read_text(encoding="utf-8")
        )
        lines = source.splitlines()
        if line < 0 or line >= len(lines):
            return []
        _, modules = self.workspace_for(document_path)
        configuration = self._reasoning_configuration_completions(
            source=source,
            document_path=document_path,
            line=line,
            character=character,
            modules=modules,
        )
        if configuration:
            return configuration
        receiver_match = re.search(
            r"([A-Za-z_]\w*)\.[A-Za-z_]*$", lines[line][:character]
        )
        if receiver_match is None:
            return []
        receiver = receiver_match.group(1)

        candidate_source = source
        try:
            program = parse_source(candidate_source, path=str(document_path))
            checked = check(program, modules=modules)
        except (PrismSyntaxError, PrismTypeError, ValueError):
            if not lines[line].lstrip().startswith("on "):
                return []
            sanitized = list(lines)
            sanitized[line] = ""
            candidate_source = "\n".join(sanitized)
            if source.endswith("\n"):
                candidate_source += "\n"
            try:
                program = parse_source(candidate_source, path=str(document_path))
                checked = check(program, modules=modules)
            except (PrismSyntaxError, PrismTypeError, ValueError):
                return []

        reasoning = self._reasoning_at(program, line)
        if reasoning is None:
            return []
        output = checked.reasoning_outputs.get(reasoning.name, {}).get(receiver)
        if output is None:
            return []
        resolved = checked.aliases.get(output.name, output)
        variants = checked.variants.get(output.name) or checked.variants.get(
            resolved.name, ()
        )
        result = [
            PrismIdeCompletionItem(
                label=constructor,
                kind="variant",
                detail=constructor,
                type_text=output.render(),
            )
            for constructor in variants
        ]
        record = checked.record_contracts.get(
            output.name
        ) or checked.record_contracts.get(resolved.name)
        if record is not None:
            substitutions = dict(
                zip(record.type_parameters, output.arguments, strict=False)
            )
            for field in record.fields:
                field_type = self._substitute(field.type, substitutions)
                if field_type.name == "Bool":
                    result.append(
                        PrismIdeCompletionItem(
                            label=field.name,
                            kind="field",
                            detail=f"{field.name}: {field_type.render()}",
                            type_text=output.render(),
                        )
                    )
        return sorted(result, key=lambda item: item.label)

    def _reasoning_configuration_completions(
        self,
        *,
        source: str,
        document_path: Path,
        line: int,
        character: int,
        modules: WorkspaceModuleLoader,
    ) -> list[PrismIdeCompletionItem]:
        """Complete configured-reasoning slots and compatible typed values."""

        current_program = self._parse_with_current_line_elided(
            source, document_path, line
        )
        if current_program is None:
            return []
        baseline_source = source
        try:
            baseline_program = parse_source(baseline_source, path=str(document_path))
            checked = check(baseline_program, modules=modules)
        except (PrismSyntaxError, PrismTypeError, ValueError):
            if not document_path.exists():
                return []
            baseline_source = document_path.read_text(encoding="utf-8")
            try:
                baseline_program = parse_source(
                    baseline_source, path=str(document_path)
                )
                checked = check(baseline_program, modules=modules)
            except (PrismSyntaxError, PrismTypeError, ValueError):
                return []

        call = self._call_at(current_program, line + 1, character)
        if call is None:
            return []
        reasoning_name = self._expression_name(call.callee)
        binding = checked.globals.get(reasoning_name)
        declaration = binding.value if binding is not None else None
        if not isinstance(declaration, ReasoningDecl):
            return []

        expected_names = self._reasoning_configuration_names(declaration, checked)
        supplied = {argument.name for argument in call.arguments if argument.name}
        baseline_call = next(
            (
                candidate
                for candidate in self._calls(baseline_program)
                if self._expression_name(candidate.callee) == reasoning_name
                and {
                    argument.name for argument in candidate.arguments if argument.name
                }.issuperset(supplied)
            ),
            None,
        )
        expected_types = (
            {
                argument.name: checked.expression_types.get(id(argument.value))
                for argument in baseline_call.arguments
                if argument.name
            }
            if baseline_call is not None
            else {}
        )

        prefix = source.splitlines()[line][:character]
        value_match = re.search(r"([A-Za-z_]\w*)\s*=\s*[A-Za-z_\w.]*$", prefix)
        if value_match is not None:
            slot = value_match.group(1)
            if slot not in expected_names:
                return []
            expected_type = expected_types.get(slot)
            if expected_type is None:
                return []
            return sorted(
                (
                    PrismIdeCompletionItem(
                        label=name,
                        kind="field",
                        detail=f"{name}: {candidate.type.render()}",
                        type_text=candidate.type.render(),
                    )
                    for name, candidate in checked.globals.items()
                    if candidate.type == expected_type
                ),
                key=lambda item: item.label,
            )

        result = []
        for name in expected_names:
            if name in supplied:
                continue
            expected_type = expected_types.get(name)
            rendered = expected_type.render() if expected_type is not None else ""
            result.append(
                PrismIdeCompletionItem(
                    label=name,
                    kind="field",
                    detail=f"{name}: {rendered}" if rendered else name,
                    type_text=rendered,
                )
            )
        return result

    @staticmethod
    def _parse_with_current_line_elided(source: str, document_path: Path, line: int):
        candidates = [source]
        lines = source.splitlines()
        if 0 <= line < len(lines):
            sanitized = list(lines)
            sanitized[line] = ""
            candidate = "\n".join(sanitized)
            if source.endswith("\n"):
                candidate += "\n"
            candidates.append(candidate)
        for candidate in candidates:
            try:
                return parse_source(candidate, path=str(document_path))
            except PrismSyntaxError:
                continue
        return None

    @classmethod
    def _call_at(cls, program, one_based_line: int, character: int) -> CallExpr | None:
        def contains(call: CallExpr) -> bool:
            end_line = call.span.end_line or call.span.line
            end_column = call.span.end_column or call.span.column
            return (
                call.span.line < one_based_line < end_line
                or (
                    call.span.line == one_based_line
                    and end_line == one_based_line
                    and call.span.column <= character <= end_column
                )
                or (
                    call.span.line == one_based_line < end_line
                    and character >= call.span.column
                )
                or (
                    call.span.line < one_based_line == end_line
                    and character <= end_column
                )
            )

        def size(call: CallExpr) -> tuple[int, int]:
            end_line = call.span.end_line or call.span.line
            end_column = call.span.end_column or call.span.column
            return end_line - call.span.line, end_column - call.span.column

        calls = [call for call in cls._calls(program) if contains(call)]
        return min(calls, key=size, default=None)

    @staticmethod
    def _calls(value) -> list[CallExpr]:
        result: list[CallExpr] = []

        def visit(item) -> None:
            if isinstance(item, CallExpr):
                result.append(item)
            if dataclasses.is_dataclass(item):
                for field in dataclasses.fields(item):
                    if field.name != "span":
                        visit(getattr(item, field.name))
            elif isinstance(item, (tuple, list)):
                for child in item:
                    visit(child)

        visit(value)
        return result

    @classmethod
    def _expression_name(cls, expression) -> str:
        if isinstance(expression, NameExpr):
            return expression.name
        if isinstance(expression, FieldExpr):
            owner = cls._expression_name(expression.value)
            return f"{owner}.{expression.field}" if owner else expression.field
        return ""

    @classmethod
    def _reasoning_configuration_names(
        cls, declaration: ReasoningDecl, checked=None
    ) -> tuple[str, ...]:
        nodes: list[NodeOccurrence] = []

        def visit(composition) -> None:
            if isinstance(composition, NodeOccurrence):
                nodes.append(composition)
                return
            router = getattr(composition, "router", None)
            if router is not None:
                visit(router)
            for child in getattr(composition, "children", ()):
                visit(child)
            for arm in getattr(composition, "arms", ()):
                for child in arm.children:
                    visit(child)

        visit(declaration.composition)
        occurrences = tuple(node.alias for node in nodes if node.alias)
        method_contracts = (
            checked.reasoning_methods.get(declaration.name, {})
            if checked is not None
            else {}
        )
        inputs = tuple(
            f"{node.alias}_input"
            for node in nodes
            if checked is not None
            and node.alias
            and isinstance(node.component, CallExpr)
            and node.component.arguments
            and node.alias in method_contracts
            and method_contracts[node.alias].parameters
            and cls._expand_aliases(
                checked.expression_types.get(id(node.component.arguments[0].value)),
                checked,
            )
            != cls._expand_aliases(
                method_contracts[node.alias].parameters[0][1],
                checked,
            )
        )
        relations = tuple(
            f"{node.alias}_by" for node in nodes if node.alias and node.relation
        )
        switches = tuple(
            dict.fromkeys(
                exit_.target.rsplit(".", 1)[-1]
                for exit_ in declaration.exits
                if exit_.action == "switch" and exit_.target
            )
        )
        return (*occurrences, *inputs, *relations, *switches)

    @classmethod
    def _expand_aliases(cls, type_, checked, seen=frozenset()):
        if type_ is None:
            return None
        if type_.name in checked.aliases and type_.name not in seen:
            parameters = checked.type_parameters.get(type_.name, ())
            if len(parameters) == len(type_.arguments):
                expanded = cls._substitute(
                    checked.aliases[type_.name],
                    dict(zip(parameters, type_.arguments, strict=True)),
                )
                return cls._expand_aliases(expanded, checked, seen | {type_.name})
        if type_.is_function:
            return dataclasses.replace(
                type_,
                parameters=tuple(
                    (name, cls._expand_aliases(item, checked, seen))
                    for name, item in type_.parameters
                ),
                result=(
                    cls._expand_aliases(type_.result, checked, seen)
                    if type_.result is not None
                    else None
                ),
            )
        return dataclasses.replace(
            type_,
            arguments=tuple(
                cls._expand_aliases(item, checked, seen) for item in type_.arguments
            ),
        )

    @staticmethod
    def _reasoning_at(program, zero_based_line: int) -> ReasoningDecl | None:
        declarations = program.declarations
        for index, declaration in enumerate(declarations):
            if not isinstance(declaration, ReasoningDecl):
                continue
            next_line = (
                declarations[index + 1].span.line - 1
                if index + 1 < len(declarations)
                else len(program.source.splitlines())
            )
            if declaration.span.line - 1 <= zero_based_line < next_line:
                return declaration
        return None

    @classmethod
    def _substitute(cls, type_, substitutions):
        from prism.language.core import CoreType

        if (
            type_.name in substitutions
            and not type_.arguments
            and not type_.is_function
        ):
            return substitutions[type_.name]
        if type_.is_function:
            return CoreType(
                type_.name,
                parameters=tuple(
                    (name, cls._substitute(item, substitutions))
                    for name, item in type_.parameters
                ),
                result=(
                    cls._substitute(type_.result, substitutions)
                    if type_.result is not None
                    else None
                ),
                effects=type_.effects,
            )
        return CoreType(
            type_.name,
            tuple(cls._substitute(item, substitutions) for item in type_.arguments),
        )

    def diagnostic(self, error: BaseException, source: str) -> PrismIdeDiagnostic:
        text = str(error)
        diagnostic = (
            error.diagnostic if isinstance(error, PrismDiagnosticError) else None
        )
        line_number = diagnostic.span.line if diagnostic else None
        message = diagnostic.message if diagnostic else text
        line_index = line_number - 1 if line_number is not None else None
        lines = source.splitlines()
        source_line = (
            lines[line_index]
            if line_index is not None and 0 <= line_index < len(lines)
            else ""
        )
        return PrismIdeDiagnostic(
            code=error.__class__.__name__,
            severity="error",
            message=message,
            line=line_index,
            character=0 if line_index is not None else None,
            end_line=line_index,
            end_character=len(source_line) if source_line else None,
            line_text=source_line,
        )
