---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: overview
title: Language concepts
description: Follow typed domain values through reasoning, execution, and trace inspection.
slug: /concepts
---

Prism programs connect four layers. Each layer has a distinct contract and a
clear owner.

```text
typed domain values
    -> epistemic reasoning and assurance
    -> executable workflows and materialization
    -> explicit capabilities and external operations
    -> typed result and execution trace
```

## Language foundation

[Language foundations](./language-foundations.md) introduces modules,
immutable values, records, closed sums, refinements, and pure functions.
[Effects, failures, and permissions](./effects-failures-permissions.md) explains
the contract for recoverable errors, external operations, and authority.

These rules apply to every function, workflow, agent, and application entry.

## Epistemic reasoning

[Reasoning types](./reasoning-types.md) describes the epistemic operation at
each reasoning occurrence. [Relations and materialization](./relations-materialization.md)
connects the abstract topology to executable callables and typed relation
certificates.

[Provenance types](./provenance-types.md) record how a value was produced.
[Assurance and inference](./assurance-types.md) records why a value or
proposition may be accepted. Strategy, provenance, and assurance remain
independent.

## Execution

[Workflows](./workflows.md) defines typed sequencing, parallel work, routing,
and bounded repetition. [Execution and tracing](./execution-tracing.md) covers
workflow construction, `solve`, `execute`, effect handlers, persisted runs,
and the trusted kernel boundary.

## Capabilities and integration

[Agents](./agents.md) receive typed tools, skills, and hooks. [Tools and
interop](./tools-interop.md) distinguishes agent tools, provider calls, Python
effects, model generation, and MCP effects.

[Sources, connections, and resources](./sources-connections-resources.md)
explains typed data acquisition and deployment bindings. [External
artifacts](./external-artifacts.md) covers the conversion of skills, hooks, and
provider assets into checked Prism modules.

## Choose the smallest callable

| Need | Prism declaration |
| --- | --- |
| Deterministic transformation | `def` |
| Executable topology | `workflow` |
| Reusable epistemic topology | `reasoning` |
| Model generation with typed capabilities | `agent` |

A pure function is sufficient when the program only transforms typed values.
A workflow makes execution order, failures, and effects visible. A reasoning
declaration adds reusable epistemic intent and requires materialization before
execution.
