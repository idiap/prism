# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Collection literal and index inference."""

from __future__ import annotations

from prism.language.core import (
    BindingScope,
    CoreType,
)

from ...syntax.ast import (
    IndexExpr,
    ListExpr,
    MapExpr,
    TupleExpr,
)
from ..base import _CheckerPhase


class _CollectionInferenceMixin(_CheckerPhase):
    def _infer_list(
        self,
        expression: ListExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        items = [
            self._infer(item, scope, enclosing_result) for item in expression.items
        ]
        item_types = [item_type for item_type, _ in items]
        effects.extend(effect for _, item_effects in items for effect in item_effects)
        if item_types and all(item.name == "Skill" for item in item_types):
            type_ = CoreType(
                "Skills",
                tuple(
                    item.arguments[0] if item.arguments else CoreType("Any")
                    for item in item_types
                ),
            )
        elif item_types and all(item.name == "Tool" for item in item_types):
            type_ = CoreType(
                "Tools",
                tuple(
                    item.arguments[0] if item.arguments else CoreType("Any")
                    for item in item_types
                ),
            )
        elif (
            not item_types
            and expected_type is not None
            and expected_type.name in {"Skills", "Tools"}
        ):
            type_ = expected_type
        else:
            type_ = CoreType(
                "List", (item_types[0] if item_types else CoreType("Never"),)
            )
            for item in item_types[1:]:
                self._expect(type_.arguments[0], item, expression.span, "list element")

        return type_, tuple(effects)

    def _infer_tuple(
        self,
        expression: TupleExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        items = [
            self._infer(item, scope, enclosing_result) for item in expression.items
        ]
        effects.extend(effect for _, item_effects in items for effect in item_effects)
        type_ = CoreType(
            "Tuple",
            tuple(item_type for item_type, _ in items),
        )

        return type_, tuple(effects)

    def _infer_map(
        self,
        expression: MapExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        inferred_pairs = [
            (
                self._infer(key, scope, enclosing_result),
                self._infer(value, scope, enclosing_result),
            )
            for key, value in expression.items
        ]
        pairs = [
            (key_result[0], value_result[0])
            for key_result, value_result in inferred_pairs
        ]
        effects.extend(
            effect
            for key_result, value_result in inferred_pairs
            for item_effects in (key_result[1], value_result[1])
            for effect in item_effects
        )
        type_ = CoreType(
            "Map",
            (
                (pairs[0][0], pairs[0][1])
                if pairs
                else (CoreType("Never"), CoreType("Never"))
            ),
        )

        return type_, tuple(effects)

    def _infer_index(
        self,
        expression: IndexExpr,
        scope: BindingScope,
        enclosing_result: CoreType | None,
        expected_type: CoreType | None = None,
    ) -> tuple[CoreType, tuple[str, ...]]:
        effects: list[str] = []
        collection, collection_effects = self._infer(
            expression.value, scope, enclosing_result
        )
        index, index_effects = self._infer(expression.index, scope, enclosing_result)
        effects.extend((*collection_effects, *index_effects))
        if collection.name != "List" or len(collection.arguments) != 1:
            self.fail(
                "indexing requires a List value",
                expression.value.span,
                "type-list-index-owner",
            )
        if index.name not in {"Int", "Nat"}:
            self.fail(
                "list index must be Int or Nat",
                expression.index.span,
                "type-list-index",
            )
        type_ = collection.arguments[0]

        return type_, tuple(effects)
