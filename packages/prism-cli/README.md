<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-cli

Command-line frontend for parsing, checking, compiling, running, and verifying
Prism programs, plus ahead-of-time builds of Open Agent Skills and native
Codex or Claude hooks through the separate `prism-transpiler` package. Material
generation can use deterministic fake results, LiteLLM, or the authenticated
Codex CLI through `prism run PROGRAM --handler codex`.
