# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Parser for the reduced canonical Prism syntax."""

from __future__ import annotations

import re
from dataclasses import replace

from prism.language.developer.diagnostics import (
    Diagnostic,
    PrismSyntaxError,
    SourceSpan,
)

from .ast import (
    AgentDecl,
    Binding,
    CallArgument,
    CallExpr,
    ChoiceArm,
    ChoiceComposition,
    Composition,
    Exact,
    ExpressionStatement,
    FunctionDecl,
    GuardedExit,
    ImportDecl,
    MethodMetadata,
    ModuleImportDecl,
    NodeOccurrence,
    OccurrenceConstraint,
    ParallelComposition,
    Parameter,
    Program,
    ReasoningDecl,
    RelationDecl,
    RepeatComposition,
    Return,
    SequenceComposition,
    TheoremDecl,
    ToolDecl,
    TypeDecl,
    TypeExpr,
    TypeField,
    WorkflowDecl,
)
from .expressions import _convert_operator_expression as _convert_operator_expression
from .expressions import _convert_python_expression as _convert_python_expression
from .expressions import _python_character_offset as _python_character_offset
from .expressions import _python_node_span as _python_node_span
from .expressions import _span_from_positions as _span_from_positions
from .expressions import _syntax_error_span as _syntax_error_span
from .expressions import _trimmed_slice as _trimmed_slice
from .expressions import _unsupported_expression as _unsupported_expression
from .expressions import parse_expression as parse_expression
from .lexer import tokenize
from .text import _matching_square as _matching_square
from .text import find_top_level as find_top_level
from .text import matching_delimiter as matching_delimiter
from .text import split_top_level as split_top_level
from .tokens import Token, TokenKind

REMOVED_FORMS = {
    "structure": "replace `structure` with a `type Name:` record",
    "assume": "replace `assume` with an explicitly typed immutable record value",
    "claim": "replace `claim` with a typed value or proposition function",
    "expr": "replace `expr` with an ordinary typed immutable binding",
    "equation": "replace `equation` with an ordinary typed immutable binding",
    "doc": "replace `doc` with `name: Resource[T] = embed(path)`",
    "kb": "replace `kb` with a typed `Source[T]` or `GraphSource[T]` binding",
    "tactic": "replace `tactic` with a typed function returning proof syntax or a core term",
    "derive": "replace `derive` with a typed function or workflow component",
    "have": "replace `have` with an ordinary immutable binding",
    "repeat": "`repeat` is legal only as a bounded workflow composition",
    "require": "replace `require |~` with a typed policy result propagated through `Result`",
    "run": "replace `run` with an ordinary typed function call",
    "apply": "replace `apply` with an ordinary typed prover call",
    "invoke": "replace `invoke` with a direct agent or workflow call",
    "step": "`step` was removed; use a bracketed workflow node occurrence",
    "after": "`after` was removed; express dependencies with workflow topology",
    "reasoning_method": "replace `reasoning_method` with a descriptive `type` declaration",
}


def parse_source(source: str, path: str | None = None) -> Program:
    if path and path.endswith(".prism-layout"):
        raise PrismSyntaxError(
            Diagnostic(
                "`.prism-layout` is not supported by the Prism language frontend",
                SourceSpan(1, 1),
                "syntax-layout-profile",
            ),
            path,
        )
    return _Parser(tokenize(source, path=path), source, path).parse()


