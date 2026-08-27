---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: vscode-language-support
title: VS Code language support
description: Install the Prism syntax and language extension in VS Code.
slug: /editors/vscode-language-support
---

**Prism Language Support** owns the `.prism` language mode. It provides syntax
highlighting, diagnostics from the Prism compiler, type hovers, completion, and
definition navigation.

## Requirements

Before installing the extension, make sure these tools are available.

- A working [Prism toolchain](../installation.md).
- Node.js and npm.
- VS Code 1.89 or newer.
- The `code` command in the terminal.

If `code` is missing, open the VS Code command palette and run **Shell Command:
Install 'code' command in PATH**.

## Install the local extension

Run the installer from the Prism checkout.

```bash
cd apps/prism-vscode-syntax
./scripts/install-local.sh
```

The installer tests the extension, builds a fresh VSIX package, installs it,
and removes the temporary package.

For VS Code Insiders, select its CLI explicitly.

```bash
CODE_COMMAND=code-insiders ./scripts/install-local.sh
```

Run **Developer: Reload Window** in VS Code after installation.

:::warning Remove the legacy grammar first

If the old `prism-local.prism-syntax` extension is installed, remove it so two
extensions cannot register the `.prism` grammar together.

```bash
code --uninstall-extension prism-local.prism-syntax
```

:::

## Connect the compiler

Open **Preferences: Open User Settings (JSON)** and point the extension at the
Python interpreter created during Prism installation.

```json
{
  "prism.languageServer.pythonPath": "/path/to/prism/.venv/bin/python"
}
```

On Windows, use `C:\\path\\to\\prism\\.venv\\Scripts\\python.exe`.

The extension sends the current editor buffer to
`python -m prism.tooling.ide_server`. Unsaved changes therefore receive the
same feedback from the parser and type checker as saved files.

For each document, the language service discovers the nearest `runtime.json`
and uses its `workspace` value as the project root, or treats an enclosing
`<project>/.prism` directory as project-local source. Several Prism projects
can therefore be opened under one larger VS Code workspace. Set
`PRISM_PROJECT_ROOT` before launching VS Code only when an explicit root should
override document-based discovery.

## Verify the installation

Confirm the canonical extension identity.

```bash
code --list-extensions --show-versions
```

The output must contain `prism.prism-language-support` followed by its version.

Open the quick start's `main.prism` and check the following behavior.

1. The status bar language mode is **Prism**.
2. The source is syntax highlighted.
3. Hovering `candidate` shows its inferred type.
4. **Prism: Type Check Current Document** reports no diagnostics after the Run
   Explorer is installed.

## What the extension understands

Language support covers the complete active surface.

- Types, functions, effects, failures, and permissions.
- `reasoning`, relations, workflows, and guarded exits.
- Generated, evidence, computed, supported, validated, and proof types.
- Agents, tools, built skills, and native hooks.
- Local and imported definition navigation.

If the configured interpreter cannot import Prism, open the **Prism Language
Support** output channel to see which Python paths were probed.
