---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: reasoning-types
title: Reasoning types
description: Choose the epistemic operation performed by each Prism reasoning occurrence.
slug: /concepts/reasoning-types
---

A reasoning type states the epistemic operation an occurrence performs.
Backend selection, provenance, and assurance remain separate.
`Deductive[Conclusion, Premises]`, for example, describes derivation from
explicit premises. Formal proof still requires `Proof[P]`.

## Standard reasoning types

Prism provides eight reasoning types in the standard library.

| Type | Use it to | Logical input |
| --- | --- | --- |
| `Deductive` | Derive a conclusion from explicit premises and valid rules. | `DeductionInput[Premises]` |
| `Abductive` | Propose an explanation, premise, or bridge. | `AbductionInput[Background, Observation]` |
| `Inductive` | Generalize provisionally from cases. | `InductionInput[Dataset, Population]` |
| `Analogical` | Transfer through an explicit correspondence. | `AnalogicalInput[Source, Target, Correspondence]` |
| `Contrastive` | Compare a baseline with an alternative. | `ContrastInput[Baseline, Alternative]` |
| `ModelBased` | Probe through an explicit model. | `ModelInput[Model, Inputs]` |
| `Refutational` | Search for contradictions or defeaters. | `RefutationInput[Subject, Search]` |
| `Evidential` | Calibrate status from observations and criteria. | `EvidentialInput[Observations, Criteria]` |

The language imports these type aliases from `prism.reasoning.methods`.

## Reasoning declarations

A `reasoning` declaration composes reasoning occurrences into a pure, reusable
topology.

```prism
reasoning ReleaseReadiness(
    change: ReleaseCandidate,
) -> Supported[ReadyToDeploy()]:
    sequence:
        [evidence: CaptureEvidence(change)]
        [checks: DeriveChecks(evidence)] by Requires
        [defeaters: FindDefeaters(DefeaterInput(checks = checks, change = change))] by Test
        [finding: SupportReadiness(ReadinessInput(evidence = evidence, checks = checks, defeaters = defeaters, change = change))] by Calibrate

    return finding
```

The names on the left, `evidence`, `checks`, `defeaters`, and `finding`, are
stable occurrence identities. They appear again in materialization and in the
runtime trace.

Operational choices such as models, prompts, tools, effects, permissions,
retries, and provider settings belong in materialization. An abstract reasoning
declaration contains only the epistemic topology. Execution requires a concrete
binding for every occurrence and attached relation.

## Composition

Reasoning uses each workflow composition form according to its exact meaning.

- `sequence` passes through ordered dependencies.
- `parallel` evaluates independent alternatives before a typed collector.
- `choice` selects exactly one exhaustive case.
- `repeat` re-executes a bounded body while carrying compatible state.

Relations attach to individual occurrences with `by Relation`. A relation
names exact source and target endpoints plus a certificate. Attach a relation
only to an occurrence, which has a single logical input.

## Materialization

Materialization binds the abstract topology to executable callables.

```prism
release_readiness = ReleaseReadiness(
    evidence = capture_release,
    checks = derive_checks,
    defeaters = find_defeaters,
    finding = support_readiness,
    checks_by = build_required,
    defeaters_by = build_tested,
    finding_by = build_calibrated,
)
```

Every occurrence and relation is bound exactly once. Concrete implementations
may add failures and effects while preserving the declared topology and
successful result types.

## Three independent questions

When selecting a reasoning type, answer three independent questions.

1. **Strategy.** What epistemic operation is being performed?
2. **Provenance.** Where did the value come from?
3. **Assurance.** What justifies accepting the value or proposition?

Continue with [provenance types](./provenance-types.md) and
[assurance and inference](./assurance-types.md) for the other two dimensions.
[Relations and materialization](./relations-materialization.md) explains the
executable binding contract.
