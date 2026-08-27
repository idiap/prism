---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: prism-python-adapter
description: Create, update, or review typed PRISM-to-Python effect adapters using `Python.Call`, `python_call[...]`, `PythonEffectHandler`, and `prism.python_effects` package entry points. Use for Python-backed PRISM operations; do not use for pure PRISM functions or unrelated Python code.
---

# PRISM Python Adapter

Expose a Python implementation through a typed PRISM effect boundary while keeping deployment bindings and Python module paths out of authored PRISM source.

## Inspect the supported boundary

Read sections 5 and 8.3 of `notes/SYNTAX.md`, `packages/prism-adapter-python/README.md`, `packages/prism-adapter-python/src/prism/adapters/python/__init__.py`, and `tests/test_python_effects.py`.

## Define the PRISM interface

Use nominal request and response types. Give the wrapper an explicit `PythonCall` permission, `Python.Call` effect, and typed `PythonError` failure:

```prism
def calculate_score(
    request: ScoreRequest,
    access: PythonCall,
) -> Result[Score, PythonError] ! {Python.Call}:
    return python_call[Score]("scores.calculate", request, access)
```

- Use a stable logical operation name such as `scores.calculate`; do not put a Python module path in PRISM source.
- Pass variable inputs in the typed request and authority through `PythonCall`. Do not read ambient configuration from the PRISM program.
- Let `python_call[Output]` return `Result[Output, PythonError]`; propagate or handle that failure explicitly.
- Return only ordinary typed data. `python_call` cannot introduce protected provenance or assurance types: `Generated`, `Evidence`, `Computed`, `Supported`, `Validated`, `Proof`, or `Verified`. Apply their native typed introduction or checking operations in PRISM after the Python call.

## Implement the Python effect

- Implement a callable with signature `EffectRequest -> EffectResult`.
- Read arguments from `request.arguments` and preserve the declared PRISM shape. Use core runtime values such as `RecordValue`, `Ok`, and `Err` where the result type requires them.
- Set `EffectResult.result_type` to `request.result_type`.
- Return `Ok(value)` for success or a typed `Err(message)` for recoverable failure. The adapter converts an uncaught Python exception to `Err("ExceptionType: message")`, but handle expected domain failures deliberately when they need richer diagnostics or provenance.
- Record truthful provenance and executor metadata. Include replay artifacts only when they are real, bounded, and useful for audit or replay.
- Keep credentials, endpoints, deployment paths, and other environment-dependent values in runtime configuration rather than reusable source.

## Register deployment bindings

Register each logical operation in the implementation package:

```toml
[project.entry-points."prism.python_effects"]
"scores.calculate" = "score_package.effects:calculate_score"
```

The entry-point value is the deployment-time Python `module:function` binding. Logical names must be unique across installed packages; duplicate names with different implementations are rejected. For isolated tests, pass an explicit `{operation: "module:function"}` mapping to `PythonEffectHandler` instead of installing a package.

## Keep assurance in PRISM

Treat Python output as ordinary untrusted data. Perform deterministic parsing, validation, evidence construction, elaboration, counterexample search, or kernel checking in explicit downstream PRISM steps. A Python implementation must not fabricate `Generated`, `Evidence`, `Computed`, `Supported`, `Validated`, `Proof`, or `Verified` values.

## Verify both sides

Add or update focused tests covering successful dispatch, response shape, typed failure, required permission, and protected-type rejection when relevant. Run:

```bash
uv run prism check path/to/program.prism
uv run prism compile path/to/program.prism
uv run prism run path/to/program.prism
uv run pytest path/to/python_adapter_test.py
```

Confirm that the PRISM operation name matches its registered entry point, the wrapper declares `PythonCall` and `Python.Call`, the Python callable returns `EffectResult` with the declared type, and no module path or assurance claim crosses the effect boundary.
