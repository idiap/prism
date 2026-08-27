---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: vscode-run-explorer
title: VS Code Run Explorer
description: Install the Prism Run Explorer and inspect a reasoning log.
slug: /editors/vscode-run-explorer
---

**Prism Run Explorer** adds a Prism activity bar view for type checking,
executing the active document, selecting persisted runs, and reading reports.
It complements the separate Language Support extension.

## Install the extension

Install [Prism Language Support](./vscode-language-support.md) first. Then run
these commands from the Prism checkout.

```bash
cd apps/prism-vscode-extension
npm ci
npm run build
npx --yes @vscode/vsce package \
  --allow-missing-repository \
  --no-rewrite-relative-links \
  --out /tmp/prism-solver-workbench.vsix
code --install-extension /tmp/prism-solver-workbench.vsix --force
```

Run **Developer: Reload Window** in VS Code.

## Configure the Python service

Set the workbench to the same managed interpreter as Language Support.

```json
{
  "prism.languageServer.pythonPath": "/path/to/prism/.venv/bin/python",
  "prismSolver.pythonPath": "/path/to/prism/.venv/bin/python"
}
```

On Windows, use the checkout's `.venv\\Scripts\\python.exe`.

Verify both extension identities.

```bash
code --list-extensions --show-versions
```

The output must include both identifiers.

```text
prism.prism-language-support
prism.prism-solver-workbench
```

Open a `.prism` file. The Prism icon should appear in the activity bar with two
views named **Run Explorer** and **Report**.

## Run a document

The editor run command currently uses LiteLLM. Configure at least one model
identifier in its settings.

```json
{
  "prismSolver.execution.models": [
    "anthropic/claude-opus-4-8"
  ]
}
```

Use a LiteLLM model identifier available in your environment. Provider
credentials must be visible to the VS Code process when a program uses
`AI.Generate`. The command asks for a configured model identifier for every
run. A pure deterministic program completes without contacting the provider.

With a `.prism` file active, run **Prism: Run Current Document**. Completed runs
are stored under `.prism/runs` in the opened workspace. Selecting a previous run
updates both the explorer and its report.

## Reasoning Log

The **Reasoning Log** appears in the Report view for a run that executed a
materialized `reasoning` declaration. The Report builds the log from the typed
execution trace. Hidden chain-of-thought text never enters the log.

Each row represents a reasoning occurrence and shows the following fields.

- Its stable occurrence name.
- Its order in the executed topology.
- Its declared output type.
- Its status.
- The result recorded for that step.

The underlying trace also records the abstract reasoning type, concrete
implementation, reasoning declaration, effects, failure type, and logical input
type. Expand the full `trace` field in Run Explorer when you need those details.

Follow these steps to produce a useful log.

1. Open a checked entry point that calls
   `solve ReleaseReadiness(candidate) using flow` or another concrete reasoning
   invocation.
2. Run **Prism: Run Current Document** and select the model entry.
3. Open the Prism activity bar, then expand **Report**.
4. Expand a step under **Reasoning Log** to inspect its result.

The report only shows this section when the runtime trace contains materialized
reasoning occurrences. The quick start uses an ordinary function. Its report
contains a result without a Reasoning Log section.

## Run history and diagnostics

The Run Explorer also exposes the final result, complete trace, diagnostics,
effect records, metadata, and program hash. Use the run selector to compare
persisted executions of the same file, or delete a run from its context menu.

For extension problems, run **Prism: Show Debug Log**. Set
`prismSolver.logging.level` to `debug` or `trace` only while reproducing an
issue. Payload logging remains off by default.
