# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Untrusted lowering from supported Prism syntax to native core terms."""

from __future__ import annotations

import re
from dataclasses import dataclass

from prism.language.kernel import (
    PROP,
    TYPE,
    App,
    Const,
    ConstructorRef,
    Context,
    Environment,
    InductiveRef,
    Lam,
    Local,
    Pi,
    Term,
    apps,
    whnf,
)
from prism.language.verification import ProofElaborationError, RawProofTerm

from .diagnostics import SourceSpan
from .syntax.ast import (
    BinaryExpr,
    CallExpr,
    Expression,
    FieldExpr,
    LambdaExpr,
    LiteralExpr,
    NameExpr,
)
from .syntax.parser import parse_expression


@dataclass(frozen=True, slots=True)
class CoreLocal:
    name: str
    type: Term


def elaborate_type_text(
    text: str,
    environment: Environment,
    locals: tuple[CoreLocal, ...] = (),
) -> Term:
    text = text.strip()
    if text.startswith("Proof[") and text.endswith("]"):
        return elaborate_type_text(text[6:-1], environment, locals)
    if text == "Prop":
        return PROP
    if text == "Type":
        return TYPE
    if text == "Nat":
        return InductiveRef("Nat")
    if text == "Bool":
        return InductiveRef("Bool")
    if text.startswith("forall "):
        binder, body = _split_forall(text[7:])
        name, separator, domain_text = binder.partition(":")
        if not separator or not name.strip() or not domain_text.strip():
            raise ProofElaborationError("forall requires a named typed binder")
        domain = elaborate_type_text(domain_text, environment, locals)
        return Pi(
            name.strip(),
            domain,
            elaborate_type_text(
                body, environment, (*locals, CoreLocal(name.strip(), domain))
            ),
        )
    try:
        expression = parse_expression(text, SourceSpan(1))
    except ValueError as exc:
        raise ProofElaborationError(f"cannot elaborate core type `{text}`") from exc
    return elaborate_expression(expression, environment, locals)


def elaborate_expression(
    expression: Expression,
    environment: Environment,
    locals: tuple[CoreLocal, ...] = (),
) -> Term:
    if isinstance(expression, LiteralExpr):
        if isinstance(expression.value, bool):
            return ConstructorRef("Bool.true" if expression.value else "Bool.false")
        if isinstance(expression.value, int) and expression.value >= 0:
            return nat_literal(expression.value)
        raise ProofElaborationError(
            f"literal `{expression.value!r}` is not available in the proof fragment"
        )
    if isinstance(expression, NameExpr):
        for offset, local in enumerate(reversed(locals)):
            if local.name == expression.name:
                return Local(offset)
        aliases = {
            "sum_range": "Nat.sum_range",
            "rfl": "Eq.rfl",
        }
        name = aliases.get(expression.name, expression.name)
        declaration = environment.get(name)
        if declaration.kind == "inductive":
            return InductiveRef(name)
        if declaration.kind == "constructor":
            return ConstructorRef(name)
        return Const(name)
    if isinstance(expression, FieldExpr):
        return elaborate_expression(
            NameExpr(_expression_name(expression), expression.span), environment, locals
        )
    if isinstance(expression, CallExpr):
        function = elaborate_expression(expression.callee, environment, locals)
        if any(argument.name is not None for argument in expression.arguments):
            raise ProofElaborationError("named arguments are not core proof terms")
        return apps(
            function,
            *(
                elaborate_expression(item.value, environment, locals)
                for item in expression.arguments
            ),
        )
    if isinstance(expression, BinaryExpr):
        left = elaborate_expression(expression.left, environment, locals)
        right = elaborate_expression(expression.right, environment, locals)
        if expression.operator == "+":
            return apps(Const("Nat.add"), left, right)
        if expression.operator == "*":
            return apps(Const("Nat.mul"), left, right)
        if expression.operator == "==":
            return apps(InductiveRef("Eq"), InductiveRef("Nat"), left, right)
        raise ProofElaborationError(
            f"operator `{expression.operator}` is not available in the proof fragment"
        )
    raise ProofElaborationError(
        f"`{type(expression).__name__}` is not available in the proof fragment"
    )


