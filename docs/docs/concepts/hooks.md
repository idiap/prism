---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: hooks
title: Hooks
description: Build native Codex and Claude hook configurations into provider typed Prism artifacts.
slug: /concepts/hooks
---

A hook artifact carries a validated native lifecycle configuration into an
agent call. Its type records the target provider as `Hooks[Codex]` or
`Hooks[Claude]`. Provider identity remains visible during checking, compilation,
and execution.

## Prepare a native configuration

The builder accepts JSON, TOML, or YAML. A source file or directory must
contain exactly one configuration with a nonempty `hooks` mapping.

The following Codex configuration checks shell tool use with a command hook.

```json title="hooks/codex.json"
{
  "description": "Apply the repository review policy",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "review-policy"
          }
        ]
      }
    ]
  }
}
```

The configuration keeps the provider's native event, matcher, and handler
shape. Codex artifacts accept command handlers. Claude artifacts can represent
command, HTTP, MCP tool, prompt, and agent handlers where the selected event
allows them.

## Build the typed module

Select the provider explicitly.

```bash
/path/to/prism/.venv/bin/prism build hooks codex hooks/codex.json \
  --out review/generated/codex_hooks
```

The command validates event names, matcher placement, handler kinds, required
fields, and field types. It then checks and writes a standalone Prism module.
The Codex command exports the following value.

```text
codex_hooks: Hooks[Codex]
```

Use `claude` as the provider argument to produce `claude_hooks` with type
`Hooks[Claude]`.

The build reads configuration data and emits a typed artifact. Hook commands
remain dormant during this process.

## Attach hooks to an agent

Import the generated value and declare it as a persistent capability.

```prism
from review.generated.codex_hooks import codex_hooks

agent reviewer(
    task: ReviewTask,
) -> Result[Generated[Review], ModelFailure]
    ! {AI.Generate, Context.Disclose}:
    hooks: Hooks[Codex] = codex_hooks
```

The provider parameter prevents a Claude artifact from filling a
`Hooks[Codex]` binding. This catches a provider mismatch during `prism check`.

A caller can add another hook artifact for one invocation.

```prism
result = reviewer(
    task,
    hooks = strict_codex_hooks,
)
```

The runtime keeps the persistent and invocation artifacts, records their
provider identities in the agent trace event, and forwards their native
configurations to the active generation handler.

## Activation boundary

The generation handler controls native activation. Prism forwards the native
configuration as part of the agent request. Activation occurs when the
selected handler interprets that configuration.

This boundary keeps provider lifecycle behavior visible in Prism source while
credentials and provider process state remain runtime configuration.

## Resolve build failures

Use the build command as the compatibility check for a native configuration.
Common failures include an unknown event, a matcher on an event that rejects
matchers, an unsupported handler kind, a missing command or URL, and a field
with the wrong type.

```bash
/path/to/prism/.venv/bin/prism build hooks codex hooks/codex.json \
  --out review/generated/codex_hooks
/path/to/prism/.venv/bin/prism check main.prism
```

Continue with [agents](./agents.md) for capability composition and
[skills](./skills.md) for typed instruction bundles. [External
artifacts](./external-artifacts.md) explains standalone builds and project
conversion.