class _Parser:
    def __init__(
        self, tokens: tuple[Token, ...], source: str, path: str | None
    ) -> None:
        self.tokens = tokens
        self.source = source
        self.path = path
        self.index = 0

    def parse(self) -> Program:
        declarations: list[object] = []
        while self.current.kind != TokenKind.EOF:
            if self.current.kind in {TokenKind.INDENT, TokenKind.DEDENT}:
                self.fail(
                    "unexpected layout token", self.current, "layout-unexpected-token"
                )
            declaration = self.parse_declaration()
            if isinstance(declaration, tuple):
                declarations.extend(declaration)
            else:
                declarations.append(declaration)
        return Program(tuple(declarations), self.source, self.path)  # type: ignore[arg-type]

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def parse_declaration(self):
        token = self.advance()
        line = token.value
        if line.startswith("skill "):
            self.fail(
                "native `skill` declarations were removed; build the Open Agent "
                "Skill into a typed module and import its `Skill[Task]` export",
                token,
                "removed-skill-declaration",
            )
        first = _removed_form(line)
        if first is not None:
            self.fail(REMOVED_FORMS[first], token, f"removed-{first}")
        parsers = {
            "from": self.parse_from_import,
            "import": self.parse_module_import,
            "type": self.parse_type,
            "def": self.parse_function,
            "workflow": self.parse_workflow,
            "reasoning": self.parse_reasoning,
            "relation": self.parse_relation,
            "agent": self.parse_agent,
            "tool": self.parse_tool,
            "theorem": self.parse_theorem,
        }
        keyword, separator, _ = line.partition(" ")
        parser = parsers.get(keyword) if separator else None
        return (parser or self.parse_binding_line)(line, token)

    def parse_from_import(self, line: str, token: Token) -> ImportDecl:
        match = re.fullmatch(r"from\s+([A-Za-z_][\w.]*)\s+import\s+(.+)", line)
        if not match:
            self.fail("invalid absolute from-import", token, "syntax-import")
        imported_names = match.group(2).strip()
        if imported_names.startswith("("):
            if not imported_names.endswith(")"):
                self.fail(
                    "parenthesized import list must end with `)`",
                    token,
                    "syntax-import",
                )
            imported_names = imported_names[1:-1].strip()
        if not imported_names:
            self.fail(
                "from-import requires at least one imported name",
                token,
                "syntax-import-name",
            )

        items = list(split_top_level(imported_names, keep_empty=True))
        if items and not items[-1]:
            items.pop()
        if any(not item for item in items):
            self.fail(
                "import list contains an empty imported name",
                token,
                "syntax-import-name",
            )
        if not items:
            self.fail(
                "from-import requires at least one imported name",
                token,
                "syntax-import-name",
            )

        return ImportDecl(
            match.group(1), self._parse_import_names(items, token), token.span
        )

    def parse_module_import(self, line: str, token: Token) -> ModuleImportDecl:
        match = re.fullmatch(r"import\s+([A-Za-z_][\w.]*)\s+as\s+([A-Za-z_]\w*)", line)
        if not match:
            self.fail(
                "module imports require `import module as alias`",
                token,
                "syntax-import",
            )
        return ModuleImportDecl(match.group(1), match.group(2), token.span)

    def parse_type(self, line: str, token: Token) -> TypeDecl:
        metadata = (
            self._parse_method_metadata(token) if line.endswith(" with:") else None
        )
        alias = self._parse_type_alias(line.removesuffix(" with:"), token)
        if alias is not None:
            return replace(
                alias, metadata=metadata, span=metadata.span if metadata else alias.span
            )
        if metadata is not None:
            self.fail(
                "method metadata requires a function-type alias",
                token,
                "syntax-method-metadata",
            )
        header = re.fullmatch(r"type\s+([A-Za-z_]\w*)(?:\[([^]]+)\])?:", line)
        if not header:
            self.fail("invalid type declaration", token, "syntax-type")
        children = self.take_suite(token)
        fields: list[TypeField] = []
        alternatives: list[str] = []
        alternative_spans: list[SourceSpan] = []
        for child in children:
            if child.kind != TokenKind.LINE:
                self.fail(
                    "nested suites are not supported in a record type",
                    child,
                    "syntax-type-field",
                )
            if child.value.startswith("|"):
                alternatives.append(child.value[1:].strip())
                alternative_spans.append(child.span)
                continue
            match = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(.+)", child.value)
            if not match:
                self.fail(
                    "record fields require `name: Type`", child, "syntax-type-field"
                )
            fields.append(
                TypeField(
                    match.group(1), TypeExpr(match.group(2), child.span), child.span
                )
            )
        if fields and alternatives:
            self.fail(
                "a type cannot mix record fields and variants",
                token,
                "syntax-type-mixed",
            )
        return TypeDecl(
            header.group(1),
            tuple(fields),
            token.span,
            _parse_type_parameters(header.group(2)),
            tuple(alternatives),
            alternative_spans=tuple(alternative_spans),
        )

    def parse_function(self, line: str, token: Token) -> FunctionDecl:
        is_proposition_declaration = not line.endswith(":")
        name, type_params, params, result, effects = self.parse_callable_header(
            f"{line}:" if is_proposition_declaration else line, "def", token
        )
        if is_proposition_declaration:
            if result.text != "Prop" or effects:
                self.fail(
                    "only a pure function returning `Prop` may omit its body",
                    token,
                    "syntax-proposition-declaration",
                )
            body = ()
        else:
            body = self.parse_statements(self.take_suite_tokens(token))
        return FunctionDecl(
            name,
            params,
            result,
            body,
            token.span,
            effects,
            type_params,
            is_proposition_declaration,
        )

    def parse_workflow(self, line: str, token: Token) -> WorkflowDecl:
        name, type_params, params, result, effects = self.parse_callable_header(
            line, "workflow", token
        )
        failure_marker = find_top_level(result.text, " fails ")
        if failure_marker >= 0:
            failure_text = result.text[failure_marker + len(" fails ") :].strip()
            result_text = result.text[:failure_marker].strip()
            if not failure_text:
                self.fail(
                    "`fails` requires a closed failure type",
                    token,
                    "syntax-workflow-failure",
                )
            result = TypeExpr(result_text, token.span)
            failure = TypeExpr(failure_text, token.span)
        else:
            failure = TypeExpr("Never", token.span)
        composition, result_alias = _WorkflowParser(
            self.take_suite_tokens(token), self.path
        ).parse()
        return WorkflowDecl(
            name,
            params,
            result,
            failure,
            composition,
            result_alias,
            token.span,
            effects,
            type_params,
        )

    def parse_reasoning(self, line: str, token: Token) -> ReasoningDecl:
        if " fails " in line:
            self.fail(
                "reasoning declarations cannot declare failures",
                token,
                "syntax-reasoning-failure",
            )
        name, type_params, params, result, effects = self.parse_callable_header(
            line, "reasoning", token
        )
        if effects:
            self.fail(
                "reasoning declarations cannot declare effects",
                token,
                "syntax-reasoning-effect",
            )
        composition, exits, result_alias = _ReasoningParser(
            self.take_suite_tokens(token), self.path
        ).parse()
        return ReasoningDecl(
            name,
            params,
            result,
            composition,
            exits,
            result_alias,
            token.span,
            type_params,
        )

    def parse_relation(self, line: str, token: Token) -> RelationDecl:
        if line.endswith(":"):
            self.fail(
                "relation declarations are contracts and cannot have a suite",
                token,
                "syntax-relation-suite",
            )
        line = _desugar_relation_judgment(line, token, self)
        name, type_params, params, result, effects = self.parse_callable_header(
            f"{line}:", "relation", token
        )
        if effects:
            self.fail(
                "relation declarations must be pure",
                token,
                "syntax-relation-effect",
            )
        return RelationDecl(name, params, result, token.span, type_params)

    def parse_agent(self, line: str, token: Token) -> AgentDecl:
        name, _, parameters, result, effects = self.parse_callable_header(
            line, "agent", token
        )
        statements = (
            self.parse_statements(self.take_suite_tokens(token))
            if self.current.kind == TokenKind.INDENT
            else ()
        )
        capabilities: list[Binding] = []
        seen: set[str] = set()
        for statement in statements:
            if not isinstance(statement, Binding) or statement.name not in {
                "tools",
                "skills",
                "hooks",
            }:
                self.fail(
                    "agent suites contain only typed `tools`, `skills`, and `hooks` bindings",
                    token,
                    "syntax-agent-capability",
                )
            if statement.annotation is None:
                self.fail(
                    f"agent capability `{statement.name}` requires an explicit type",
                    token,
                    "syntax-agent-capability-type",
                )
            if statement.name in seen:
                self.fail(
                    f"duplicate agent capability `{statement.name}`",
                    token,
                    "syntax-agent-capability",
                )
            seen.add(statement.name)
            capabilities.append(statement)
        return AgentDecl(
            name, parameters, result, tuple(capabilities), token.span, effects
        )

    def parse_tool(self, line: str, token: Token) -> ToolDecl:
        equal = find_top_level(line, "=")
        if equal < 0:
            self.fail(
                "tool declarations use `tool name: Tool[Contract] = callable`",
                token,
                "syntax-tool",
            )
        left = line[len("tool ") : equal].strip()
        right = line[equal + 1 :].strip()
        match = re.fullmatch(r"([A-Za-z_]\w*)\s*:\s*(Tool\[.+\])", left)
        if match is None or not right:
            self.fail(
                "tool declarations use `tool name: Tool[Contract] = callable`",
                token,
                "syntax-tool",
            )
        return ToolDecl(
            match.group(1),
            TypeExpr(match.group(2), token.span),
            parse_expression(right, token.span, self.path),
            token.span,
        )

    def parse_theorem(self, line: str, token: Token) -> TheoremDecl:
        if not line.endswith(":"):
            self.fail(
                "theorem declaration must open an indented proof suite",
                token,
                "syntax-theorem",
            )
        content = line[len("theorem ") : -1].strip()
        if content.endswith(" by") and ":= by" in content:
            content = content[: -len(" := by")]
        paren = content.find("(")
        if paren < 1:
            self.fail(
                "theorem requires a name and typed parameters", token, "syntax-theorem"
            )
        close = matching_delimiter(content, paren)
        name = content[:paren].strip()
        params = parse_parameters(content[paren + 1 : close], token.span, self)
        judgment = content[close + 1 :].strip()
        if judgment.startswith(":"):
            judgment = judgment[1:].strip()
        split = _split_strict_judgment(judgment)
        if split is None:
            self.fail(
                "theorem statement requires `{premises} |- proposition`",
                token,
                "syntax-theorem-judgment",
            )
        premises, conclusion = split
        body = self.parse_statements(self.take_suite_tokens(token))
        return TheoremDecl(name, params, premises, conclusion, body, token.span)

    def parse_callable_header(
        self, line: str, keyword: str, token: Token
    ) -> tuple[str, tuple[str, ...], tuple[Parameter, ...], TypeExpr, tuple[str, ...]]:
        if not line.endswith(":"):
            self.fail(
                f"`{keyword}` declaration must end in `:`", token, f"syntax-{keyword}"
            )
        content = line[len(keyword) : -1].strip()
        match = re.match(
            r"([A-Za-z_]\w*)(?:\[([^]]+)\])?",
            content,
        )
        if not match:
            self.fail(f"invalid {keyword} name", token, f"syntax-{keyword}")
        name = match.group(1)
        type_params = _parse_type_parameters(match.group(2))
        rest = content[match.end() :].strip()
        if rest.startswith("("):
            close = matching_delimiter(rest, 0)
            params_text = rest[1:close]
            rest = rest[close + 1 :].strip()
        else:
            self.fail(
                f"`{keyword}` requires a parameter list",
                token,
                f"syntax-{keyword}-parameters",
            )
        if not rest.startswith("->"):
            self.fail(
                f"`{keyword}` requires an explicit result type",
                token,
                f"syntax-{keyword}-result",
            )
        result_text = rest[2:].strip()
        result_text, effects = _take_effect_row(result_text, token, self)
        if not result_text:
            self.fail("missing result type", token, f"syntax-{keyword}-result")
        return (
            name,
            type_params,
            parse_parameters(params_text, token.span, self),
            TypeExpr(result_text, token.span),
            effects,
        )

    def parse_statements(self, tokens: tuple[Token, ...]):
        parser = _StatementParser(tokens, self.path)
        return parser.parse()

    def parse_binding_line(self, line: str, token: Token) -> Binding:
        equal = find_top_level(line, "=")
        if equal < 0:
            self.fail(
                "expected a declaration or immutable binding",
                token,
                "syntax-declaration",
            )
        if equal + 1 < len(line) and line[equal + 1] == "=":
            self.fail(
                "top-level expressions must be bound to a name", token, "syntax-binding"
            )
        left, _ = _trimmed_slice(line, token.source_positions, 0, equal)
        right, right_positions = _trimmed_slice(line, token.source_positions, equal + 1)
        match = re.fullmatch(r"([A-Za-z_]\w*)(?:\s*:\s*(.+))?", left)
        if not match or not right:
            self.fail(
                "immutable bindings use `name[: Type] = expression`",
                token,
                "syntax-binding",
            )
        annotation = TypeExpr(match.group(2), token.span) if match.group(2) else None
        return Binding(
            match.group(1),
            parse_expression(
                right,
                token.span,
                self.path,
                source_positions=right_positions,
            ),
            token.span,
            annotation,
        )

    def take_suite(self, opener: Token) -> tuple[Token, ...]:
        return tuple(
            token
            for token in self.take_suite_tokens(opener)
            if token.kind == TokenKind.LINE
        )

    def take_suite_tokens(self, opener: Token) -> tuple[Token, ...]:
        if self.current.kind != TokenKind.INDENT:
            self.fail("expected an indented suite", opener, "layout-missing-suite")
        self.advance()
        depth = 1
        result: list[Token] = []
        while depth:
            token = self.advance()
            if token.kind == TokenKind.EOF:
                self.fail("unterminated suite", opener, "layout-unterminated-suite")
            if token.kind == TokenKind.INDENT:
                depth += 1
            elif token.kind == TokenKind.DEDENT:
                depth -= 1
                if depth == 0:
                    break
            result.append(token)
        return tuple(result)

    def fail(self, message: str, token: Token, code: str):
        raise PrismSyntaxError(Diagnostic(message, token.span, code), self.path)

    def _parse_import_names(self, items, token):
        names = []
        for item in items:
            name_match = re.fullmatch(
                r"([A-Za-z_]\w*)(?:\s+as\s+([A-Za-z_]\w*))?", item
            )
            if not name_match:
                self.fail(
                    f"invalid imported name `{item}`", token, "syntax-import-name"
                )
            names.append((name_match.group(1), name_match.group(2)))
        return tuple(names)

    def _parse_method_metadata(self, token: Token) -> MethodMetadata:
        entries: dict[str, tuple[str, ...]] = {}
        taxonomy = version = ""
        archetype_state = "unclassified"
        children = self.take_suite(token)
        for child in children:
            match = re.fullmatch(r"([a-z][a-z0-9_]*)\s*=\s*(.+)", child.value)
            if child.kind != TokenKind.LINE or match is None:
                self.fail(
                    "method metadata requires declarative name = value entries",
                    child,
                    "syntax-method-metadata",
                )
            key, value = match.groups()
            if key in entries or (key == "taxonomy" and taxonomy):
                self.fail(
                    f"duplicate metadata field `{key}`", child, "syntax-method-metadata"
                )
            if key == "taxonomy":
                reference = re.fullmatch(r'"([a-z][a-z0-9-]*)@(\d+\.\d+\.\d+)"', value)
                if reference is None:
                    self.fail(
                        'taxonomy requires a pinned "identifier@version"',
                        child,
                        "syntax-method-metadata",
                    )
                taxonomy, version = reference.groups()
                continue
            values = self._metadata_identifiers(value, child)
            if key == "reasoning_archetypes":
                archetype_state = (
                    "not_applicable" if values == ("not_applicable",) else "applicable"
                )
                if archetype_state == "not_applicable":
                    values = ()
            entries[key] = values
        if not taxonomy:
            self.fail(
                "method metadata requires taxonomy identifier and version",
                token,
                "syntax-method-metadata",
            )
        return MethodMetadata(
            taxonomy,
            version,
            tuple(entries.items()),
            archetype_state,
            replace(
                token.span,
                end_line=children[-1].span.end_line,
                end_column=children[-1].span.end_column,
            ),
        )

    def _metadata_identifiers(self, value: str, token: Token) -> tuple[str, ...]:
        text = value[1:-1] if value.startswith("[") and value.endswith("]") else value
        values = tuple(split_top_level(text))
        if not values or any(
            re.fullmatch(r"[a-z][a-z0-9_]*", item) is None for item in values
        ):
            self.fail(
                "metadata values must be canonical identifiers or identifier lists",
                token,
                "syntax-method-metadata",
            )
        return values

    def _parse_type_alias(self, line: str, token: Token) -> TypeDecl | None:
        alias_header = line[len("type ") :].strip()
        alias_name = re.match(r"[A-Za-z_]\w*", alias_header)
        if alias_name is not None:
            name = alias_name.group(0)
            cursor = alias_name.end()
            parameters: str | None = None
            if cursor < len(alias_header) and alias_header[cursor] == "[":
                close = matching_delimiter(alias_header, cursor)
                parameters = alias_header[cursor + 1 : close]
                cursor = close + 1
            remainder = alias_header[cursor:].strip()
            if remainder.startswith("=") and remainder[1:].strip():
                return TypeDecl(
                    name,
                    (),
                    token.span,
                    _parse_type_parameters(parameters),
                    alias=TypeExpr(remainder[1:].strip(), token.span),
                )
        return None


