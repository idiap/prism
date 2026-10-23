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

Assurance is independent of reasoning classification and origin. A method label,
a deterministic run, and a source assertion do not establish acceptance.

## Exact claims

A proposition is a pure `Prop` declaration. Its application checks argument
arity/types and retains resolved module identity, dependent binders, and actual
runtime values. Rendered names do not establish claim equality.

## Assurance contracts

| Type | Meaning |
| --- | --- |
| Ordinary `T` | Unchecked assurance. |
| `Assessment[P]` | A completed accepted, rejected, or inconclusive policy decision. |
| `Supported[P]` | An accepted assessment was explicitly admitted as support. |
| `Validated[value: T, P(value)]` | A registered validator accepted this exact value. |
| `CoreTerm[P]` | An elaborated candidate awaiting kernel checking. |
| `Proof[P]` | A native derivation of the exact target, retaining assumptions. |
| `Verified[value: T, P(value)]` | The exact value paired with a checked proof about it. |

Protected types have no public constructors, implicit conversions, or promotion
through `Any`. External tools can propose ordinary values and proof syntax;
they cannot create protected assurance.

## Material assessment and accepted support

`material_policy(name, evaluator = callable)` binds a typed evaluator receiving
the evidence and actual claim arguments. Its effects and failure type are
preserved. The name labels the policy; it cannot replace evaluation.

```prism title="Explanatory fragment"
assessment = try observations |~[engineering_policy] Promising(design)
support = try accept_support(assessment)
```

The first expression returns `Result[Assessment[Promising(design)], Failure]`.
A successful policy execution can still reject the claim or leave it
inconclusive. `Err(Failure)` means evaluation did not complete.
`accept_support` returns `Supported` only for an accepted assessment; otherwise
it returns `SupportError`. There is no rejected `Supported` value.

A `|~` relation requires accepted support for its actual source and target.
Support is defeasible and cannot become proof through a method label.

## Registered validation

This complete program validates a positive number.

```prism executable
def Positive(value: Int) -> Prop

def positive(value: Int) -> Bool:
    return value > 0

positive_validator = validator[value: Int, Positive(value)](positive)

def main() -> Result[Validated[value: Int, Positive(value)], ValidationError]:
    return validate[Positive(3)](3, validator = positive_validator)
```

Registration requires a pure, infallible Boolean callable with the exact input
type. Validation invokes it on the subject and records its identity, hash, and
claim. A false result yields `ValidationError`. String labels and precomputed
Boolean requirements cannot substitute for the validator.

The registration expresses trust in this implementation's interpretation of
`Positive`; it does not prove soundness. Validation preserves the exact input
and its provenance, including generated data inside a validated record.

## Native proof and pairing

```prism executable
def Same(left: Nat, right: Nat) -> Prop:
    return left == right

def main() -> Result[Verified[value: Nat, Same(value, 7)], ProofError]:
    version: Nat = 7
    term = try elaborate_proof[Same(version, 7)]("rfl")
    proof = try kernel.check(term)
    return Ok(verify(version, proof))
```

Elaboration targets the actual value-specific proposition; the kernel checks
the term; `verify` checks that the proof refers to the paired value. A proof
about `7` cannot certify `9`, even if a local binding shadows a global name.
The trace retains proof, proposition, environment hashes, and axiom dependencies.

Runtime value instantiation currently supports native natural numbers and
Booleans. Unsupported records, strings, floats, and negative integers receive
a diagnostic. Abstract propositions and arbitrary domain models are not
automatically formalized. A conditional theorem retains its assumptions and
does not establish their real-world truth.

The strict release example proves a property of its returned version. The
refinement example validates under a simulator model and supplies accepted
material support; it does not prove physical landing safety.

See [provenance](./provenance-types.md), [reasoning](./reasoning-types.md), and
[relations](./relations-materialization.md) for the independent contracts.
