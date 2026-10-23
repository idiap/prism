# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Builtin dispatch and runtime constructors."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from prism.language.core import (
    CoreType,
    Err,
    Ok,
    RefinementPolicyValue,
)
from prism.language.interop import (
    ConnectionReference,
    ResourceReference,
    SourceReference,
)
from prism.language.kernel import (
    Term,
)

from .effects import _builtin_generate, _builtin_python_call, _builtin_tool_call
from .evidence import (
    _builtin_accept_assessment,
    _builtin_accept_support,
    _builtin_combine_evidence,
    _builtin_compute,
    _builtin_inconclusive_assessment,
    _builtin_map_evidence,
    _builtin_material_policy,
    _builtin_observe,
    _builtin_reject_assessment,
    _builtin_validate,
    _builtin_validator,
)
from .proofs import _builtin_elaborate_proof, _builtin_kernel_check, _builtin_verify
from .sources import _builtin_query, _builtin_resource_evidence
from .values import ClaimValue, HooksArtifactValue, SkillArtifactValue

if TYPE_CHECKING:
    from .execution import _Engine


def _call_builtin(
    self: _Engine,
    name: str,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
    *,
    proof_context=(),
) -> Any:
    handler = _BUILTINS.get(name)
    if handler is None:
        raise ValueError(f"unknown runtime builtin `{name}`")
    if name == "elaborate_proof":
        return _builtin_elaborate_proof(
            self, args, named, result_type, expected_term, proof_context=proof_context
        )
    return handler(self, args, named, result_type, expected_term)


def _checked_module_hash(self: _Engine) -> str | None:
    module = self.program.checked_module
    return module.content_hash if module is not None else None


def _builtin_ok(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return Ok(args[0] if args else next(iter(named.values())))


def _builtin_err(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return Err(args[0] if args else next(iter(named.values())))


def _builtin_claim(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return ClaimValue(str(args[0]), "asserted:" + str(args[0]))


def _builtin_refinement_policy(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    bound = args[0]
    if type(bound) is not int or bound <= 0:
        raise ValueError(
            "refinement_policy requires a positive integer iteration bound"
        )
    return RefinementPolicyValue(bound)


def _builtin_embed(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return ResourceReference(str(args[0]), "Any")


def _builtin_inline_resource(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    try:
        content = base64.b64decode(str(args[1]), validate=True)
        return ResourceReference(
            str(args[0]),
            "Bytes",
            content,
            str(args[2]),
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid inline resource: {exc}") from exc


def _builtin_length(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return len(args[0])


def _builtin_data_source(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return SourceReference(str(args[0]), None)


def _builtin_graph_source(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return SourceReference(str(args[0]), None, True)


def _builtin_connect(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return ConnectionReference(str(args[0]), "Any")


def _builtin_skill_artifact(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    return SkillArtifactValue(
        str(args[0]),
        str(args[1]),
        str(args[2]),
        str(args[3]),
        str(args[4]),
        str(args[5]),
    )


def _builtin_hooks_artifact(
    self: _Engine,
    args,
    named,
    result_type: CoreType | None = None,
    expected_term: Term | None = None,
) -> Any:
    provider = (
        result_type.arguments[0].name
        if result_type is not None
        and result_type.name == "Hooks"
        and result_type.arguments
        else "Unknown"
    )
    return HooksArtifactValue(provider, str(args[0]))


_BUILTINS = {
    "Ok": _builtin_ok,
    "Err": _builtin_err,
    "claim": _builtin_claim,
    "material_policy": _builtin_material_policy,
    "accept_assessment": _builtin_accept_assessment,
    "reject_assessment": _builtin_reject_assessment,
    "inconclusive_assessment": _builtin_inconclusive_assessment,
    "accept_support": _builtin_accept_support,
    "refinement_policy": _builtin_refinement_policy,
    "embed": _builtin_embed,
    "inline_resource": _builtin_inline_resource,
    "length": _builtin_length,
    "data_source": _builtin_data_source,
    "graph_source": _builtin_graph_source,
    "connect": _builtin_connect,
    "skill_artifact": _builtin_skill_artifact,
    "hooks_artifact": _builtin_hooks_artifact,
    "observe": _builtin_observe,
    "map_evidence": _builtin_map_evidence,
    "combine_evidence": _builtin_combine_evidence,
    "compute": _builtin_compute,
    "validator": _builtin_validator,
    "validate": _builtin_validate,
    "resource_evidence": _builtin_resource_evidence,
    "query": _builtin_query,
    "python_call": _builtin_python_call,
    "tool_call": _builtin_tool_call,
    "generate": _builtin_generate,
    "elaborate_proof": _builtin_elaborate_proof,
    "kernel.check": _builtin_kernel_check,
    "verify": _builtin_verify,
}