class _StatementParser:
    def __init__(self, tokens: tuple[Token, ...], path: str | None) -> None:
        self.tokens = (
            *tokens,
            Token(TokenKind.EOF, "", tokens[-1].span if tokens else SourceSpan(1)),
        )
        self.index = 0
        self.path = path

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def parse(self):
        statements = []
        while self.current.kind != TokenKind.EOF:
            token = self.advance()
            if token.kind != TokenKind.LINE:
                self.fail(
                    "unexpected indentation in suite", token, "layout-unexpected-token"
                )
            line = token.value
            first = _removed_form(line)
            if first is not None:
                self.fail(REMOVED_FORMS[first], token, f"removed-{first}")
            if "|-" in line and not line.startswith("theorem "):
                self.fail(
                    "`|-` is legal only in theorem or proof-obligation positions",
                    token,
                    "strict-outside-theorem",
                )
            if line.startswith("return "):
                expression_text, expression_positions = _trimmed_slice(
                    line, token.source_positions, len("return ")
                )
                statements.append(
                    Return(
                        parse_expression(
                            expression_text,
                            token.span,
                            self.path,
                            source_positions=expression_positions,
                        ),
                        token.span,
                    )
                )
            elif line.startswith("exact "):
                expression_text, expression_positions = _trimmed_slice(
                    line, token.source_positions, len("exact ")
                )
                statements.append(
                    Exact(
                        parse_expression(
                            expression_text,
                            token.span,
                            self.path,
                            source_positions=expression_positions,
                        ),
                        token.span,
                    )
                )
            elif find_top_level(line, "=") >= 0:
                statements.append(self.parse_binding(token))
            else:
                statements.append(
                    ExpressionStatement(
                        parse_expression(
                            line,
                            token.span,
                            self.path,
                            source_positions=token.source_positions,
                        ),
                        token.span,
                    )
                )
        return tuple(statements)

    def parse_binding(self, token: Token) -> Binding:
        outer = _Parser((), "", self.path)
        return outer.parse_binding_line(token.value, token)

    def fail(self, message: str, token: Token, code: str):
        raise PrismSyntaxError(Diagnostic(message, token.span, code), self.path)


