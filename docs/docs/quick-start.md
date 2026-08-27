---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: quick-start
title: Quick start
description: Create, check, compile, and run a small typed Prism program.
slug: /quick-start
---

This first program contains one record type, one pure function, and one entry
point. It exercises the real parser, type checker, compiler, and runtime. The
program requires neither a model nor provider credentials.

## Before you begin

Complete [installation](./installation.md) and keep the Prism checkout at
`/path/to/prism`. The commands below use its managed CLI directly.

## Create a project

Create an empty directory outside the Prism checkout.

```bash
mkdir hello-prism
cd hello-prism
```

Create `main.prism` with the following content.

```prism title="main.prism"
type ReleaseCandidate:
    tests_passed: Bool
    approved: Bool

def ready(candidate: ReleaseCandidate) -> Bool:
    return candidate.tests_passed and candidate.approved

candidate = ReleaseCandidate(tests_passed = True, approved = True)

def main() -> Bool:
    return ready(candidate)
```

The record holds the facts to evaluate. `ready` is an ordinary typed function,
and `main` returns the useful domain result.

## Check the program

Run the static checker before execution.

```bash
/path/to/prism/.venv/bin/prism check main.prism
```

A successful check reports an accepted program with no diagnostics.

## Compile it

Compile the checked source to an execution form that remains independent of the
runtime backend.

```bash
/path/to/prism/.venv/bin/prism compile main.prism
```

Compilation prints the program contract, including its result, failures, and
effects. This program returns `Bool` and has no effects.

## Run it

Use the deterministic fake handler. The program performs no external or
generative effects, so the fake handler supplies everything it needs.

```bash
/path/to/prism/.venv/bin/prism run main.prism --handler fake
```

The run is accepted and its result is `true`.

## What just happened?

The same source passed through four boundaries.

1. The parser recognized Prism declarations and expressions.
2. The type checker proved that the record, function call, and return type fit.
3. The compiler produced execution IR that remains independent of the backend.
4. The runtime evaluated `main` and returned the typed result.

An ordinary function is sufficient for this small deterministic computation.
Use a `reasoning` declaration when the epistemic topology needs reuse,
independent review, or an audit trail.

## Add editor support

Install [VS Code language support](./editors/vscode-language-support.md) for
syntax highlighting, diagnostics, hovers, completion, and navigation. Add the
[Run Explorer](./editors/vscode-run-explorer.md) when you want persisted runs,
reports, and reasoning logs inside the editor.
