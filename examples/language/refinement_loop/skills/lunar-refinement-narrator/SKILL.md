---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

name: lunar-refinement-narrator
description: Explain a simulator-guided lunar landing refinement using only typed mission data, feedback, and proposed controls.
metadata:
  version: "1.0.0"
---

# Lunar refinement narrator

Produce the `PlanNarrative` for the supplied `ExplainRefinement` task.

- Inspect every feedback constraint whose `satisfied` field is false.
- Ground the strategy in the supplied observed values and required conditions.
- Explain how the proposed coast, braking, descent, and terminal burns address those failures.
- Mention a fuel, velocity, clearance, or attitude trade-off when it is relevant.
- Treat the proposed burn controls as immutable. Do not invent or modify numerical controls.
- Do not claim that the proposed plan is safe, accepted, or converged before simulator validation.
- If feedback is inactive, describe the proposed controls as an initial simulation candidate.
- Return only the requested structured `PlanNarrative`, with a concise `strategy`.
