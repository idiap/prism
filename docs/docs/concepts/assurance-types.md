---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: assurance-types
title: Assurance and inference
description: Represent material support, deterministic validation, and propositions checked by the Prism kernel.
slug: /concepts/assurance-types
---

Assurance types state why a value or proposition may be accepted. Prism keeps
material support, deterministic validation, and formal proof as separate
guarantees. Every transition names the policy, validator, elaborator, or kernel
operation that justifies it.

## Propositions

`Prop` is the type of propositions. A pure proposition can have a body.

```prism
def Ready(change: Change) -> Prop:
    return TestsPass(change) and Approved(change)
```

An abstract proposition may omit its body. The declaration names the claim and
leaves its support or proof to a materialization.

```prism
def Addresses(draft: Draft, critique: Critique) -> Prop
```

Propositions compose with `and`, `or`, `not`, `->`, `forall`, and `exists`.
A Boolean computes a truth value. A proposition can appear as an index in
`Supported[P]`, `Proof[P]`, and other assurance types.

## Assurance levels

| Type | Guarantee |
| --- | --- |
| `T` | An ordinary value with no additional assurance. |
| `Supported[P]` | Evidence was assessed under a named material policy for `P`. |
| `Validated[value: T, P(value)]` | A named deterministic validator accepted this exact value against `P`. |
| `CoreTerm[P]` | Proof source was elaborated for `P` and awaits kernel checking. |
| `Proof[P]` | Prism's trusted kernel checked a strict proof of `P`. |
| `Verified[value: T, P(value)]` | The exact value is paired with a kernel checked proof. |

Protected assurance types have no public constructors or implicit conversions.

## Material support

Material inference uses `|~` and requires an explicit policy.

```prism
support = observations |~[engineering_policy] Promising(design)
```

For a compatible `MaterialPolicy`, the expression has this contract.

```text
Evidence[Observation] |~[policy] Proposition
    -> Result[Supported[Proposition], Failure] ! Effects
```

Material support is defeasible. New evidence or a changed policy can alter the
status.

### Support status and operational failure

A completed policy assessment returns `Supported[P]`. The value records an
accepted or rejected status together with the policy and evidence trace.

An `Err(error)` means the policy evaluator could not complete. A rejected
`Supported[P]` means the evaluator completed and its requirements were not
satisfied.

| Result | Meaning |
| --- | --- |
| Accepted `Supported[P]` | The named policy supports `P`. |
| Rejected `Supported[P]` | The named policy does not support `P` for this evidence. |
| `Err(Failure)` | The policy evaluator failed to produce a decision. |

`|~` only introduces material support. It cannot produce `Proof[P]`.

## Validation

Validation checks one exact value against a proposition.

```prism
validated = validate[Acceptable(candidate)](
    candidate,
    validator = "release-policy-v2",
    require = checks,
)
```

The result is `Validated[value: T, P(value)]` or `ValidationError`. The type
retains the exact input, including any provenance wrapper.

```text
Validated[
    value: Generated[Assessment],
    Acceptable(value),
]
```

Validation establishes that a named deterministic check accepted the value.
Kernel assurance for the validator requires a separate proof of its soundness.

## Strict inference

Strict inference uses `|-` in theorem statements and typed proof obligations.
A theorem consumes proof premises and returns a proof of its conclusion.

```prism
theorem ready_from_parts(
    change: Change,
    tests: Proof[TestsPass(change)],
    approval: Proof[Approved(change)],
) : {tests, approval} |- Ready(change) := by
    unfold Ready
    exact And.intro(tests, approval)
```

The premises inside `{}` are proof values. The tactic block constructs a core
term. The trusted kernel checks that term before it returns
`Proof[Ready(change)]`.

Core tactics include these operations.

```text
exact  assumption  intro  apply  constructor  cases  induction
rewrite  unfold  simp  decide
```

## Proof source from an external system

A model or external prover may propose proof syntax. Prism applies two native
boundaries before the proposition gains strict assurance.

```text
proof source
    -> elaborate_proof[P]
    -> CoreTerm[P]
    -> kernel.check
    -> Proof[P]
```

Elaboration checks the source against a proposition chosen by the Prism caller.
The kernel checks the elaborated term. External code cannot construct
`CoreTerm[P]` or `Proof[P]` through a tool or Python effect.

## Verified values

`Verified[value: T, P(value)]` keeps a useful domain value and its proof
together. The value remains available through `.value` while the verified type
retains its proof.

```prism
verified = verify(candidate, proof)
```

Use this type when a consumer needs the value and kernel assurance about that
exact value.

## Choose the required assurance

| Requirement | Result type |
| --- | --- |
| Ordinary computation | `T` |
| Defeasible policy decision | `Supported[P]` |
| Deterministic acceptance of one value | `Validated[value: T, P(value)]` |
| Strict derivation of a proposition | `Proof[P]` |
| Value paired with strict derivation | `Verified[value: T, P(value)]` |

Reasoning strategy and provenance remain independent. A `Deductive`
occurrence identifies an epistemic operation. Proof and validation require
their explicit assurance transitions.

[Relations and materialization](./relations-materialization.md) explains
material and strict relation certificates. [Provenance types](./provenance-types.md)
explains `Generated`, `Evidence`, and `Computed` values.
