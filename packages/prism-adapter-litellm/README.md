<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# prism-adapter-litellm

Structured `AI.Generate` effect handler backed by LiteLLM.

The handler serializes the first `generate` argument as the model request,
sends the expected Prism result type as a strict JSON schema, invokes
`litellm.completion`, and converts the returned JSON object into the matching
typed Prism record. Provider errors and malformed structured output are
returned as `ModelFailure` results.
