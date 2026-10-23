---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: provenance-types
title: Provenance types
description: Track how Prism values were generated, observed, or computed.
slug: /concepts/provenance-types
---

Provenance records actual production activity and upstream dependencies.
Assurance is a separate property: generated, acquired, asserted, and computed
values begin unchecked unless they carry an independently introduced guarantee.

## Origin wrappers and actual activities

| Type | Introduction | Meaning |
| --- | --- | --- |
| `Generated[T]` | Authorized `generate[T]` | Model-produced payload; fake generation is explicitly synthetic. |
| `Evidence[T]` | `observe` or a typed source read | An assertion or an adapter-captured acquisition. |
| `Computed[T]` | `compute(..., procedure = pure_function)` | Result of actually executing that function. |

The graph distinguishes `literal`, `supplied`, `asserted`, `generated`,
`acquired`, `computed`, and `external_unknown` producers. The normalized origin
constraint defaults to `unconstrained`. Wrappers impose compatible producer
requirements; ordinary records retain origins through their value references.

`observe(value, source = "label", method = "description")` records a source
assertion. The text cannot establish that a file, tool, or database was read.
Actual source/effect adapters capture acquisitions and retain effect records.
Available source metadata, implementation hashes, and synthetic markers remain
inspectable alongside ancestry.

## Execute transformations

This complete program returns computed evidence with assertion ancestry.

```prism executable
def increment(value: Int) -> Int:
    return value + 1

def main() -> Evidence[Int]:
    packet = observe(3, source = "user assertion", method = "typed input")
    return map_evidence(packet, transformation = increment)
```

`map_evidence(packet, extra_inputs..., transformation = callable)` passes the
packet's value and extra inputs to a pure, infallible callable.
`combine_evidence(packets..., transformation = callable)` supplies packet values
to a pure combiner. `compute(inputs..., procedure = callable)` invokes an
ordinary pure function and returns `Computed[Result]`. Strings and supplied
replacement results are no longer accepted transformation APIs.

Projection preserves the selected value's producer. A helper that returns its
input can therefore preserve that input's origin. New arithmetic records
computation; neither case loses the relevant generated/acquired ancestors.
Map keys and values have separate references, as do fields and collection
items. Copying a generated field into a computed record preserves that field's
model ancestry without marking unrelated literal fields as generated.

## Preserve origin across assurance

A validation can return `Validated[value: Generated[Draft], Acceptable(value)]`.
The validator's acceptance does not remove the original generation. Similarly,
proof pairing, accepted support, repeated state, and switch handoffs retain the
value references they depend on.

The refinement tutorial uses a generated narrative inside a computed plan and
then validates the plan. The [Reasoning Log](../editors/vscode-run-explorer.md#reasoning-log)
shows the declared constraints, actual producer, upstream activities, and
assurance separately. This is tracing of values and activities, not a complete
machine-instruction trace or an external provenance database.

See [assurance](./assurance-types.md) for the introduction boundaries and
[sources](./sources-connections-resources.md) for acquisition capabilities.
