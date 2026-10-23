# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Expression parsing, Python AST conversion, and precise source spans."""

from __future__ import annotations

import ast as python_ast

from prism.language.developer.diagnostics import (
    Diagnostic,
    PrismSyntaxError,
    SourceSpan,
)

from .ast import (
    BinaryExpr,
    CallArgument,
    CallExpr,
    ConditionalExpr,
    ExecuteExpr,
    Expression,
    FieldExpr,
    IndexExpr,
    LambdaExpr,
    ListExpr,
    LiteralExpr,
    MapExpr,
    MaterialInferenceExpr,
    NameExpr,
    SolveExpr,
    TryExpr,
    TupleExpr,
    TypeExpr,
    UnaryExpr,
)
from .text import (
    _matching_square,
    find_top_level,
)


def _trimmed_slice(
    text: str,
    source_positions: tuple[tuple[int, int], ...],
    start: int = 0,
    end: int | None = None,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    stop = len(text) if end is None else end
    while start < stop and text[start].isspace():
        start += 1
    while stop > start and text[stop - 1].isspace():
        stop -= 1
    return text[start:stop], source_positions[start:stop]


def _span_from_positions(
    source_positions: tuple[tuple[int, int], ...], fallback: SourceSpan
) -> SourceSpan:
    if not source_positions:
        return fallback
    start_line, start_column = source_positions[0]
    end_line, end_column = source_positions[-1]
    return SourceSpan(start_line, start_column, end_line, end_column + 1)


def _python_character_offset(text: str, line: int, byte_column: int) -> int:
    lines = text.splitlines(keepends=True) or [text]
    line_index = max(0, min(line - 1, len(lines) - 1))
    prefix = sum(len(item) for item in lines[:line_index])
    encoded = lines[line_index].encode("utf-8")[:byte_column]
    return prefix + len(encoded.decode("utf-8", errors="ignore"))


def _python_node_span(
    node: python_ast.AST,
    text: str,
    source_positions: tuple[tuple[int, int], ...],
    fallback: SourceSpan,
) -> SourceSpan:
    if not source_positions or not hasattr(node, "col_offset"):
        return fallback
    start = _python_character_offset(
        text, getattr(node, "lineno", 1), getattr(node, "col_offset", 0)
    )
    end = _python_character_offset(
        text,
        getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        getattr(node, "end_col_offset", getattr(node, "col_offset", 0) + 1),
    )
    selected = source_positions[start:end]
    return _span_from_positions(selected, fallback)


def _syntax_error_span(
    text: str,
    source_positions: tuple[tuple[int, int], ...],
    fallback: SourceSpan,
    line: int,
    column: int,
) -> SourceSpan:
    if not source_positions:
        return fallback
    offset = _python_character_offset(text, line, max(column - 1, 0))
    selected = source_positions[offset : offset + 1]
    return _span_from_positions(selected, fallback)


def parse_expression(
    text: str,
    span: SourceSpan,
    path: str | None = None,
    *,
    source_positions: tuple[tuple[int, int], ...] = (),
) -> Expression:
    expression_span = _span_from_positions(source_positions, span)
    if find_top_level(text, "|-") >= 0:
        raise PrismSyntaxError(
            Diagnostic(
                "`|-` is legal only in theorem or proof-obligation positions",
                expression_span,
                "strict-outside-theorem",
            ),
            path,
        )
    if text.startswith("try "):
        inner_text, inner_positions = _trimmed_slice(
            text, source_positions, len("try ")
        )
        return TryExpr(
            parse_expression(
                inner_text,
                expression_span,
                path,
                source_positions=inner_positions,
            ),
            expression_span,
        )
    for keyword, cls in (("solve ", SolveExpr), ("execute ", ExecuteExpr)):
        if text.startswith(keyword):
            return _parse_execution_expression(
                text, source_positions, expression_span, path, keyword, cls
            )
    material = find_top_level(text, "|~[")
    if material >= 0:
        policy_start = material + 3
        close = _matching_square(text, policy_start - 1)
        left, left_positions = _trimmed_slice(text, source_positions, 0, material)
        policy, policy_positions = _trimmed_slice(
            text, source_positions, policy_start, close
        )
        proposition, proposition_positions = _trimmed_slice(
            text, source_positions, close + 1
        )
        if not left or not policy or not proposition:
            raise PrismSyntaxError(
                Diagnostic(
                    "material inference requires `evidence |~[policy] proposition`",
                    expression_span,
                    "syntax-material-inference",
                ),
                path,
            )
        return MaterialInferenceExpr(
            parse_expression(
                left, expression_span, path, source_positions=left_positions
            ),
            parse_expression(
                policy, expression_span, path, source_positions=policy_positions
            ),
            parse_expression(
                proposition,
                expression_span,
                path,
                source_positions=proposition_positions,
            ),
            expression_span,
        )
    if find_top_level(text, "|~") >= 0:
        raise PrismSyntaxError(
            Diagnostic(
                "`|~` requires a bracketed policy",
                expression_span,
                "material-policy-required",
            ),
            path,
        )
    try:
        tree = python_ast.parse(text, mode="eval").body
    except SyntaxError as exc:
        raise PrismSyntaxError(
            Diagnostic(
                f"invalid expression: {exc.msg}",
                _syntax_error_span(
                    text,
                    source_positions,
                    expression_span,
                    exc.lineno or 1,
                    exc.offset or 1,
                ),
                "syntax-expression",
            ),
            path,
        ) from exc
    return _convert_python_expression(
        tree, expression_span, path, text, source_positions
    )


def _convert_python_expression(
    node: python_ast.expr,
    span: SourceSpan,
    path: str | None,
    text: str,
    source_positions: tuple[tuple[int, int], ...],
) -> Expression:
    node_span = _python_node_span(node, text, source_positions, span)
    if isinstance(node, python_ast.Constant):
        return LiteralExpr(node.value, node_span)
    if isinstance(node, python_ast.Name):
        return NameExpr(node.id, node_span)
    if isinstance(node, python_ast.Lambda):
        if (
            len(node.args.args) != 1
            or node.args.posonlyargs
            or node.args.kwonlyargs
            or node.args.vararg is not None
            or node.args.kwarg is not None
            or node.args.defaults
            or node.args.kw_defaults
        ):
            return _unsupported_expression(node, span, path)
        return LambdaExpr(
            node.args.args[0].arg,
            _convert_python_expression(node.body, span, path, text, source_positions),
            node_span,
        )
    if isinstance(node, python_ast.List):
        return ListExpr(
            tuple(
                _convert_python_expression(item, span, path, text, source_positions)
                for item in node.elts
            ),
            node_span,
        )
    if isinstance(node, python_ast.Tuple):
        return TupleExpr(
            tuple(
                _convert_python_expression(item, span, path, text, source_positions)
                for item in node.elts
            ),
            node_span,
        )
    if isinstance(node, python_ast.Dict):
        if any(key is None for key in node.keys):
            return _unsupported_expression(node, span, path)
        return MapExpr(
            tuple(
                (
                    _convert_python_expression(key, span, path, text, source_positions),
                    _convert_python_expression(
                        value, span, path, text, source_positions
                    ),
                )
                for key, value in zip(node.keys, node.values, strict=True)
                if key is not None
            ),
            node_span,
        )
    return _convert_python_access(node, span, path, text, source_positions, node_span)


def _convert_operator_expression(
    node,
    span: SourceSpan,
    path: str | None,
    text: str,
    source_positions: tuple[tuple[int, int], ...],
) -> Expression:
    binary_names = {
        python_ast.Add: "+",
        python_ast.Sub: "-",
        python_ast.Mult: "*",
        python_ast.Div: "/",
        python_ast.Pow: "**",
        python_ast.Mod: "%",
    }
    comparison_names = {
        python_ast.Eq: "==",
        python_ast.NotEq: "!=",
        python_ast.Lt: "<",
        python_ast.LtE: "<=",
        python_ast.Gt: ">",
        python_ast.GtE: ">=",
    }
    if isinstance(node, python_ast.BinOp) and type(node.op) in binary_names:
        return BinaryExpr(
            _convert_python_expression(node.left, span, path, text, source_positions),
            binary_names[type(node.op)],
            _convert_python_expression(node.right, span, path, text, source_positions),
            _python_node_span(node, text, source_positions, span),
        )
    if isinstance(node, python_ast.BoolOp):
        operator = "and" if isinstance(node.op, python_ast.And) else "or"
        result = _convert_python_expression(
            node.values[0], span, path, text, source_positions
        )
        for value in node.values[1:]:
            result = BinaryExpr(
                result,
                operator,
                _convert_python_expression(value, span, path, text, source_positions),
                _python_node_span(node, text, source_positions, span),
            )
        return result
    if (
        isinstance(node, python_ast.Compare)
        and len(node.ops) == 1
        and type(node.ops[0]) in comparison_names
    ):
        return BinaryExpr(
            _convert_python_expression(node.left, span, path, text, source_positions),
            comparison_names[type(node.ops[0])],
            _convert_python_expression(
                node.comparators[0], span, path, text, source_positions
            ),
            _python_node_span(node, text, source_positions, span),
        )
    return _unsupported_expression(node, span, path)


def _unsupported_expression(node, span: SourceSpan, path: str | None):
    raise PrismSyntaxError(
        Diagnostic(
            f"unsupported expression in this language slice: {type(node).__name__}",
            span,
            "syntax-unsupported-expression",
        ),
        path,
    )


def _parse_execution_expression(
    text, source_positions, expression_span, path, keyword, cls
) -> Expression:
    inner_start = len(keyword)
    marker = find_top_level(text[inner_start:], " using ")
    if marker < 0:
        workflow_text, workflow_positions = _trimmed_slice(
            text, source_positions, inner_start
        )
        if not workflow_text:
            raise PrismSyntaxError(
                Diagnostic(
                    f"`{keyword.strip()}` requires a workflow",
                    expression_span,
                    f"syntax-{keyword.strip()}-workflow",
                ),
                path,
            )
        return cls(
            None,
            parse_expression(
                workflow_text,
                expression_span,
                path,
                source_positions=workflow_positions,
            ),
            expression_span,
        )
    marker += inner_start
    reasoning_text, reasoning_positions = _trimmed_slice(
        text, source_positions, inner_start, marker
    )
    workflow_text, workflow_positions = _trimmed_slice(
        text, source_positions, marker + len(" using ")
    )
    if not reasoning_text or not workflow_text:
        raise PrismSyntaxError(
            Diagnostic(
                f"`{keyword.strip()}` requires both reasoning and a workflow",
                expression_span,
                f"syntax-{keyword.strip()}-using",
            ),
            path,
        )
    return cls(
        parse_expression(
            reasoning_text,
            expression_span,
            path,
            source_positions=reasoning_positions,
        ),
        parse_expression(
            workflow_text,
            expression_span,
            path,
            source_positions=workflow_positions,
        ),
        expression_span,
    )


def _convert_python_access(
    node: python_ast.expr,
    span: SourceSpan,
    path: str | None,
    text: str,
    source_positions: tuple[tuple[int, int], ...],
    node_span: SourceSpan,
) -> Expression:
    if isinstance(node, python_ast.Attribute):
        return FieldExpr(
            _convert_python_expression(node.value, span, path, text, source_positions),
            node.attr,
            node_span,
        )
    if isinstance(node, python_ast.IfExp):
        return ConditionalExpr(
            condition=_convert_python_expression(
                node.test, span, path, text, source_positions
            ),
            when_true=_convert_python_expression(
                node.body, span, path, text, source_positions
            ),
            when_false=_convert_python_expression(
                node.orelse, span, path, text, source_positions
            ),
            span=node_span,
        )
    if isinstance(node, python_ast.Subscript):
        if isinstance(node.slice, python_ast.Slice):
            return _unsupported_expression(node, span, path)
        return IndexExpr(
            value=_convert_python_expression(
                node.value, span, path, text, source_positions
            ),
            index=_convert_python_expression(
                node.slice, span, path, text, source_positions
            ),
            span=node_span,
        )
    if isinstance(node, python_ast.Call):
        return _convert_python_call(node, span, path, text, source_positions, node_span)
    if isinstance(node, python_ast.UnaryOp):
        operator = {
            python_ast.Not: "not",
            python_ast.USub: "-",
            python_ast.UAdd: "+",
        }.get(type(node.op))
        if operator:
            return UnaryExpr(
                operator,
                _convert_python_expression(
                    node.operand, span, path, text, source_positions
                ),
                node_span,
            )
    if isinstance(node, python_ast.BinOp | python_ast.BoolOp | python_ast.Compare):
        return _convert_operator_expression(node, span, path, text, source_positions)
    return _unsupported_expression(node, span, path)


def _convert_python_call(node, span, path, text, source_positions, node_span):
    if any(keyword.arg is None for keyword in node.keywords):
        return _unsupported_expression(node, span, path)
    callee = node.func
    type_arguments: tuple[TypeExpr, ...] = ()
    if isinstance(callee, python_ast.Subscript):
        generic = callee.slice
        items = generic.elts if isinstance(generic, python_ast.Tuple) else (generic,)
        type_arguments = tuple(
            TypeExpr(
                python_ast.unparse(item),
                _python_node_span(item, text, source_positions, span),
            )
            for item in items
        )
        callee = callee.value
    return CallExpr(
        _convert_python_expression(callee, span, path, text, source_positions),
        (
            *(
                CallArgument(
                    _convert_python_expression(item, span, path, text, source_positions)
                )
                for item in node.args
            ),
            *(
                CallArgument(
                    _convert_python_expression(
                        item.value, span, path, text, source_positions
                    ),
                    item.arg,
                )
                for item in node.keywords
            ),
        ),
        node_span,
        type_arguments,
    )
