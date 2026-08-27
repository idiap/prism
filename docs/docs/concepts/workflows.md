---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: workflows
title: Workflows
description: Compose typed Prism callables with sequence, parallel, choice, and bounded repeat topology.
slug: /concepts/workflows
---

A workflow composes typed functions, agents, tools, and other workflows into an
executable topology. Its signature exposes the successful result, closed
failure type, and effect row. Its body contains bracketed occurrences and four
composition forms.

## Declare a workflow

The following workflow prepares and publishes a message in sequence.

```prism
type Message:
    text: String

def draft(text: String) -> Message:
    return Message(text = text)

def publish(draft: Message) -> Message:
    return draft

workflow publishing(text: String) -> Message:
    sequence:
        [draft: draft(text)]
        [published: publish(draft)]
    return published
```

`draft` and `published` are occurrence identities. The final `return` selects
one occurrence and must agree with the workflow result type.

Each explicit call shows the values passed to the component. This form keeps
data flow visible when the surrounding topology contains several compatible
bindings. A concise occurrence can also resolve component ports by exact name.

```prism
[published: publish(draft)]
```

The checker reports a missing port when an input name is unavailable and a type
error when an available value has an incompatible type.

## Composition forms

Use the form whose execution structure matches the callable dependencies.

| Form | Checked structure |
| --- | --- |
| `sequence` | Children execute in order and later nodes can consume earlier occurrences. |
| `parallel` | Branches begin from the same environment and must produce distinct occurrence names. |
| `choice` | A closed sum value selects one exhaustive case and all arms converge to the same outputs. |
| `repeat` | A positive static bound controls iteration and compatible occurrences carry state. |

Nested forms create one visible topology.

```prism
workflow inspect_change(
    change: Change,
) -> Review:
    sequence:
        parallel:
            [tests: run_tests(change)]
            [analysis: inspect_static(change)]
        [draft: assemble_review(change, tests, analysis)]
        repeat refinement_policy(3):
            [draft: refine_review(draft)]
    return draft
```

Parallel branch outputs join after the block. Duplicate occurrence names across
branches are rejected.

## Route with a closed sum

A choice router must return a closed sum type. Every constructor requires a
case unless a `_` case covers the remainder.

```prism
type ReviewRoute:
    | Automatic
    | Manual

workflow route_review(submission: Submission) -> Review:
    choice [route: choose_route(submission)]:
        case Automatic:
            [review: automatic_review(submission)]
        case Manual:
            [review: manual_review(submission)]
    return review
```

Every arm above produces `review` with the same type. Duplicate constructors,
unknown constructors, missing cases, and divergent outputs fail checking.

## Bound a repeat

`refinement_policy` creates a `RefinementPolicy` with a positive static
iteration bound.

```prism
workflow refine(initial: Draft) -> Draft:
    repeat refinement_policy(3):
        [initial: revise(initial)]
    return initial
```

Reusing `initial` marks a loop carried occurrence. Every iteration must return
the same type as the incoming value.

An optional pure Boolean expression can stop the loop early.

```prism
repeat refinement_policy(5, until = state.Finished):
    [state: revise(state)]
```

The static bound remains mandatory and prevents an unbounded execution path.

## Declare failures and effects

A workflow collects failures and effects from every component. Its signature
must cover the complete surface.

```prism
workflow create_review(
    task: ReviewTask,
) -> Generated[Review]
    fails ModelFailure
    ! {AI.Generate, Context.Disclose}:
    [review: reviewer(task)]
```

When a component returns `Result[T, E]`, the successful occurrence has type
`T` and `E` enters the workflow failure surface. Missing failures or effects
produce checker diagnostics.

## Construct and execute

Calling a workflow constructs a pure `Workflow` value. `solve`
executes that value.

```prism
flow: Workflow[Message, Never] = publishing("ready")

def main() -> Message:
    return solve flow
```

Only `def main` can serve as the application entry. A `workflow main`
declaration is rejected.

Abstract epistemic topology belongs in a `reasoning` declaration. A concrete
workflow can materialize that topology and is selected with
`solve Reasoning(inputs) using flow`.

Continue with [execution and tracing](./execution-tracing.md) for runtime
resolution, [reasoning types](./reasoning-types.md) for abstract topology, and
[agents](./agents.md) for generated workflow nodes.
