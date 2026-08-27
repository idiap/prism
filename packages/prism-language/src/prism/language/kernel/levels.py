# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Universe levels for Prism core calculus v1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .diagnostics import KernelError


@dataclass(frozen=True, slots=True)
class LevelZero:
    pass


@dataclass(frozen=True, slots=True)
class LevelVar:
    name: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "a").isalnum():
            raise KernelError(
                f"invalid universe variable `{self.name}`",
                code="kernel-invalid-level",
            )


@dataclass(frozen=True, slots=True)
class LevelSucc:
    of: "Level"


@dataclass(frozen=True, slots=True)
class LevelMax:
    left: "Level"
    right: "Level"


Level: TypeAlias = LevelZero | LevelVar | LevelSucc | LevelMax
ZERO = LevelZero()


def level_from_int(value: int) -> Level:
    if value < 0:
        raise KernelError(
            "universe levels cannot be negative", code="kernel-invalid-level"
        )
    level: Level = ZERO
    for _ in range(value):
        level = LevelSucc(level)
    return level


def level_to_int(level: Level) -> int | None:
    count = 0
    while isinstance(level, LevelSucc):
        count += 1
        level = level.of
    return count if isinstance(level, LevelZero) else None


def normalize_level(level: Level) -> Level:
    if isinstance(level, LevelZero | LevelVar):
        return level
    if isinstance(level, LevelSucc):
        return LevelSucc(normalize_level(level.of))
    values: list[Level] = []

    def collect(value: Level) -> None:
        value = normalize_level(value)
        if isinstance(value, LevelMax):
            collect(value.left)
            collect(value.right)
        else:
            values.append(value)

    collect(level.left)
    collect(level.right)
    unique = {repr(value): value for value in values}
    values = list(unique.values())
    closed = [value for value in values if level_to_int(value) is not None]
    open_values = [value for value in values if level_to_int(value) is None]
    if closed:
        largest = max(closed, key=lambda value: level_to_int(value) or 0)
        if level_to_int(largest) != 0 or not open_values:
            open_values.append(largest)
    values = sorted(open_values, key=repr)
    if len(values) == 1:
        return values[0]
    successors = [value for value in values if isinstance(value, LevelSucc)]
    if values and len(successors) == len(values):
        nested = successors[0].of
        for value in successors[1:]:
            nested = LevelMax(nested, value.of)
        return LevelSucc(normalize_level(nested))
    result = values[0]
    for value in values[1:]:
        result = LevelMax(result, value)
    return result


def level_max(left: Level, right: Level) -> Level:
    return normalize_level(LevelMax(left, right))


def level_leq(left: Level, right: Level) -> bool:
    left, right = normalize_level(left), normalize_level(right)
    if left == right:
        return True
    left_int, right_int = level_to_int(left), level_to_int(right)
    if left_int is not None and right_int is not None:
        return left_int <= right_int
    if isinstance(left, LevelZero):
        return True
    if isinstance(left, LevelMax):
        return level_leq(left.left, right) and level_leq(left.right, right)
    if isinstance(right, LevelMax):
        return level_leq(left, right.left) or level_leq(left, right.right)
    if isinstance(left, LevelSucc) and isinstance(right, LevelSucc):
        return level_leq(left.of, right.of)
    if isinstance(right, LevelSucc):
        return level_leq(left, right.of)
    return False


def level_variables(level: Level) -> frozenset[str]:
    if isinstance(level, LevelZero):
        return frozenset()
    if isinstance(level, LevelVar):
        return frozenset({level.name})
    if isinstance(level, LevelSucc):
        return level_variables(level.of)
    return level_variables(level.left) | level_variables(level.right)


def substitute_level(level: Level, substitutions: Mapping[str, Level]) -> Level:
    if isinstance(level, LevelZero):
        return level
    if isinstance(level, LevelVar):
        return substitutions.get(level.name, level)
    if isinstance(level, LevelSucc):
        return normalize_level(LevelSucc(substitute_level(level.of, substitutions)))
    return level_max(
        substitute_level(level.left, substitutions),
        substitute_level(level.right, substitutions),
    )
