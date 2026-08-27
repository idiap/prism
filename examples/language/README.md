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
and relation bindings. Generated values remain generated until an explicit
validator runs, and relation-specific certificates carry their ordinary typed
proof data rather than prose descriptions.

Material inference always names its rule:

```prism
packet = combine_evidence(
    context,
    value = ReviewPacket(case = case_input, analysis = analysis.value),
    transformation = "validated review",
)
return packet |~[review_policy] Acceptable(case)
```

Agents are typed callables with explicit tools, skills, and hooks:

```prism
type Inspect = String -> Result[Generated[Analysis], ModelFailure]
tool inspect_tool: Tool[Inspect] = inspect_case

agent reviewer(context: String) -> Result[Generated[Analysis], ModelFailure]
    ! {AI.Generate}:
    tools: Tools[Inspect] = [inspect_tool]
```

Strict reasoning keeps generated explanations outside the proof boundary:

```prism
suggestion = try sympy_suggest(equation_text, python_access)
term = try elaborate_proof[Target(equation)]("rfl")
proof = try kernel.check(term)
return Ok(verify(equation, proof))
```

The examples cover:

- a kernel-checked release-version proof carried across a strict `|-` relation;
- guarded argument review and normative material support;
- abstract relation judgments using `|~` and `|-` with policy-backed support and
  kernel-checked proof materializations;
- judicial evidence with deterministically constructed traceable reporting;
- an untrusted SymPy suggestion kept separate from native kernel proof checking;
- recursive ERP source review and ordinary record results;
- bounded draft/critique/revision/validation repetition;
- JSON, SQLite, and graph sources with preserved provenance;
- an AI mechanics explanation kept separate from strict verification; and
- a Mathformer materialization of `OddSumProofReasoning`, whose abstract
  topology uses `Abductive`, `Deductive`, `Refutational`, and `Evidential`
  reasoning types. The thin materialization binds those occurrences to focused
  candidate, consistency, refutation, calibration, and finalization modules.
  Its drafting component uses deterministic SymPy callables to prepare a
  scaffold, then routes the model-produced proof
  syntax through deterministic SymPy checks, elaboration against a statically
  declared proposition, and native kernel verification. Standard `Assume`,
  `Test`, and `Calibrate` relation builders retain typed epistemic contracts
  without granting proof authority.

With their typed epistemic materials and the fake model backend, examples
01–06 and 08–09 return an accepted, reproducible test result. Example 07
returns a rejected
`Supported[Administer(order)]` for the fixture's severe allergy and
pharmacist-review requirements. Example 09 proves the general identity
`Sum(2*i + 1, (i, 0, n - 1)) = n^2`. It probes dependencies, indexes the
installed SymPy API, parses and models the source, grounds concepts, builds a
deterministic scaffold, generates and executes the Python artifact, validates
the identity, searches
`0 <= n <= 100` for counterexamples, verifies the transformation trace, and
builds the final consistency report. Every adapter and request constructor is
declared outside the topology; the workflow itself shows only named nodes and
their `sequence`/`parallel` structure. The generated artifact carries proof
syntax, which is elaborated only against the independently declared native
target. The generated proof syntax crosses the strict proof boundary only after
deterministic artifact checks, target-directed elaboration, and native kernel
checking. The artifact's symbolic rendering never defines the theorem's
meaning.
