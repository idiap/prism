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

Provenance types record a value's origin and production history. Assurance
remains a separate dimension. Generated values begin as `Generated[T]`, and
deterministic computations begin as `Computed[T]`.

## The three provenance categories

| Type | Meaning | Introduced by |
| --- | --- | --- |
| `Generated[T]` | A generative model produced a value of type `T`. | `generate[T](request, model, access)` |
| `Evidence[T]` | A value of type `T` was observed with source provenance. | `observe(value, source, method)` or a typed source read |
| `Computed[T]` | A deterministic procedure computed a value of type `T`. | `compute(value, procedure)` |

Transitions between these categories require explicit functions.

## Generated values

Generation makes nondeterminism visible in both the result and effect row.

```prism
def assess(
    request: AssessmentRequest,
    model: Model,
    access: ModelGenerate,
) -> Result[Generated[Assessment], ModelFailure] ! {AI.Generate}:
    return generate[Assessment](request, model, access)
```

`Generated[Assessment]` records model origin. Stronger claims require an
explicit validator, material support policy, or proof boundary.

## Evidence values

`Evidence[T]` contains the observed value plus immutable provenance entries.
Each entry can record the following details.

- Source and acquisition method.
- Observation time.
- Transformation history.
- Assumptions.
- Integrity status.
- Additional typed runtime metadata.

For example, the following function records a release request as evidence.

```prism
def capture_release(change: ReleaseCandidate) -> Evidence[ReleaseCandidate]:
    return observe(
        change,
        source = "release request",
        method = "typed application input",
    )
```

Use `map_evidence` to transform evidence and `combine_evidence` to join packets.
Both retain upstream provenance and append the named transformation.

## Computed values

Use `Computed[T]` for the result of a deterministic program, simulator, or
checker when the procedure itself matters.

```prism
score = compute(candidate, procedure = "release-score-v2")
```

Determinism improves reproducibility. Specification checking requires
`Validated[value: T, P(value)]` when a named validator has checked the exact
value. A proposition checked by the kernel has type `Proof[P]`.

## Provenance survives assurance

Provenance and assurance can be nested while retaining both dimensions.

```text
Validated[
  value: Generated[Assessment],
  Acceptable(value)
]
```

This type says that a model produced the assessment and a named validator
accepted that exact generated value. Kernel proof requires a separate
`Proof[P]`.

Execution traces store provenance and assurance in separate fields. The
[Reasoning Log](../editors/vscode-run-explorer.md#reasoning-log) can therefore
show what happened without conflating origin with justification.

[Sources, connections, and resources](./sources-connections-resources.md)
explains how external reads introduce evidence. [Assurance and
inference](./assurance-types.md) explains the guarantees that can wrap a
provenanced value.