class _SuiteCursor:
    """Small cursor shared by the two declaration-only suite grammars."""

    def __init__(self, tokens: tuple[Token, ...], path: str | None) -> None:
        self.tokens = (
            *tokens,
            Token(TokenKind.EOF, "", tokens[-1].span if tokens else SourceSpan(1)),
        )
        self.index = 0
        self.path = path

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.current
        self.index += 1
        return token

    def take_nested_suite(self, opener: Token) -> tuple[Token, ...]:
        if self.current.kind != TokenKind.INDENT:
            self.fail("expected an indented suite", opener, "layout-missing-suite")
        self.advance()
        depth = 1
        result: list[Token] = []
        while depth:
            token = self.advance()
            if token.kind == TokenKind.EOF:
                self.fail(
                    "unterminated nested suite",
                    opener,
                    "layout-unterminated-suite",
                )
            if token.kind == TokenKind.INDENT:
                depth += 1
            elif token.kind == TokenKind.DEDENT:
                depth -= 1
                if depth == 0:
                    break
            result.append(token)
        return tuple(result)

    def fail(self, message: str, token: Token, code: str):
        raise PrismSyntaxError(Diagnostic(message, token.span, code), self.path)


class _WorkflowParser(_SuiteCursor):
    """Parse a workflow as visual topology rather than executable statements."""

    def parse(self) -> tuple[Composition, str | None]:
        if self.current.kind == TokenKind.EOF:
            self.fail(
                "workflow requires exactly one root composition",
                self.current,
                "syntax-workflow-topology",
            )
        composition = self.parse_composition()
        result_alias: str | None = None
        if self.current.kind == TokenKind.LINE and self.current.value.startswith(
            "return "
        ):
            token = self.advance()
            result_alias = token.value[len("return ") :].strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", result_alias):
                self.fail(
                    "workflow return selects one occurrence alias",
                    token,
                    "syntax-workflow-return",
                )
        if self.current.kind != TokenKind.EOF:
            self.fail(
                "workflow body contains one root composition and an optional final return",
                self.current,
                "syntax-workflow-topology",
            )
        return composition, result_alias

    def parse_composition(self) -> Composition:
        token = self.advance()
        if token.kind != TokenKind.LINE:
            self.fail(
                "expected a workflow composition",
                token,
                "syntax-workflow-topology",
            )
        line = token.value
        if line.startswith("["):
            return self.parse_node(line, token)
        block_match = re.fullmatch(
            r"(sequence|parallel)(?:\s+by\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))?:",
            line,
        )
        if block_match is not None:
            children = self.parse_children(token)
            relation = block_match.group(2)
            if block_match.group(1) == "sequence":
                return SequenceComposition(children, token.span, relation)
            return ParallelComposition(children, token.span, relation)
        if line.startswith("choice ") and line.endswith(":"):
            choice_text = line[len("choice ") : -1].strip()
            router_text, relation = _take_relation_suffix(choice_text)
            router = self.parse_node(router_text, token)
            arms = self.parse_choice_arms(token)
            return ChoiceComposition(router, arms, token.span, relation)
        if line.startswith("repeat ") and line.endswith(":"):
            return self._parse_repeat(line, token)
        if line.startswith("return "):
            self.fail(
                "workflow return is allowed only after the root composition",
                token,
                "syntax-workflow-return",
            )
        first = _removed_form(line)
        if first in {"step", "after"}:
            self.fail(REMOVED_FORMS[first], token, f"removed-{first}")
        self.fail(
            "workflow bodies contain only bracketed nodes and sequence, parallel, choice, or repeat",
            token,
            "syntax-workflow-topology",
        )

    def parse_children(self, opener: Token) -> tuple[Composition, ...]:
        suite = _WorkflowParser(self.take_nested_suite(opener), self.path)
        children: list[Composition] = []
        while suite.current.kind != TokenKind.EOF:
            children.append(suite.parse_composition())
        if not children:
            self.fail(
                "workflow composition cannot be empty",
                opener,
                "syntax-workflow-empty",
            )
        return tuple(children)

    def parse_choice_arms(self, opener: Token) -> tuple[ChoiceArm, ...]:
        suite = _SuiteCursor(self.take_nested_suite(opener), self.path)
        arms: list[ChoiceArm] = []
        seen: set[str] = set()
        while suite.current.kind != TokenKind.EOF:
            token = suite.advance()
            if token.kind != TokenKind.LINE:
                suite.fail(
                    "choice contains only case arms",
                    token,
                    "syntax-workflow-choice",
                )
            match = re.fullmatch(r"case\s+(.+):", token.value)
            if match is None:
                suite.fail(
                    "choice arms use `case Pattern:`",
                    token,
                    "syntax-workflow-choice",
                )
            pattern = match.group(1).strip()
            if not pattern or pattern in seen:
                suite.fail(
                    "choice patterns must be non-empty and unique",
                    token,
                    "syntax-workflow-choice",
                )
            seen.add(pattern)
            branch = _WorkflowParser(suite.take_nested_suite(token), self.path)
            children: list[Composition] = []
            while branch.current.kind != TokenKind.EOF:
                children.append(branch.parse_composition())
            if not children:
                suite.fail(
                    "choice arm cannot be empty",
                    token,
                    "syntax-workflow-empty",
                )
            arms.append(ChoiceArm(pattern, tuple(children), token.span))
        if not arms:
            self.fail(
                "choice requires one or more case arms",
                opener,
                "syntax-workflow-choice",
            )
        return tuple(arms)

    def parse_node(self, text: str, token: Token) -> NodeOccurrence:
        constraints = ()
        if text.endswith(" with:"):
            text = text[: -len(" with:")]
            constraints = self._parse_occurrence_constraints(token)
        try:
            close = matching_delimiter(text, 0)
        except ValueError:
            close = -1
        if not text.startswith("[") or close < 0:
            self.fail(
                "workflow nodes use `[component]` or `[alias: component]`",
                token,
                "syntax-workflow-node",
            )
        suffix = text[close + 1 :].strip()
        relation: str | None = None
        if suffix:
            relation_match = re.fullmatch(
                r"by\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)", suffix
            )
            if relation_match is None:
                self.fail(
                    "an occurrence relation uses `by ImportedRelation`",
                    token,
                    "syntax-reasoning-relation",
                )
            relation = relation_match.group(1)
        content = text[1:close].strip()
        colon = find_top_level(content, ":")
        alias: str | None = None
        component = content
        if colon >= 0:
            alias = content[:colon].strip()
            component = content[colon + 1 :].strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", alias):
                self.fail(
                    "occurrence aliases must be identifiers",
                    token,
                    "syntax-workflow-node",
                )
        if not component:
            self.fail(
                "occurrence component cannot be empty", token, "syntax-workflow-node"
            )
        start = token.value.find(component)
        positions = token.positions_for(start, start + len(component))
        return NodeOccurrence(
            parse_expression(
                component,
                token.span,
                self.path,
                source_positions=positions,
            ),
            alias,
            token.span,
            relation,
            constraints,
        )

    def _parse_occurrence_constraints(self, token):
        constraints = []
        suite = _SuiteCursor(self.take_nested_suite(token), self.path)
        while suite.current.kind != TokenKind.EOF:
            child = suite.advance()
            match = re.fullmatch(
                r"(input|output)((?:\.(?:[A-Za-z_]\w*|\*|\d+|case:[A-Za-z_]\w*))*)"
                r"\.(producers|ancestors)\s*=\s*\[([^\]]+)\]",
                child.value,
            )
            if child.kind != TokenKind.LINE or match is None:
                self.fail(
                    "occurrence constraints use input/output paths and producers/ancestors = [origins]",
                    child,
                    "syntax-occurrence-constraint",
                )
            subject, path, dimension, values = match.groups()
            constraints.append(
                OccurrenceConstraint(
                    subject,
                    tuple(path[1:].split(".")) if path else (),
                    dimension,
                    tuple(item.strip() for item in values.split(",")),
                    child.span,
                )
            )
        return tuple(constraints)

    def _parse_repeat(self, line: str, token: Token) -> RepeatComposition:
        repeat_text = line[len("repeat ") : -1].strip()
        policy_text, relation = _take_relation_suffix(repeat_text)
        policy = parse_expression(policy_text, token.span, self.path)
        until = None
        if isinstance(policy, CallExpr):
            policy_arguments: list[CallArgument] = []
            for argument in policy.arguments:
                if argument.name != "until":
                    policy_arguments.append(argument)
                    continue
                if until is not None:
                    self.fail(
                        "repeat accepts one `until` terminal expression",
                        token,
                        "syntax-repeat-until",
                    )
                until = argument.value
            if until is not None:
                policy = CallExpr(
                    policy.callee,
                    tuple(policy_arguments),
                    policy.span,
                    policy.type_arguments,
                )
        return RepeatComposition(
            policy,
            self.parse_children(token),
            token.span,
            relation,
            until,
        )


