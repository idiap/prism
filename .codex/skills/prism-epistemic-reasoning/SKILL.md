---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: prism-epistemic-reasoning
description: "Create, refactor, or review pure PRISM epistemic topology: `reasoning` declarations, standard reasoning methods, occurrence inputs, typed relations, guarded exits, and reasoning loops. Do not use for concrete materialization, runtime backends, or Python bindings."
---

# PRISM Epistemic Reasoning

Express reusable epistemic intent as a pure, non-executable topology with exact logical inputs, results, relations, and control flow.

## Ground the declaration

1. Read `notes/CORE_PRINCIPLES.md`, sections 6 and 8.2 of `notes/SYNTAX.md`, the relevant method contracts under `libs/prism/reasoning/methods/`, and the closest executable `reasoning.prism` under `examples/language/`.
2. Define the reasoning's real input, useful result, propositions, provenance, and assurance level before laying out occurrences.
3. Keep strategy, provenance, and assurance independent. Material support is not proof, and generated output is not validated output.

## Select exact epistemic methods

For each occurrence, choose the closest standard method by semantic role:

- `Deductive` derives from explicit premises and rules.
- `Abductive` proposes an explanation, premise, or bridge.
- `Inductive` generalizes provisionally from cases.
- `Analogical` transfers through an explicit correspondence.
- `Contrastive` compares a baseline with an alternative.
- `ModelBased` probes through an explicit model.
- `Refutational` searches for contradictions or defeaters.
- `Evidential` calibrates status from evidence and tests.

Use the standard method's exact input record or a pure structural constructor. Do not declare a new method merely to reshape input. Declare a custom reasoning method only when no standard method performs the epistemic operation; state why the standard methods are insufficient and give the custom method one exact logical input and result.

Deterministic collection, record assembly, validation, formatting, and other structural computation are functions or workflow components, not reasoning methods.

## Keep reasoning operationally pure

A `reasoning` declaration:

- has no `fails` clause or effect row;
- contains only reasoning calls, nested reasoning plans, and pure infallible structural constructors;
- contains no models, agents, callable skills, tools, sources, prompts, retries, effects, failures, permissions, adapters, provider choices, or backend settings; and
- cannot execute until every abstract part is materialized.

Keep the reasoning declaration in `reasoning.prism`, separate from executable implementation. Preserve descriptive domain names for occurrences and exact explicit data dependencies.

## Model topology and relations precisely

- Give every leaf a unique output name and an explicit call. Use `sequence`, `parallel`, `choice`, and `repeat` for their actual semantics.
- Use `parallel` followed by a typed collector to form alternatives. Use `choice` only to select exactly one exhaustive case.
- Attach `by Relation` only to an occurrence; composition blocks do not have the single explicit logical input a relation requires.
- Declare every relation with exact source and target endpoints and an exact certificate: `|~` for `Supported[P]`, `|-` for `Proof[P]`, or `-> Certificate` for a nominal witness.
- Put the evidence, policy, proof construction, and relation implementation in materialization, not in the relation declaration.
- Preserve guarded exits and switch handoffs explicitly. A materializer must receive the exact guarded value.

## Encode repetition as repetition

When the topology re-executes steps, use `repeat`; a sequential block, comment, or occurrence name ending in `loop` is not a loop.

- Give `refinement_policy` a positive static bound.
- When success can terminate the loop, set `until` to a Boolean expression produced by the body.
- Carry state by rebinding a visible, type-compatible value that the next iteration consumes.
- Keep one-time initialization before `repeat` and post-loop validation after it when those steps should not recur.

```prism
[state: initialize(source)]
repeat refinement_policy(10, until = state.accepted):
    [assessment: Assess(state)]
    [state: Revise(assessment)]
[validated: Validate(state)]
```

## Check the result

Run `uv run prism check` and `uv run prism compile` on the nearest real entry point that imports the reasoning. Confirm that every occurrence uses the closest semantic method, every relation has exact endpoints, every loop carries changing state, and no operational choice leaked into the reasoning file.
