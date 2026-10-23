# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Built-in call dispatch."""

from __future__ import annotations

from .builtin_context import _BuiltinCall
from .builtin_effects import _BuiltinEffectsMixin
from .builtin_evidence import _BuiltinEvidenceMixin
from .builtin_proofs import _BuiltinProofsMixin
from .builtin_values import _BuiltinValuesMixin

_BUILTIN_HANDLERS = {
    "Ok": "_builtin_result",
    "Err": "_builtin_result",
    "length": "_builtin_length",
    "Generated": "_builtin_generated",
    "Computed": "_builtin_computed",
    "Validated": "_builtin_validated",
    "embed": "_builtin_embed",
    "inline_resource": "_builtin_inline_resource",
    "data_source": "_builtin_data_source",
    "graph_source": "_builtin_graph_source",
    "connect": "_builtin_connect",
    "skill_artifact": "_builtin_skill_artifact",
    "hooks_artifact": "_builtin_hooks_artifact",
    "material_policy": "_builtin_material_policy",
    "accept_assessment": "_builtin_policy_decision",
    "reject_assessment": "_builtin_policy_decision",
    "inconclusive_assessment": "_builtin_policy_decision",
    "accept_support": "_builtin_accept_support",
    "refinement_policy": "_builtin_refinement_policy",
    "proposition": "_builtin_proposition",
    "observe": "_builtin_observe",
    "map_evidence": "_builtin_map_evidence",
    "combine_evidence": "_builtin_combine_evidence",
    "generate": "_builtin_generate",
    "compute": "_builtin_compute",
    "validator": "_builtin_validator",
    "validate": "_builtin_validate",
    "query": "_builtin_query",
    "resource_evidence": "_builtin_resource_evidence",
    "python_call": "_builtin_python_call",
    "tool_call": "_builtin_tool_call",
    "elaborate_proof": "_builtin_elaborate_proof",
    "kernel.check": "_builtin_kernel_check",
    "verify": "_builtin_verify",
}


class _BuiltinCheckingMixin(
    _BuiltinValuesMixin,
    _BuiltinEvidenceMixin,
    _BuiltinEffectsMixin,
    _BuiltinProofsMixin,
):
    def _infer_builtin_call(
        self, name, arguments, expression, scope, expected_type=None
    ):
        handler_name = _BUILTIN_HANDLERS.get(name)
        if handler_name is None:
            return None
        return getattr(self, handler_name)(
            _BuiltinCall(self, name, arguments, expression, expected_type, scope)
        )