class _ReasoningParser(_WorkflowParser):
    """Parse a non-executable reasoning topology and its guarded exits."""

    def parse(
        self,
    ) -> tuple[Composition, tuple[GuardedExit, ...], str | None]:
        if self.current.kind == TokenKind.EOF:
            self.fail(
                "reasoning requires exactly one root composition",
                self.current,
                "syntax-reasoning-topology",
            )
        composition = self.parse_composition()
        exits: list[GuardedExit] = []
        while self.current.kind == TokenKind.LINE and self.current.value.startswith(
            "on "
        ):
            exits.append(self.parse_exit())
        result_alias: str | None = None
        if self.current.kind == TokenKind.LINE and self.current.value.startswith(
            "return "
        ):
            token = self.advance()
            result_alias = token.value[len("return ") :].strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", result_alias):
                self.fail(
                    "reasoning return selects one occurrence alias",
                    token,
                    "syntax-reasoning-return",
                )
        if self.current.kind != TokenKind.EOF:
            self.fail(
                "reasoning body contains one topology, guarded exits, and a final return",
                self.current,
                "syntax-reasoning-topology",
            )
        return composition, tuple(exits), result_alias

    def parse_exit(self) -> GuardedExit:
        token = self.advance()
        match = re.fullmatch(
            r"on\s+([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*=>\s*"
            r"(accept|stop|switch\s+@([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*))",
            token.value,
        )
        if match is None:
            self.fail(
                "guarded exits use `on occurrence.selector => accept|stop|switch @Reasoning`",
                token,
                "syntax-reasoning-exit",
            )
        raw_action = match.group(3)
        action = "switch" if raw_action.startswith("switch") else raw_action
        return GuardedExit(
            match.group(1),
            match.group(2),
            action,
            token.span,
            match.group(4),
        )


