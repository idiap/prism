<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# Canonical Prism language examples

The examples in this directory define the supported executable language slice.
Larger examples split abstract topology into `reasoning.prism` and concrete
execution into `materialization.prism`. The abstract half declares exact method
and relation contracts; the materialization supplies workflows, pure
certificate builders, switches, effects, failures, and permissions.

Reasoning declarations are configured directly with complete named occurrence
and relation bindings. Fixed pure structural helpers require no abstract slot.
Generated ancestry survives deterministic transformation and validation;
relation-specific certificates carry their exact declared assurance.

Material inference always names its rule:

```prism title="Explanatory fragment"
packet = map_evidence(context, case_input, analysis, transformation = build_review_packet)
assessment = try packet |~[review_policy] Acceptable(case)
return accept_support(assessment)
```

Agents are typed callables with explicit tools, skills, and hooks:

```prism title="Explanatory fragment"
type Inspect = String -> Result[Generated[Analysis], ModelFailure]
tool inspect_tool: Tool[Inspect] = inspect_case

agent reviewer(context: String) -> Result[Generated[Analysis], ModelFailure]
    ! {AI.Generate}:
    tools: Tools[Inspect] = [inspect_tool]
```

Strict reasoning keeps generated explanations outside the proof boundary:

```prism title="Explanatory fragment"
suggestion = try sympy_suggest(equation_text, python_access)
term = try elaborate_proof[Target(equation)]("rfl")
proof = try kernel.check(term)
return Ok(verify(equation, proof))
```

## Strict release approval

`strict_inference/main.prism` returns `Ok(7)`. Its `Deductive` occurrence has
unchecked `Nat` output; the attached `ApprovesRelease` relation separately
proves `SameVersion(target, approved)` for the returned target. Changing the
materializer to return `9` fails that exact proof obligation.

The abstract plan permits `literal` and `computed` output producers. The
`release_approval` and `computed_release_approval` materializations both satisfy
it without changing the topology. An asserted replacement origin is rejected.

## Lunar refinement

`refinement_loop/main.prism` returns a computed plan validated under its
simulator model. The fake handler produces five narration proposals before the
loop accepts, within its bound of ten. Numerical controls are computed;
model-generated narration retains its ancestry through assembly and validation.
A typed policy assesses mission and feedback preservation, and only accepted
assessments become the `SupportTrajectoryHypothesis` relation's support.

Final validation rechecks the actual plan. Empty mission input or a rejecting
final validator cannot produce the accepted result. This is not a native proof
of physical landing safety. The declared capabilities remain `ModelGenerate`
and `ContextDisclose`.

## Inspect all three properties

Run either entry through `uv run prism check`, `uv run prism compile`, and
`uv run prism run ... --handler fake`. The CLI and editor share normalized
contracts and version `11` outcomes. A compact selection is:

| Occurrence/edge | Classification | Observed origin | Assurance | Contract |
| --- | --- | --- | --- | --- |
| Strict `version` | Deductive | literal or computed | unchecked | satisfied |
| `ApprovesRelease` | Relation | native proof computation | proved | satisfied |
| Refinement `candidate` | Abductive | computed plan with generated narration ancestry | validated | satisfied |
| `SupportTrajectoryHypothesis` | Relation | policy evaluation of referenced evidence | supported, accepted | satisfied |
| Refinement `safe_plan` | Deductive | retained computed plan | validated under model | satisfied |

The full trace records actual producer IDs, activity inputs, effect references,
claim and certificate hashes, and distinct loop instances. Successful execution
never substitutes for those checks. Fake generation is explicitly synthetic.
