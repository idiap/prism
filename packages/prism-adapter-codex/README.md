<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-adapter-codex

Structured `AI.Generate` effect handler backed by `codex exec`.

Each generation effect starts an isolated, ephemeral Codex session in a temporary
directory with a read-only sandbox. The handler supplies the PRISM output type via
`codex exec --output-schema`, parses the final JSON response, and converts it into
the matching typed PRISM value. It reuses the Codex CLI's saved authentication and
configured model by default.

Optional environment variables:

- `PRISM_CODEX_MODEL`: model override passed to `codex exec --model`.
- `PRISM_CODEX_PROFILE`: Codex configuration profile passed with `--profile`.
- `PRISM_CODEX_EXECUTABLE`: Codex executable path or name; defaults to `codex`.
- `PRISM_CODEX_TIMEOUT_SECONDS`: positive subprocess timeout in seconds.

Authenticate the Codex CLI before selecting this handler. Provider failures,
timeouts, and malformed structured output are returned as `ModelFailure` results.
