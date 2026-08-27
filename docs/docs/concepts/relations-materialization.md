---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: relations-materialization
title: Relations and materialization
description: Connect pure reasoning topology to executable callables and typed relation certificates.
slug: /concepts/relations-materialization
---

A reasoning declaration records epistemic intent. Materialization supplies the
callables that execute each occurrence and certify each relation. This split
keeps provider choices, effects, failures, and permissions out of reusable
reasoning topology.

## Pure reasoning topology

A reasoning declaration may contain reasoning calls, nested reasoning plans,
and pure structural constructors. It has no `fails` clause or effect row.

```prism
type Input:
    text: String

type Candidate:
    text: String

type Status:
    | Accepted
    | Refuted

type CandidateMethod = Input -> Candidate
type VerdictMethod = Candidate -> Status

reasoning Review(source: Input) -> Status:
    sequence:
        [candidate: CandidateMethod(source)]
        [status: VerdictMethod(candidate)] by Test
    return status
```

The occurrence names `candidate` and `status` remain stable through
materialization and execution tracing.

## Typed relations

A relation gives one epistemic edge an exact source type, target type, and
certificate type.

```prism
type Tested[SourceValue, TargetValue]:
    source: SourceValue
    target: TargetValue

relation Test[SourceValue, TargetValue](
    source: SourceValue,
    target: TargetValue,
) -> Tested[SourceValue, TargetValue]
```

`by Test` attaches the relation to one occurrence. Its source is the complete
logical input passed to that occurrence. Composition blocks such as `sequence`
and `parallel` have no single logical input, so a relation cannot attach to the
block itself.

The standard reasoning library provides these relation declarations.

| Relation | Recorded connection |
| --- | --- |
| `Requires` | The target depends on the source. |
| `Assume` | The target is considered under the source assumption. |
| `Test` | The target results from testing the source. |
| `Calibrate` | The target calibrates the source. |
| `Transfer` | The target transfers from the source. |
| `Probe` | The target probes the source. |
| `Preserve` | The target carries an exact preservation proof. |

These names describe edge semantics. The certificate type determines the
assurance carried by the edge.

## Material and strict certificates

An abstract relation can require material support.

```prism
def Addresses(draft: Draft, critique: Critique) -> Prop

relation TestsAddressing(
    source: Draft,
    target: Critique,
) |~ Addresses(source, target)
```

The result type is `Supported[Addresses(source, target)]`. Its materializer
must apply an explicit `MaterialPolicy` to evidence.

A strict relation can require a kernel proof.

```prism
def Correct(candidate: Candidate) -> Prop

relation EstablishesCorrectness(
    source: Premises,
    target: Candidate,
) |- Correct(target)
```

The result type is `Proof[Correct(target)]`. The materializer must return a
proof produced through theorem elaboration and kernel checking.

## Bind every occurrence and relation

Calling a reasoning declaration with named configuration produces a callable
materialization.

```prism
def form_candidate(source: Input) -> Candidate:
    return Candidate(text = source.text)

def accept_candidate(candidate: Candidate) -> Status:
    return Accepted()

def build_test(
    source: Candidate,
    target: Status,
) -> Tested[Candidate, Status]:
    return Tested(source = source, target = target)

configured_review = Review(
    candidate = form_candidate,
    status = accept_candidate,
    status_by = build_test,
)
```

Every occurrence and attached relation requires one binding. Extra, missing,
or incompatible bindings fail checking. Concrete occurrence callables may add
recoverable failures and effects. Prism infers them into the resulting
`Workflow` type.

A relation builder is pure. It receives the full semantic input and successful
target value. It returns the declared certificate directly or as
`Result[Certificate, Error]`.

## Adapt a concise topology input

An occurrence may display a concise dependency whose type differs from the
reasoning method input. An `<occurrence>_input` binding performs the pure
adaptation.

```prism
type Raw:
    text: String

type SemanticInput:
    raw: Raw
    prefix: String

type Assess = SemanticInput -> Status

reasoning AdaptedReview(raw: Raw) -> Status:
    [status: Assess(raw)]
    return status

def prepare_status(
    source: Raw,
    prefix: String,
) -> SemanticInput:
    return SemanticInput(
        raw = source,
        prefix = prefix,
    )

def assess_status(source: SemanticInput) -> Status:
    return Accepted()

adapted_review = AdaptedReview(
    status_input = prepare_status,
    status = assess_status,
)
```

The adapter must be pure and infallible. Fallible preparation belongs in an
ordinary workflow occurrence. Additional adapter parameters become explicit
inputs of the configured callable.

## Route guarded reasoning

A reasoning declaration may hand a guarded value to another reasoner.

```prism
type ReviewStatus = Input -> Status
type RepairStatus = Status -> Status

reasoning Repair(handoff: Status) -> Status:
    [status: RepairStatus(handoff)]
    return status

reasoning Review(source: Input) -> Status:
    [status: ReviewStatus(source)]
    on status.Refuted => switch @Repair
    return status
```

The switch materializer receives the guarded handoff as its first input. Any
model, permission, or operational input appears as an additional typed
parameter. A switch inside `repeat` resumes the loop after the selected
reasoner returns. A switch outside `repeat` exits through the selected
reasoner.

## Solve the declared reasoning

The configured callable constructs a workflow. `solve` checks the successful
result and materialization identity before execution.

```prism
def main() -> Status:
    source = Input(text = "candidate")
    flow = configured_review(source)
    return solve Review(source) using flow
```

[Execution and tracing](./execution-tracing.md) covers `solve`, `execute`, and
the relation events recorded in the trace.
