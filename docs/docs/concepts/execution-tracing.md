---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: execution-tracing
title: Execution and tracing
description: Construct workflows, solve reasoning, inspect typed traces, and verify persisted effects.
slug: /concepts/execution-tracing
---

Calling a workflow declaration constructs a typed `Workflow` value. `solve`
and `execute` run that value through the Prism runtime.

## Construct a workflow

```prism
flow: Workflow[Message, Never] = publishing("ready")
```

Construction evaluates the workflow arguments and records the output, failure,
and effect contract. The workflow nodes run when the application resolves the
value.

## Choose solve or execute

| Expression | Result |
| --- | --- |
| `solve workflow` | The successful domain value or `Result[Value, Failure]` |
| `solve Reasoning(input) using workflow` | The same result after checking the materialization identity |
| `execute workflow` | `Execution[Value, Failure]` with a result and typed trace |
| `execute Reasoning(input) using workflow` | The execution value after the materialization check |

An infallible workflow resolves directly to its successful value.

```prism
def main() -> Message:
    return solve publishing("ready")
```

A fallible workflow resolves to `Result`.

```prism
def main() -> Result[Report, ReportError]:
    return solve build_report(request)
```

Reasoning resolution checks that the workflow materializes the instantiated
reasoning declaration and returns its required type.

```prism
def main() -> Status:
    flow = configured_review(source)
    return solve Review(source) using flow
```

## Read the trace

An execution trace records the typed path to the result. Events can include
these values.

- Reasoning invocation and occurrence identity
- Abstract reasoning type and concrete materializer
- Relation declaration and certificate
- Function, workflow, and agent calls
- Effect request, handler, permission, and failure
- Evidence source and transformation
- Material policy decision
- Proof elaboration and kernel decision

Provenance and assurance occupy separate trace fields. Trace collection leaves
both types unchanged.

The [Reasoning Log](../editors/vscode-run-explorer.md#reasoning-log) presents
the occurrence sequence in VS Code. The full run record retains additional
effect and certificate data.

## Runtime handlers

The compiled program is independent of a provider. A handler implements one or
more declared effects.

| Handler | Typical use |
| --- | --- |
| Fake | Deterministic structural tests |
| LiteLLM | Model generation through a configured provider |
| Codex | Isolated generation through the Codex CLI |
| Python | Installed logical operations backed by Python callables |
| Composite | Routing several effect families in one run |

Handler selection cannot add an effect or permission to the compiled program.
The runtime rejects an operation when no handler accepts its effect request.

## Persist a run

`--output` writes the typed result, trace, checked module, and effect records.
Replay artifacts use content addressed storage next to the result file.

```bash
uv run prism run main.prism --handler fake --output result.json
```

Offline verification checks the stored module, records, and artifact hashes.

```bash
uv run prism verify-run result.json --mode offline
```

Live verification executes supported effects again and compares the new
records with the stored run.

```bash
uv run prism verify-run result.json --mode live
```

## Trust boundaries

| Component | Responsibility |
| --- | --- |
| Parser | Recognize Prism source. |
| Type checker | Check types, failures, effects, permissions, and callable compatibility. |
| Compiler | Produce a typed execution representation. |
| Runtime | Schedule workflows, enforce capabilities, call handlers, and record traces. |
| Effect handler | Execute an authorized external operation. |
| Kernel | Decide whether an elaborated proof term establishes its proposition. |

Generation handlers and external provers may propose values or proof syntax.
Only the kernel introduces `Proof[P]`.
