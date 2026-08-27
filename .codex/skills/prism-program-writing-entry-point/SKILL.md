---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: prism-program-writing-entry-point
description: Plan, wire, validate, refactor, or review a complete executable PRISM program across its reasoning, materialization, adapters, and application entry point. Use for end-to-end `.prism` work or when the correct PRISM layer is not yet clear; use a narrower PRISM skill for a task confined to one layer.
---

# PRISM Program Writing Entry Point

Produce the smallest complete PRISM program that returns the requested domain value with explicit types, dependencies, authority, effects, failures, provenance, and assurance.

## Route the work

Read and apply only the specialized skills required by the task:

- For abstract reasoning declarations, occurrences, relations, switches, or epistemic method selection, use [prism-epistemic-reasoning](../prism-epistemic-reasoning/SKILL.md).
- For executable workflows and concrete bindings of abstract reasoning, use [prism-materialization](../prism-materialization/SKILL.md).
- For typed `Python.Call` effects and their Python implementations, use [prism-python-adapter](../prism-python-adapter/SKILL.md).

Use this skill with every applicable specialized skill for end-to-end work. Do not load an unrelated specialization merely because it exists.

## Establish the contract

1. Read `notes/CORE_PRINCIPLES.md`, the relevant sections of `notes/SYNTAX.md`, and the closest executable example under `examples/language/`. Treat current executable examples as the source of truth for supported syntax.
2. Define the useful domain result, real inputs, domain types, propositions, failures, effects, permissions, and required assurance level before choosing orchestration.
3. Prefer pure functions, typed transformations, strict inference, deterministic validators, and kernel checking. Add material inference or generation only where deterministic methods are inadequate.
4. Keep `Generated[T]`, `Evidence[T]`, `Computed[T]`, `Supported[P]`, `Validated[...]`, `Proof[P]`, and `Verified[...]` distinct. No provenance category implies assurance.

## Keep the program complete and minimal

- Receive variable domain data, policies, connections, capabilities, permissions, and environment settings through typed parameters, imports, or runtime configuration.
- Keep credentials, endpoints, local paths, provider and model names, commands, and deployment settings out of reusable PRISM source.
- Define a constant only for a genuine domain invariant; do not add speculative configuration.
- Prefer `import package.module as module` and qualified access such as `module.Name` when consuming several exports. Reserve `from package.module import Name` for isolated names.
- Use real values. Do not emit `TODO`, `TBD`, ellipses, fake identifiers, dummy strings, pseudocode bodies, empty branches, fabricated evidence, or placeholder returns.
- Make every import, type, binding, function, workflow node, agent port, relation, output field, and branch contribute to the requested result or its trace and assurance boundary.
- Prefer small pure functions and explicit named data flow. Use one representation per concept and one responsibility per module.
- Return the useful domain result rather than an orchestration artifact with no consumer.

## Structure only as needed

For a nontrivial program with reusable abstract reasoning, prefer:

```text
feature/
├── reasoning.prism        # pure epistemic topology
├── relations.prism        # relation contracts and witness types, when substantial
├── materialization.prism  # concrete functions, skills, tools, and workflows
└── main.prism             # real inputs and application wiring
```

Keep a smaller program in fewer files when separation would create empty or single-use modules. Split files that mix abstract reasoning, operational materialization, domain relations, or application wiring; avoid files approaching 200 lines when a cohesive split is clearer.

## Wire the entry point

- Let `main` receive runtime capabilities and variable inputs explicitly.
- Import, configure, and invoke rather than duplicating declarations.
- Use `solve workflow` for an ordinary executable workflow.
- Use `solve Reasoning(arguments) using materialized_workflow(arguments)` when executing a declared reasoning plan so the runtime checks that the workflow materializes the requested reasoning and returns its result type.
- Use `execute` only when the caller needs the typed execution trace rather than just the domain result.

## Validate before delivery

Run the checks that apply to the real entry point and any changed repository behavior:

```bash
uv run prism check path/to/main.prism
uv run prism compile path/to/main.prism
uv run prism run path/to/main.prism --handler fake
uv run pytest path/to/relevant_test.py
```

Confirm that no placeholder or unused declaration remains, every effect has explicit authority, all generated or supported values cross an explicit validation or proof boundary before stronger use, and the program returns the requested domain value.
