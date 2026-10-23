# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Runtime proofs operations."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    CoreType,
    DependentPair,
    Err,
    Ok,
)
from prism.language.developer import CoreLocal, elaborate_proof_source
from prism.language.kernel import (
    CheckedTerm,
    Context,
    InductiveRef,
    KernelError,
    Term,
    is_def_eq,
    substitute,
    term_hash,
)
from prism.language.verification import ProofSyntax, RawProofTerm
from prism.runtime.results import TraceEvent

if TYPE_CHECKING:
    from .execution import _Engine


def _builtin_elaborate_proof(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
    *,
    proof_context=(),
) -> Any:
    if result_type is None or result_type.name != "Result":
        return Err("elaborate_proof is missing its expected proposition")
    core_term_type = result_type.arguments[0]
    if core_term_type.name != "CoreTerm" or not core_term_type.arguments:
        return Err("elaborate_proof requires CoreTerm[P] result context")
    if expected_term is None:
        return Err("elaborate_proof is missing its checked kernel proposition")
    try:
        expected = expected_term
        source_value = args[0]
        source = (
            source_value.source
            if isinstance(source_value, ProofSyntax)
            else str(source_value)
        )
        self.trace.append(
            TraceEvent(
                "proof-goal-created",
                "dynamic",
                metadata={
                    "expected_type_hash": term_hash(expected),
                    "module_hash": self._checked_module_hash(),
                },
            )
        )
        self.trace.append(
            TraceEvent(
                "proof-syntax-elaborated",
                "dynamic",
                provenance="Computed",
                metadata={
                    "procedure": "prism-proof-elaborator-v1",
                    "expected_type_hash": term_hash(expected),
                    "module_hash": self._checked_module_hash(),
                },
            )
        )
        locals_ = tuple(
            CoreLocal(name, InductiveRef(type_.name))
            for name, type_, _ in proof_context
        )
        raw = elaborate_proof_source(source, expected, self.kernel.environment, locals_)
        term = raw.term
        for _, _, value in reversed(proof_context):
            term = substitute(term, value)
        raw = replace(raw, term=term)
        self.trace.append(
            TraceEvent(
                "proof-term-elaborated",
                raw.producer,
                metadata={
                    "term_hash": term_hash(raw.term),
                    "expected_type_hash": term_hash(expected),
                    "module_hash": self._checked_module_hash(),
                },
            )
        )
        return Ok(raw)
    except (KernelError, ValueError) as exc:
        return Err(str(exc))


def _builtin_kernel_check(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    raw = args[0]
    if not isinstance(raw, RawProofTerm):
        return Err("kernel.check accepts only elaborated raw core terms")
    try:
        if expected_term is None or not is_def_eq(
            self.kernel.environment, Context(), expected_term, raw.expected_type
        ):
            raise KernelError(
                "kernel.check rejected a raw term for a different instantiated proposition"
            )
        proof = self.kernel.check(raw.term, expected_term)
    except KernelError as exc:
        self.trace.append(
            TraceEvent(
                "kernel-check-rejected",
                "native",
                metadata={
                    "reason": str(exc),
                    "type_hash": term_hash(raw.expected_type),
                    "term_hash": term_hash(raw.term),
                    "environment_hash": self.kernel.environment.hash,
                    "module_hash": self._checked_module_hash(),
                },
            )
        )
        return Err(str(exc))
    self.trace.append(
        TraceEvent(
            "kernel-check-accepted",
            "native",
            assurance="Proof",
            metadata={
                "type_hash": proof.type_hash,
                "term_hash": proof.term_hash,
                "environment_hash": proof.environment_hash,
                "module_hash": self._checked_module_hash(),
                "axioms": sorted(proof.axioms),
            },
        )
    )
    self.trace.append(
        TraceEvent(
            "axiom-dependency-recorded",
            "native",
            assurance="Proof",
            metadata={
                "term_hash": proof.term_hash,
                "module_hash": self._checked_module_hash(),
                "axioms": sorted(proof.axioms),
            },
        )
    )
    return Ok(proof)


def _builtin_verify(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    value, proof = args
    if not isinstance(proof, CheckedTerm):
        raise ValueError("verify requires a kernel-checked inhabitant")
    try:
        rechecked = self.kernel.recheck(proof)
    except KernelError as exc:
        raise ValueError(f"verify rejected an invalid checked term: {exc}") from exc
    if expected_term is None or not is_def_eq(
        self.kernel.environment, Context(), expected_term, rechecked.type
    ):
        raise ValueError(
            "verify rejected a proof for a different instantiated value or proposition"
        )
    return DependentPair(value, rechecked)
