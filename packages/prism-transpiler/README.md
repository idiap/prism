<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-transpiler

Build Open Agent Skills and native Codex or Claude hook configurations into
checked, standalone typed Prism modules.

The package exposes `build_skill_module` and `build_hooks_module`. Unsupported
or untyped content is a build error; generated modules do not depend on the
source artifact tree at runtime.

The CLI exposes these as `prism build skill` and `prism build hooks`.
