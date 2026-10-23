# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Reasoning configuration schema and inference entry point."""

from __future__ import annotations

from typing import Mapping

from prism.language.core import (
    CallableContract,
    CoreType,
)

from ...syntax.ast import (
    CallExpr,
    NodeOccurrence,
    ReasoningDecl,
)
from ..base import _CheckerPhase
from ..helpers import (
    _composition_nodes,
    _expand_aliases,
)
from .configuration import _ReasoningConfiguration


class _ReasoningCheckingMixin(_CheckerPhase):
    def _reasoning_configuration_names(
        self,
        reasoning_name: str,
        declaration: ReasoningDecl,
    ) -> tuple[str, ...]:
        method_contracts = self.reasoning_methods.get(reasoning_name, {})
        occurrence_names = tuple(method_contracts)
        input_names = tuple(
            f"{node.alias}_input"
            for node in _composition_nodes(declaration.composition)
            if node.alias
            and self._reasoning_node_requires_input_adapter(node, method_contracts)
        )
        relation_names = tuple(
            f"{node.alias}_by"
            for node in _composition_nodes(declaration.composition)
            if node.alias and node.relation
        )
        switch_names = tuple(
            dict.fromkeys(
                exit_.target.rsplit(".", 1)[-1]
                for exit_ in declaration.exits
                if exit_.action == "switch" and exit_.target
            )
        )
        return (*occurrence_names, *input_names, *relation_names, *switch_names)

    def _reasoning_node_requires_input_adapter(
        self,
        node: NodeOccurrence,
        method_contracts: Mapping[str, CoreType],
    ) -> bool:
        if not node.alias or not isinstance(node.component, CallExpr):
            return False
        method_type = method_contracts.get(node.alias)
        if method_type is None or len(method_type.parameters) != 1:
            return False
        logical_input = node.component.arguments[0].value
        topology_input = self.expression_types.get(id(logical_input))
        if topology_input is None:
            return False
        semantic_input = method_type.parameters[0][1]
        return _expand_aliases(
            topology_input, self.aliases, self.type_parameters
        ) != _expand_aliases(semantic_input, self.aliases, self.type_parameters)

    def _infer_reasoning_configuration(
        self,
        reasoning_name: str,
        contract: CallableContract,
        declaration: ReasoningDecl,
        expression: CallExpr,
        argument_types: list[tuple[str | None, CoreType]],
    ) -> tuple[CoreType, tuple[str, ...]]:
        return _ReasoningConfiguration(
            self, reasoning_name, contract, declaration, expression, argument_types
        ).check()