def _take_relation_suffix(text: str) -> tuple[str, str | None]:
    marker = find_top_level(text, " by ")
    if marker < 0:
        return text.strip(), None
    value = text[:marker].strip()
    relation = text[marker + len(" by ") :].strip()
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", relation):
        return text.strip(), None
    return value, relation


def parse_parameters(
    text: str, span: SourceSpan, parser: _Parser
) -> tuple[Parameter, ...]:
    if not text.strip():
        return ()
    result = []
    for item in split_top_level(text):
        colon = find_top_level(item, ":")
        if colon < 0:
            parser.fail(
                "public parameters require `name: Type`",
                Token(TokenKind.LINE, item, span),
                "syntax-parameter",
            )
        name, type_text = item[:colon].strip(), item[colon + 1 :].strip()
        if not re.fullmatch(r"[A-Za-z_]\w*", name) or not type_text:
            parser.fail(
                "invalid typed parameter",
                Token(TokenKind.LINE, item, span),
                "syntax-parameter",
            )
        result.append(Parameter(name, TypeExpr(type_text, span), span))
    return tuple(result)


def _parse_type_parameters(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    return tuple(
        item.strip().split(":", 1)[0].strip() for item in split_top_level(text)
    )


def _take_effect_row(
    text: str, token: Token, parser: _Parser
) -> tuple[str, tuple[str, ...]]:
    marker = find_top_level(text, "!")
    if marker < 0:
        return text.strip(), ()
    result = text[:marker].strip()
    row = text[marker + 1 :].strip()
    if not row.startswith("{") or not row.endswith("}"):
        parser.fail(
            "effect row must use `! {Effect.Name, ...}`", token, "syntax-effect-row"
        )
    effects = tuple(item.strip() for item in split_top_level(row[1:-1]))
    return result, effects


def _split_strict_judgment(text: str) -> tuple[tuple[str, ...], str] | None:
    marker = find_top_level(text, "|-")
    if marker < 0:
        return None
    context, conclusion = text[:marker].strip(), text[marker + 2 :].strip()
    if not context.startswith("{") or not context.endswith("}") or not conclusion:
        return None
    return split_top_level(context[1:-1]), conclusion


def _desugar_relation_judgment(
    line: str,
    token: Token,
    parser: _Parser,
) -> str:
    judgments = []
    for marker, wrapper in (("|~", "Supported"), ("|-", "Proof")):
        position = find_top_level(line, marker)
        if position >= 0:
            judgments.append((position, marker, wrapper))
    if not judgments:
        return line
    if len(judgments) != 1:
        parser.fail(
            "a relation declaration must use exactly one result form",
            token,
            "syntax-relation-judgment",
        )
    marker_position, marker, wrapper = judgments[0]
    prefix = line[:marker_position].rstrip()
    proposition = line[marker_position + len(marker) :].strip()
    if find_top_level(prefix, "->") >= 0:
        parser.fail(
            "a relation declaration cannot combine `->` with an inference judgment",
            token,
            "syntax-relation-judgment",
        )
    if not proposition:
        parser.fail(
            f"relation `{marker}` requires a proposition",
            token,
            "syntax-relation-judgment",
        )
    if marker == "|~" and proposition.startswith("["):
        parser.fail(
            "material relation declarations omit the policy; provide it in the relation implementation",
            token,
            "syntax-relation-policy",
        )
    return f"{prefix} -> {wrapper}[{proposition}]"


def _removed_form(line: str) -> str | None:
    for marker in REMOVED_FORMS:
        if re.match(rf"^{re.escape(marker)}(?:\s+[A-Za-z_]|\s+\|~|:)", line):
            return marker
    return None
