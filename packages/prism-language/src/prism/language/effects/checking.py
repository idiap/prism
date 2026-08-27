# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Effect-row and capability checks."""

from __future__ import annotations


class EffectCheckError(ValueError):
    pass


def require_effects(
    declared: tuple[str, ...], required: tuple[str, ...], owner: str
) -> None:
    missing = sorted(set(required) - set(declared))
    if missing:
        raise EffectCheckError(
            f"`{owner}` is missing transitive effects: {', '.join(missing)}"
        )
