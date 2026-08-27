<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# PRISM VS Code Extension

The PRISM Solver Workbench turns `.prism` files into an interactive proof and workflow surface inside VS Code. It gives you run history and report views backed by the local Python PRISM IDE service.

Syntax highlighting, type hovers, diagnostics, and definition navigation are owned by the companion [`prism-language-support`](../prism-vscode-syntax/) extension. The workbench declares it as an extension dependency so VS Code uses one grammar and one set of language providers when both surfaces are installed.

Use this extension when you want to read or develop `.prism` programs with live feedback instead of switching between the editor and CLI after every edit.

## First Run

Run these commands from the repository root before opening the extension development host:

```bash
uv sync --all-packages
uv run prism --help
uv run prism check catalog/proofs/foundations/01a_simple_syllogism.prism
```

Expected cue: the final command prints a checked-program summary. The extension uses the same backend-neutral parser and checker as the CLI.

Then build the TypeScript extension:

```bash
cd apps/prism-vscode-extension
npm install
npm run build
```

Open the repository root in VS Code and start the launch profile `Run PRISM Solver Workbench Extension`. The profile loads both the workbench and language-support development extensions. In the Extension Development Host, open [catalog/proofs/foundations/01a_simple_syllogism.prism](../../catalog/proofs/foundations/01a_simple_syllogism.prism). The PRISM activity bar and syntax highlighting should appear.

## What To Try First

| Task | File | Command Or Action | Expected Cue |
| --- | --- | --- | --- |
| See the smallest proof surface | [01a_simple_syllogism.prism](../../catalog/proofs/foundations/01a_simple_syllogism.prism) | Open the file, then run `PRISM: Open Solver Workbench`. | The Run Explorer and report show the checked execution details. |
| Check reference navigation | [01c_formal_handoff_lean.prism](../../catalog/proofs/formal-reasoning/01c_formal_handoff_lean.prism) | Put the cursor on a local file reference and run `PRISM: Open Reference Under Cursor`. | VS Code opens the referenced proof artifact or source file. |
| Inspect workflow-backed reasoning | [02e_scenario10mod_diagrammatic_workflow.prism](../../catalog/proofs/scenario10mod/02e_scenario10mod_diagrammatic_workflow.prism) | Run `PRISM: Open Solver Workbench`, then `PRISM: Build Dynamic Plan`. | The Infoview shows plan suggestions grounded in the active `.prism` buffer. |

## Mental Model

A `.prism` file is the source of truth. The extension sends the unsaved editor text to `python -m prism.tooling.ide_server`, so the workbench reflects your current buffer rather than only the file on disk.

The Run Explorer is the compact execution-state view. It is useful for selecting persisted runs and inspecting their results.

The report is the explanation and action surface. It shows references, derivation steps, execution output, and parse diagnostics.

The Reference Explorer shows the symbols and references the session can see. The Argument Structure view is better for following derived steps, tactic steps, result logs, and output files as a navigable tree.

Document links and `PRISM: Open Reference Under Cursor` are navigation aids. They do not execute workflows; they help you jump from declarations such as `workflow`, `kb`, `source`, or file paths to the underlying catalog and proof artifacts.

## Command Groups

| Group | Commands | Use When |
| --- | --- | --- |
| Open and refresh | `PRISM: Open Run Explorer`, `PRISM: Type Check Current Document`, `PRISM: Open Report Panel` | You want the UI to reflect the active `.prism` buffer. |
| Navigate | `PRISM: Open Active PRISM Source`, `PRISM: Open Reference Under Cursor`, `PRISM: Focus Argument Structure` | You are reading a proof or workflow and need to move between declarations and supporting files. |
| Suggest and insert | `PRISM: Suggest Tactics`, `PRISM: Build Dynamic Plan`, `PRISM: Insert Sledge Step`, `PRISM: Insert Best Skill Step`, `PRISM: Insert Best Plan` | You want the local planner to propose or insert the next proof step. |
| Execute | `PRISM: Run Current Document with Model…`, `PRISM: Resume Last Run` | You want to run the active document through LiteLLM with a configured model. |
| Diagnose | `PRISM: Show Debug Log` | The Python session, parsing, navigation, or execution path is not behaving as expected. |

## Settings

| Setting | Default | Meaning |
| --- | --- | --- |
| `prismSolver.pythonPath` | `python`, or `.venv` auto-detected when present | Python executable used to launch `prism.tooling.ide_server`. Set this when VS Code cannot find the repo virtual environment. |
| `prismSolver.execution.models` | `[]` | LiteLLM model identifiers offered by `PRISM: Run Current Document with Model…` (e.g. `anthropic/claude-opus-4-8`). At least one model is required to run a document; runs always go through LiteLLM. |
| `prismSolver.logging.level` | `info` | Diagnostic log verbosity. Use `debug` or `trace` when reproducing a bug. |
| `prismSolver.logging.includePayloads` | `false` | Includes richer refs, paths, and request payloads in the diagnostic log. |
| `prismSolver.logging.revealOnError` | `true` | Opens the debug channel automatically when an extension error is recorded. |

## Troubleshooting

If the workbench opens but stays empty, run `PRISM: Refresh Solver Workbench` with a `.prism` file active.

If the Python session fails to start, run this from the repository root:

```bash
uv run python -c "import prism.tooling.ide_server"
```

If that command works but VS Code still fails, set `prismSolver.pythonPath` to the repository virtualenv Python, for example `.venv/bin/python` on macOS/Linux or `.venv\\Scripts\\python.exe` on Windows.

If `PRISM: Run Current Document with Model…` does not offer any model to pick, add LiteLLM model identifiers to `prismSolver.execution.models`. Runs always go through LiteLLM, so a configured model (and the matching provider credentials) is required.

If navigation does not open a file, check that the referenced path is relative to the repository root or to the current `.prism` file's supported catalog context. Open `PRISM: Show Debug Log` for the resolved path and session diagnostics.

## Architecture For Contributors

| Surface | Location | Responsibility |
| --- | --- | --- |
| Extension host | [src/host](src/host) | Commands, run/report views, logging, and session lifecycle. |
| Infoview protocol | [src/infoview-api](src/infoview-api) | Typed messages exchanged between the workbench and the Python IDE service. |
| Python IDE server | [../../packages/prism-lsp/src/prism/tooling/ide_server/__init__.py](../../packages/prism-lsp/src/prism/tooling/ide_server/__init__.py) | Stdio RPC entrypoint launched by the extension. |
| Python language service | [../../packages/prism-lsp/src/prism/tooling/lsp/service.py](../../packages/prism-lsp/src/prism/tooling/lsp/service.py) | Provider-free parsing, checking, symbols, and diagnostics. |
| Optional workbench | [../../packages/prism-lsp/src/prism/tooling/workbench/service.py](../../packages/prism-lsp/src/prism/tooling/workbench/service.py) | Execution and run persistence when runtime packages are installed. |
| Language support | [`../prism-vscode-syntax`](../prism-vscode-syntax/) | Canonical `.prism` grammar, editor configuration, type hovers, diagnostics, and definition navigation. |

Run the extension build after editing TypeScript:

```bash
cd apps/prism-vscode-extension
npm run build
```

For repository-level testing, use the focused IDE and extension-related tests before packaging broader changes:

```bash
uv run pytest -q tests/test_cli_ide_interface.py tests/test_document_layout_prism_parser.py tests/test_document_layout_prism_service.py
```