def elaborate_proof_expression(
    expression: Expression,
    expected: Term,
    environment: Environment,
    locals: tuple[CoreLocal, ...] = (),
) -> Term:
    if isinstance(expression, LambdaExpr):
        expected_whnf = whnf(environment, _context(locals), expected)
        if not isinstance(expected_whnf, Pi):
            raise ProofElaborationError("lambda proof supplied for a non-function goal")
        body = elaborate_proof_expression(
            expression.body,
            expected_whnf.codomain,
            environment,
            (*locals, CoreLocal(expression.parameter, expected_whnf.domain)),
        )
        return Lam(expression.parameter, expected_whnf.domain, body)
    if isinstance(expression, NameExpr) and expression.name == "rfl":
        return reflexivity_term(expected, environment, _context(locals))
    return elaborate_expression(expression, environment, locals)


def elaborate_proof_source(
    source: str,
    expected: Term,
    environment: Environment,
    locals: tuple[CoreLocal, ...] = (),
) -> RawProofTerm:
    source = source.strip()
    if source.startswith("exact "):
        source = source[6:].strip()
    expected_whnf = whnf(environment, _context(locals), expected)
    lambda_match = re.fullmatch(r"fun\s+([A-Za-z_]\w*)\s*=>\s*(.+)", source, re.DOTALL)
    if lambda_match:
        if not isinstance(expected_whnf, Pi):
            raise ProofElaborationError("lambda proof supplied for a non-function goal")
        name, body_source = lambda_match.groups()
        body = elaborate_proof_source(
            body_source,
            expected_whnf.codomain,
            environment,
            (*locals, CoreLocal(name, expected_whnf.domain)),
        ).term
        return RawProofTerm(Lam(name, expected_whnf.domain, body), expected, source)
    if source == "rfl":
        return RawProofTerm(
            reflexivity_term(expected, environment, _context(locals)), expected, source
        )
    try:
        expression = parse_expression(source, SourceSpan(1))
        term = elaborate_proof_expression(expression, expected, environment, locals)
    except ValueError as exc:
        raise ProofElaborationError(f"invalid generated proof syntax: {exc}") from exc
    return RawProofTerm(term, expected, source)


def reflexivity_term(
    expected: Term, environment: Environment, context: Context
) -> Term:
    normalized = whnf(environment, context, expected)
    head, arguments = _unfold(normalized)
    if not (
        isinstance(head, InductiveRef) and head.name == "Eq" and len(arguments) == 3
    ):
        raise ProofElaborationError("`rfl` requires an equality goal")
    value_type, left, _right = arguments
    return apps(ConstructorRef("Eq.rfl"), value_type, left)


def nat_literal(value: int) -> Term:
    result: Term = ConstructorRef("Nat.zero")
    for _ in range(value):
        result = App(ConstructorRef("Nat.succ"), result)
    return result


def _context(locals: tuple[CoreLocal, ...]) -> Context:
    result = Context()
    for local in locals:
        result = result.push(local.name, local.type)
    return result


def _unfold(term: Term) -> tuple[Term, tuple[Term, ...]]:
    from prism.language.kernel import unfold_apps

    return unfold_apps(term)


def _expression_name(expression: FieldExpr) -> str:
    parts = [expression.field]
    value = expression.value
    while isinstance(value, FieldExpr):
        parts.append(value.field)
        value = value.value
    if not isinstance(value, NameExpr):
        raise ProofElaborationError("computed field references are not core constants")
    parts.append(value.name)
    return ".".join(reversed(parts))


def _split_forall(text: str) -> tuple[str, str]:
    depth = 0
    for index, character in enumerate(text):
        if character in "([":
            depth += 1
        elif character in ")]":
            depth -= 1
        elif character == "," and depth == 0:
            return text[:index].strip(), text[index + 1 :].strip()
    raise ProofElaborationError("forall requires `,` before its body")
