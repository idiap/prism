---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: prism-materialization
description: Implement, refactor, or review executable PRISM workflows and concrete materializations of `reasoning` declarations, including occurrence, relation, input-adapter, switch, agent, effect, failure, permission, and validation bindings. Do not use for designing pure epistemic topology or Python runtime bindings.
---

# PRISM Materialization

Turn an abstract reasoning plan into the smallest executable workflow without changing its epistemic meaning.

## Inspect the contract first

Read sections 5, 6, 7, 8.1, 8.3, and 8.4 of `notes/SYNTAX.md`, the reasoning declaration being materialized, and the closest executable `materialization.prism` under `examples/language/`. If the task changes the abstract topology or method selection, also apply [prism-epistemic-reasoning](../prism-epistemic-reasoning/SKILL.md).

Define the real success value and identify every abstract occurrence, relation edge, input adaptation, guarded switch, failure, effect, and required capability before implementing.

## Bind the topology exactly

- Configure a reasoning declaration through a direct named call such as `Plan(occurrence = implementation, occurrence_by = relation_builder)`.
- Bind every occurrence and related edge exactly once. Do not add, omit, reorder, or rename epistemic steps while materializing them.
- Return the exact successful result required by each reasoning method. Concrete implementations may add recoverable failures and effects; these become part of the resulting `Workflow` type.
- Implement a relation edge as a pure two-input function over the occurrence's complete semantic input and target. Return the exact declared certificate, directly or as `Result[Certificate, Error]` when allowed.
- When visible topology input differs from a method's semantic input, bind `<occurrence>_input` to a pure infallible adapter returning the exact method input type. Keep fallible preprocessing as an ordinary workflow step.
- A switch materializer receives the guarded handoff first. Declare any additional operational inputs explicitly.
- Do not use obsolete `Reasoning.Implementation(...)`, `ReasoningSwitches(...)`, or `using = implementation` forms.

## Prefer deterministic implementation

1. Use pure functions, typed transformations, strict inference, deterministic validation, counterexample search, elaboration, and kernel checking wherever adequate.
2. Add material inference or generation only for the exact nondeterministic subtask.
3. Keep generated values as `Generated[T]` until an explicit validator succeeds. Never present `Supported[P]` as `Proof[P]`.
4. External provers or models may propose `ProofSyntax`; target-directed elaboration and the PRISM kernel must establish `Proof[P]`.

## Bound agentic work

- Identify the agent's typed input, output, failure, effects, and permission surface.
- Apply the narrowest available skill for the nondeterministic subtask and activate it for a stable scope.
- Pass functions, tools, models, permissions, and capabilities through exact typed ports; do not rely on ambient capabilities.
- Keep `AI.Generate` or `ModelGenerate` in the agent or ordinary workflow component. A skill constrains work but does not own generation.
- Route model output through deterministic parsing, validation, counterexample search, elaboration, or proof checking before downstream use.
- If no applicable skill covers the subtask, implement only the minimal typed boundary and report the uncovered capability.

## Make operations explicit

- Receive variable domain data, policies, connections, providers, models, capabilities, permissions, and environment settings as typed inputs or runtime configuration.
- Keep credentials, endpoints, local paths, module paths, commands, and deployment settings out of reusable PRISM source.
- Declare effects and failures on the component that performs them. Supply authority explicitly at the call boundary.
- Return the useful domain value, not a configuration object or trace unless the caller requests it.
- Use real complete values; do not create placeholders, fake evidence, empty branches, or unused scaffolding.

## Encode workflow loops correctly

Use `repeat refinement_policy(bound, until = condition)` when steps re-execute. The bound must be positive and static; `until` must be a Boolean produced by the body. Rebind a visible type-compatible state value so each iteration consumes the previous iteration's state. Put one-time initialization before the loop and post-loop validation after it.

## Verify the executable boundary

Run the applicable checks on the real entry point:

```bash
uv run prism check path/to/main.prism
uv run prism compile path/to/main.prism
uv run prism run path/to/main.prism --handler fake
uv run pytest path/to/relevant_test.py
```

Confirm that every occurrence, relation, adapter, and switch is bound; topology is preserved; capabilities are explicit; generated, supported, validated, and proven values remain distinct; and all declarations contribute to the returned result or assurance trace.
