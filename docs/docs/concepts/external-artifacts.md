---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: external-artifacts
title: External artifacts
description: Build or convert external agent assets into checked, standalone Prism modules.
slug: /concepts/external-artifacts
---

Prism treats agent ecosystem files as conversion input. A build or conversion
produces typed Prism modules that carry explicit contracts, effects,
permissions, resources, and preservation records.

```text
external agent assets
    -> validation and semantic conversion
    -> checked Prism source and packaged resources
    -> independent Prism execution
```

The resulting package runs without loading the original configuration tree.
An external service can remain an operational dependency through a typed
connection.

## Build one typed artifact

Open Agent Skills and native hook configurations have focused build commands.

```bash
uv run prism build skill skills/change-review \
  --contract review.contracts.ReviewTask \
  --out review/generated/change_review_skill

uv run prism build hooks codex hooks/codex.json \
  --out review/generated/codex_hooks
```

The generated modules export `Skill[ReviewTask]` and `Hooks[Codex]` values.
The build validates the source asset, embeds supported resources, checks the
generated Prism source, and writes a standalone module.

[Skills](./skills.md) and [hooks](./hooks.md) describe their source formats and
typed agent bindings.

## Convert a project

`to-prism` converts reviewed Codex, Claude, OpenCode, and Open Agent Skill
projects into canonical Prism projects. Conversion follows explicit stages.

```bash
to-prism inspect --source external-project --output conversion
to-prism model --source external-project --output conversion
to-prism baseline --source external-project --output conversion
to-prism generate \
  --source external-project \
  --output conversion \
  --plan approved-plan.json \
  --handler fake
to-prism verify \
  --source external-project \
  --output conversion \
  --portable
```

Review occurs before generation. The approved plan records how each source
asset maps to a Prism declaration or packaged value.

## Preserve semantics explicitly

Every source element receives one preservation status.

| Status | Meaning |
| --- | --- |
| Converted | Native Prism declarations preserve the behavior. |
| Embedded | Immutable source content becomes a packaged resource. |
| Packaged | Executable content remains behind a typed packaged boundary. |
| Approximated | Prism represents a reviewed subset of the behavior. |
| Unsupported | The conversion records explicit debt and blocks silent loss. |

Conversion reports any lost or approximated type, proof obligation,
provenance guarantee, effect, reasoning edge, permission, or lifecycle event.

## Keep generated projects independent

A portable project contains its Prism source, dependency lock, required
artifacts, and launchers. The original agent directory and Prism source
checkout are unnecessary at runtime.

Runtime configuration still owns credentials, endpoints, provider identities,
and service processes. Typed connections and permissions expose those approved
dependencies to the generated Prism program.

## Treat external proof and model output as untrusted data

Converted scripts, model calls, Python adapters, and external provers return
ordinary or generated values. They cannot introduce protected assurance types.
Proof syntax must pass through target directed elaboration and kernel checking
before it becomes `Proof[P]`.

[Tools and interop](./tools-interop.md) describes these call boundaries.
[Assurance and inference](./assurance-types.md) describes the native assurance
transitions.
