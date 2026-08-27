<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# Prism language support

VS Code language support for the normative Prism surface described in the
repository's `SYNTAX.md`.

## Features

- TextMate highlighting for imports, immutable bindings, records, algebraic
  data types, refinements, functions, effects, assurance types, material and
  strict inference, callable agents, typed tools, built skills, native hooks,
  reasoning, workflows,
  proof tactics, literals, strings, and comments.
- Python-compatible token scopes for declarations, function and type names,
  control flow, Boolean literals, and word operators such as `not`.
- Compiler-backed semantic tokens for canonical syntax nodes, including
  reasoning/relation declarations, topology relations, and guarded exits.
- Comment toggling, bracket matching, automatic closing pairs, significant-
  indentation folding, and block indentation after `:`.
- **Go to Definition** and Command/Ctrl-click navigation resolved by the
  canonical Prism frontend, including imports, relations, reasoning switches,
  declarations, generic type-parameter binders, parameters, fields, and
  compiler intrinsics.
- Compiler-backed type hovers for every checked expression and binding,
  including inferred bindings, aliases, agent calls, generic substitutions,
  literals, calls, operators, and imported symbols.
- Type-directed completion for guarded reasoning dispositions such as
  `status.`, including variant selectors declared by the occurrence's output
  type.
- Compiler diagnostics, including unknown fields, invalid calls, effect errors,
  unresolved type references, invalid reasoning selectors, and type mismatches,
  without duplicating the Prism type system in JavaScript.

Definition navigation is produced from the canonical AST and module loader,
so new declaration and topology forms do not require a second Prism parser in
the extension. Compiler-provided builtins link to their implementation source.

The extension launches `python -m prism.tooling.ide_server` and sends the
current unsaved document text for parsing and checking. It probes an explicitly
configured interpreter first. Otherwise it tries the workspace `.venv` only
when that environment can import the Prism IDE server, then falls back to
`python`. Set `prism.languageServer.pythonPath` to the Prism toolchain
interpreter when editing Prism files from a separate project environment.

If no candidate can import the IDE server, the extension shows an actionable
warning and records the failed interpreter probes in the **PRISM Language
Support** output channel instead of silently disabling hovers and diagnostics.

Definition navigation follows the workspace module layout used by Prism: `module.name`
resolves to `module/name.prism` or `module/name/__init__.prism`, under the
workspace root, its `src` directory, or its `.prism` directory.

Use **Developer: Inspect Editor Tokens and Scopes** to inspect TextMate scopes
under the active color theme.

## Install the local build

Build and install the current source with:

```sh
./scripts/install-local.sh
```

The script runs the tests, packages a fresh temporary VSIX, installs it over
the current version, and removes the temporary package. Run **Developer: Reload
Window** afterward. Set `CODE_COMMAND=code-insiders` to install into VS Code
Insiders instead.

Install `prism-language-support-0.7.5.vsix` from **Extensions: Install from
VSIX...**, then run **Developer: Reload Window**. This build uses the canonical
`prism.prism-language-support` extension identity, so it upgrades the existing
language extension instead of registering a second, competing `prism` grammar.

If `prism-local.prism-syntax` was installed from the earlier `0.4.0` package,
uninstall it first. The older `0.1.0` and `0.2.0` VSIX files are grammar-only
builds and do not contain definition navigation, compiler hovers, or diagnostics.

## Development

Run the grammar and navigation coverage tests with:

```sh
npm test
```
