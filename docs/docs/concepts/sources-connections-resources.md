---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: sources-connections-resources
title: Sources, connections, and resources
description: Acquire typed evidence and bind external services or immutable content through logical names.
slug: /concepts/sources-connections-resources
---

Prism uses three typed values for external data and packaged content. Each one
has a distinct lifecycle and result contract.

| Value | Purpose | Typical result |
| --- | --- | --- |
| `Source[T]` | Query an external data collection. | `Evidence[T]` |
| `Connection[I]` | Invoke an external service interface. | Ordinary typed data |
| `Resource[T]` | Embed immutable content at build time. | Packaged content or evidence |

Logical names appear in Prism source. Credentials, endpoints, and local paths
remain in runtime or build configuration.

## Typed sources

`data_source` and `graph_source` bind a value type to a logical deployment
name.

```prism
policies: Source[Policy] = data_source("production-policies")
dependencies: GraphSource[Dependency] = graph_source("service-graph")
```

A query declares its expected type, recoverable source failure, effects, and
permissions.

```prism
def fetch_policy(
    source: Source[Policy],
    access: DataRead[source],
    clock: ClockRead,
) -> Result[Evidence[Policy], SourceError]
    ! {Data.Read, Clock.Read}:
    return query(source, PolicyQuery.latest(), access, clock)
```

The returned `Evidence[Policy]` records the acquisition source, query details,
time, integrity state, and adapter metadata. `map_evidence` and
`combine_evidence` preserve the upstream entries when a workflow transforms or
joins the value.

## Typed connections

A connection names an external service through a typed interface.

```prism
reports: Connection[ReportBackend] = connect("release-reports")
```

An operation supplies a logical operation name, structured request, connection,
and permission.

```prism
def execute_report(
    request: ReportRequest,
    backend: Connection[ReportBackend],
    access: ToolCall,
) -> Result[Report, ToolError] ! {Tool.Call}:
    return tool_call[Report](
        "reports.execute",
        request,
        backend,
        access,
    )
```

The runtime resolves `release-reports` and `reports.execute` to deployment
configuration. A different deployment can satisfy the same Prism types.

## Packaged resources

`embed` creates an immutable build resource.

```prism
safety_policy: Resource[Markdown] = embed("resources/safety.md")
```

The build resolves the path and packages the content. Runtime source code uses
the typed resource value. It does not reopen the authored path.

A resource can become evidence through an explicit read with file and clock
permissions.

```prism
def load_policy(
    resource: Resource[Markdown],
    access: FileRead,
    clock: ClockRead,
) -> Result[Evidence[Markdown], SourceError]
    ! {File.Read, Clock.Read}:
    return resource_evidence(resource, access, clock)
```

## Preserve the deployment boundary

Reusable Prism modules contain logical identifiers and typed contracts.
Runtime configuration contains these operational values.

- Credentials and secret material
- Service endpoints
- Database and graph locations
- Provider configuration
- Local installation paths

This separation allows the same checked module to run against several approved
deployments. [Tools and interop](./tools-interop.md) covers the call boundary.
[Provenance types](./provenance-types.md) covers the evidence record returned by
a source.
