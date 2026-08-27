---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: effects-failures-permissions
title: Effects, failures, and permissions
description: Declare recoverable errors, external operations, and explicit authority in Prism contracts.
slug: /concepts/effects-failures-permissions
---

Prism separates three operational concerns in every callable contract.

| Concern | Representation | Question answered |
| --- | --- | --- |
| Successful and failed results | `Result[Value, Failure]` | What can the call return? |
| External operations | `! {Effect}` | Which operations can occur? |
| Authority | Typed permission value | Which resource may the call use? |

The checker follows these contracts through every call. A handler selected at
runtime implements an effect and preserves the declared type.

## Recoverable failures

Failures are ordinary typed values. A closed sum collects the errors that a
caller may receive.

```prism
type LoadError:
    | MissingFile(path: String)
    | InvalidConfig(message: String)

def parse_config(text: String) -> Result[Config, LoadError]
```

`try` unwraps `Ok(value)`. An `Err(error)` returns from the enclosing callable
when the error fits its result type.

```prism
def load_config(
    path: Path,
    access: FileRead[path],
) -> Result[Config, LoadError] ! {File.Read}:
    text = try read_text(path, access)
    return parse_config(text)
```

Prism has no unchecked exceptions in authored source. A workflow lifts a
component error into its declared `fails` surface.

```prism
workflow load_application(
    path: Path,
    access: FileRead[path],
) -> Config
    fails LoadError
    ! {File.Read}:
    [config: load_config(path, access)]
    return config
```

## Effect rows

An effect row lists the external operations reachable through a callable.
Omitting the row declares a pure callable.

```text
File.Read        File.Write       Data.Read        Data.Write
Network.Request Process.Run       Tool.Call        MCP.Call
AI.Generate      Clock.Read       Random.Sample    Trace.Emit
Context.Disclose Python.Call
```

Effect checking is transitive. A caller must declare every effect reachable
through its calls. Replacing a file handler or model provider leaves the effect
type unchanged.

Effect families may carry a narrower type index.

```text
Data.Read[PatientRecord]
File.Read[repository.root]
```

## Permission values

A permission is an unforgeable value supplied by the runtime. The callable
passes it to the operation that needs authority.

```prism
def fetch_policy(
    source: Source[Policy],
    access: DataRead[source],
    clock: ClockRead,
) -> Result[Evidence[Policy], SourceError]
    ! {Data.Read, Clock.Read}:
    return query(source, PolicyQuery.latest(), access, clock)
```

The type `DataRead[source]` ties authority to one logical source. A broad
ambient credential cannot appear in the function body.

Common permissions include `ModelGenerate`, `ToolCall`, `PythonCall`,
`ClockRead`, and resource indexed forms such as `FileRead[path]`.

## Runtime authority flow

```text
runtime configuration
    -> typed permission value
    -> checked callable parameter
    -> effect request
    -> matching effect handler
```

The compiler records the complete failure and effect surface. The runtime
checks that a matching handler and required permission are present before the
operation proceeds.

## Policy rejection and execution failure

A material policy can reject support while its evaluator completes normally.
The result remains a `Supported[P]` value with rejected status. An operational
failure in the evaluator appears as `Err(error)`.

This distinction gives a caller two separate outcomes.

| Outcome | Representation |
| --- | --- |
| The policy reached a negative decision | Rejected `Supported[P]` |
| The policy could not complete | `Err(Failure)` |

[Assurance and inference](./assurance-types.md) describes the status carried by
material support. [Execution and tracing](./execution-tracing.md) describes
handler selection and persisted effect records.
