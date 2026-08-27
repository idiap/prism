---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: language-foundations
title: Language foundations
description: Define Prism modules, immutable values, domain types, and pure functions.
slug: /concepts/language-foundations
---

Prism uses a small typed functional core. Values are immutable. Public inputs
and results carry explicit types. A function remains pure unless its signature
declares an effect row.

## Modules and bindings

Each `.prism` file forms a module. Absolute imports name the full module path.
A leading dot selects a relative import.

```prism
from prism.reasoning.methods.deductive import DeductionInput
from release.contracts import ReleaseCandidate
import release.rules as rules
```

A binding introduces one immutable value.

```prism
enabled: Bool = True
attempts: Nat = 3
labels: List[String] = ["checked", "approved"]
limits: Map[String, Int] = {"cpu": 4, "memory_gb": 16}
```

Imported names and local bindings keep their value for the rest of their
scope. A `repeat` composition has a separate rule for values carried from one
iteration to the next.

## Domain types

A field block declares an immutable record.

```prism
type ReleaseCandidate:
    name: String
    tests_passed: Bool
    approved: Bool

candidate = ReleaseCandidate(
    name = "release-2026.08",
    tests_passed = True,
    approved = True,
)
```

A variant block declares a closed sum. Pattern matching must cover every
reachable constructor.

```prism
type Decision:
    | Accept
    | Reject(reason: String)

def message(decision: Decision) -> String:
    match decision:
        case Accept:
            return "accepted"
        case Reject(reason):
            return reason
```

Aliases and generic types use the same `type` declaration.

```prism
type UserId = String
type Pair[Left, Right] = (Left, Right)
type Tree[Value]:
    | Leaf(value: Value)
    | Branch(left: Tree[Value], right: Tree[Value])
```

The standard containers are `List`, `Set`, `Map`, `Option`, and `Result`.
Scalar types include `Bool`, `Nat`, `Int`, `Float`, `Decimal`, `String`,
`Bytes`, `Time`, and `Duration`.

## Refinement types

A refinement adds a predicate to an existing representation.

```prism
type Probability = Float where 0.0 <= self and self <= 1.0
type Vector[Element, size: Nat] = List[Element] where length(self) == size
```

A dynamic value enters a refinement through a checked constructor or proof.
The checker rejects an unchecked conversion.

`Type` classifies ordinary types. `Prop` classifies propositions used by
material and strict inference.

## Pure functions

Functions declare typed parameters and one result. Generic binders appear in
brackets.

```prism
def identity[Value](value: Value) -> Value:
    return value

def ready(candidate: ReleaseCandidate) -> Bool:
    return candidate.tests_passed and candidate.approved
```

Conditional expressions evaluate one branch. Both branches must have
compatible types.

```prism
def clamp_nonnegative(value: Float) -> Float:
    return value if value >= 0.0 else 0.0
```

Recursion uses `def`. The compiler requires a structural or explicit
well-founded termination argument.

## Function types

The arrow syntax describes callable contracts.

```text
String -> Nat
(Repository, Depth) -> Analysis
(Path, FileRead[path]) -> Result[String, IOError] ! {File.Read}
```

The last contract includes a recoverable failure, a permission parameter, and
an effect row. [Effects, failures, and permissions](./effects-failures-permissions.md)
explains each part.

## Application entry

One top-level `def main` serves as the application entry.

```prism
def main() -> Bool:
    return ready(candidate)
```

`main` receives runtime capabilities and variable application inputs through
typed parameters. A `workflow main` declaration cannot serve as the entry.
