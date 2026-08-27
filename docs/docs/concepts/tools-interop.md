---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: tools-interop
title: Tools and interop
description: Distinguish agent tools, provider operations, Python adapters, model generation, and MCP effects.
slug: /concepts/tools-interop
---

Prism exposes external work through typed call boundaries. The boundary chosen
for a call determines its effects, permissions, provenance, and runtime
handler.

## Choose the call boundary

| Boundary | Use |
| --- | --- |
| `tool name: Tool[Contract] = callable` | Give a Prism function or deterministic workflow to an agent. |
| `generate[Output](request, model, access)` | Ask a model for a typed generated value. |
| `tool_call[Output](operation, request, connection, access)` | Invoke a provider operation through a typed connection. |
| `python_call[Output](operation, request, access)` | Invoke an installed Python implementation. |
| `MCP.Call` | Declare an MCP effect handled by an injected runtime adapter. |

These boundaries expose different authority. Agent tool wrapping keeps the
callable contract. Provider and Python calls return ordinary typed data.

## Give a callable to an agent

A tool preserves the parameters, result, failures, permissions, and effects of
the callable it wraps.

```prism
type Normalize = ReviewTask -> PreparedTask

def normalize(task: ReviewTask) -> PreparedTask:
    return PreparedTask(text = task.text)

tool normalize_tool: Tool[Normalize] = normalize
```

The agent receives the tool through a typed `Tools[Normalize]` binding. Tool
availability grants access to that exact contract for the agent invocation.

## Generate a typed value

Model generation requires a model value and `ModelGenerate` permission.

```prism
def assess(
    request: AssessmentRequest,
    model: Model,
    access: ModelGenerate,
) -> Result[Generated[Assessment], ModelFailure] ! {AI.Generate}:
    return generate[Assessment](request, model, access)
```

The result remains `Generated[Assessment]`. Deterministic validation, material
support, or kernel proof must introduce any stronger assurance.

## Call a provider operation

`tool_call` uses a logical operation and typed connection.

```prism
def search_documents(
    request: SearchRequest,
    backend: Connection[SearchApi],
    access: ToolCall,
) -> Result[SearchResults, ToolError] ! {Tool.Call}:
    return tool_call[SearchResults](
        "documents.search",
        request,
        backend,
        access,
    )
```

The connection selects an approved deployment. The operation string remains a
stable logical identifier.

## Call installed Python

`python_call` connects Prism to an existing Python package through one typed
request and result.

```prism
type ScoreRequest:
    order_id: String

type Score:
    value: Int

def score_order(
    request: ScoreRequest,
    access: PythonCall,
) -> Result[Score, PythonError] ! {Python.Call}:
    return python_call[Score]("orders.score", request, access)
```

The Python package registers the logical operation at deployment time.

```toml
[project.entry-points."prism.python_effects"]
"orders.score" = "order_package.effects:score_order"
```

Prism source contains the logical operation. The Python module path belongs to
the installed package.

## Keep assurance inside Prism

`tool_call` and `python_call` cannot return protected provenance or assurance
types. Their output type cannot contain `Generated`, `Evidence`, `Computed`,
`Supported`, `Validated`, `CoreTerm`, `Proof`, or `Verified`.

External output enters Prism as ordinary data. Native Prism operations then
record provenance, validate a value, apply a material policy, elaborate proof
syntax, or ask the kernel to check a term.

## MCP effects

`MCP.Call` is a standard effect family. A runtime adapter receives its logical
operation, typed arguments, result schema, and permissions. MCP server
configuration stays outside reusable Prism source.

Conversion from an external MCP configuration must preserve tool schemas,
effects, permissions, and unsupported behavior explicitly. [External
artifacts](./external-artifacts.md) covers that conversion contract.
