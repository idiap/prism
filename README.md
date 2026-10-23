<!--
SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>

SPDX-License-Identifier: MIT
-->

# Prism

**Prism is a typed programming language that makes reasoning, capabilities,
and assurance boundaries explicit in systems built with generative AI.**

[Installation](docs/docs/installation.md) ·
[Quick Start](docs/docs/quick-start.md) ·
[Documentation](docs/docs/concepts/language-concepts.md)

Generative AI makes a single agent easy to prototype. As that agent grows into
a system of skills, tools, workflows, models, and other agents, control quickly
disappears. Logic migrates into prompts and configuration. Agents gain access
to capabilities that source code does not make visible. Generated outputs flow
between components without explicit provenance or validation.

Prism makes those systems understandable and governable.

- **Reason at a high level of abstraction.** Describe epistemic intent and
  reasoning topology before selecting the agents, skills, models, and workflows
  that materialize them.
- **Separate reasoning from implementation.** Declare the reasoning strategy
  and data flow independently from the agents, models, policies, and functions
  that execute it.
- **Keep complex systems interpretable.** Inspect explicit dependencies,
  capabilities, failures, provenance, and assurance boundaries from source code
  through the execution trace.

## Describe the reasoning

A `reasoning.prism` file captures what must be reasoned about before the program
selects an agent, model, or runtime. The complete example lives in
[`examples/language/release_review`](examples/language/release_review).

```prism title="reasoning.prism" source="examples/language/release_review/reasoning.prism"
from prism.reasoning.methods.deductive import DeductionInput, Deductive
from prism.reasoning.methods.evidential import Evidential, EvidentialInput

type Change:
    summary: String
    diff: String

type ReleasePolicy:
    maximum_risk: Int

type Review:
    summary: String
    risk: Int
    tests_passed: Bool

type Decision:
    approved: Bool
    rationale: String

type DecisionInput:
    review: Generated[Review]
    policy: ReleasePolicy

type ReviewTask = EvidentialInput[Change, ReleasePolicy]

reasoning AssessRelease(task: ReviewTask) -> Decision:
    sequence:
        [review: Evidential[
            Generated[Review],
            Change,
            ReleasePolicy,
        ](task)]
        [decision: Deductive[
            Decision,
            DecisionInput,
        ](DeductionInput(context = DecisionInput(
            review = review,
            policy = task.criteria,
        )))]
    return decision
```

This topology declares evidential review followed by deductive intent.
Execution remains unspecified at this layer. `Decision` has unchecked assurance;
its `approved` field is a domain decision, not `Supported`, `Validated`, or a
kernel proof. Standard method metadata records classification independently.

## Materialize the implementation

Materialization binds each abstract occurrence to executable code. The agent
below applies one typed Open Agent Skill inside a workflow. A pure function then
applies the release policy.

```prism title="materialization.prism" source="examples/language/release_review/materialization.prism"
from examples.language.release_review.reasoning import (
    AssessRelease,
    Decision,
    DecisionInput,
    Review,
    ReviewTask,
)
from examples.language.release_review.release_review_skill import release_review_skill
from prism.reasoning.methods.deductive import DeductionInput

agent review_change(
    task: ReviewTask,
) -> Result[Generated[Review], ModelFailure]
    ! {AI.Generate, Context.Disclose}:
    skills: Skills[ReviewTask] = [release_review_skill]

workflow produce_review(
    task: ReviewTask,
) -> Generated[Review]
    fails ModelFailure
    ! {AI.Generate, Context.Disclose}:
    sequence:
        [review: review_change(task)]
    return review

def apply_release_policy(
    source: DeductionInput[DecisionInput],
) -> Decision:
    review = source.context.review.value
    return Decision(
        approved = (
            review.tests_passed
            and review.risk <= source.context.policy.maximum_risk
        ),
        rationale = review.summary,
    )

assess_release = AssessRelease(
    review = produce_review,
    decision = apply_release_policy,
)
```

Calling `assess_release(task)` constructs an executable workflow that preserves
the declared reasoning topology. Prism checks its types, effects, failures, and
capabilities before the runtime invokes the model.

The [release-review skill](examples/language/release_review/skills/release-review/SKILL.md)
and its compiled module are included. To rebuild the typed skill from the
repository root:

```bash
uv run prism build skill \
  examples/language/release_review/skills/release-review \
  --contract examples.language.release_review.reasoning.ReviewTask \
  --out examples/language/release_review/release_review_skill
```

The entry point supplies an illustrative change and policy, receives the runtime
permissions explicitly, and executes the materialized reasoning:

```prism title="main.prism" source="examples/language/release_review/main.prism"
import examples.language.release_review.reasoning as release
from examples.language.release_review.materialization import assess_release
from prism.reasoning.methods.evidential import EvidentialInput

def main(
    model_access: ModelGenerate,
    disclosure: ContextDisclose,
) -> Result[release.Decision, ModelFailure] ! {AI.Generate, Context.Disclose}:
    task = EvidentialInput(
        observations = release.Change(
            summary = "Reject empty release notes.",
            diff = "-return True\n+return notes != \"\"\n",
        ),
        criteria = release.ReleasePolicy(maximum_risk = 1),
    )
    return solve release.AssessRelease(task) using assess_release(task)
```

After [installation](docs/docs/installation.md), run from the repository root:

```bash
uv run prism check examples/language/release_review/main.prism
uv run prism compile examples/language/release_review/main.prism
uv run prism run examples/language/release_review/main.prism --handler fake
```

The fake handler supplies a synthetic review; execution succeeds with a decision
whose `approved` field is `False`. This example does not execute tests:
`tests_passed` is a generated assertion, and the decision remains unchecked.
The documentation tests check these snippets against their source files, compile
them, and run the entry point with the fake handler.

## Bring your existing skills and code

Prism can serve as the reasoning layer for an existing codebase. The skill
builder compiles an Open Agent Skill into a typed `Skill[Task]`. A typed
[`Python.Call`](packages/prism-adapter-python/README.md) adapter exposes an
existing Python operation. Ordinary Prism functions and workflows compose both.
Provider credentials, model selection, and deployment details live in runtime
configuration and stay outside application source.

## Development verification

Install `uv` and Node.js 22, then set up the Python environment and the
repository-managed commit and pre-push hooks:

```bash
uv sync --all-packages --frozen
uv run pre-commit install
```

The pre-push hook runs the same Python quality, REUSE compliance, and VS Code
extension checks as the GitLab pipeline. Run the complete verification directly
at any time with `./check-all.sh`.

Python architecture contracts run before pytest in `./check.sh`, including in
GitLab CI and the pre-push hook. To run only architecture verification:

```bash
uv run lint-imports
uv run pytest -n0 tests/test_architecture_boundaries.py tests/test_architecture_contracts.py tests/test_dependency_declarations.py
```

The Import Linter contracts in `pyproject.toml` enforce language layers and
distribution dependency directions, including indirect and type-checking imports.
The pytest checks enforce public language imports, distribution cycles, namespace
ownership, and packaging rules. Fixture tests exercise forbidden relative imports,
submodule imports, indirect dependencies, and undeclared language layers.

Two exact edges are exempt from the lightweight language-server contract: the IDE
server's optional workbench loader and the SDK's optional knowledge loader. Tests
require those imports to stay inside functions. One existing private language edge,
`prism.tooling.lsp.symbols.intrinsics -> prism.language.developer.api`, is recorded in the
public API test because go-to-definition reads intrinsic source locations there.
Remove that exception when a public source-location API replaces the dependency.
Obsolete exceptions fail verification; avoid broad package exclusions.

When adding a distribution, update the import roots and namespace ownership map.
When adding a language layer, declare its position in the exhaustive layer contract
and its public namespace in the architecture tests. Imports loaded through dynamic
plugin discovery are outside the static graph and still need integration tests.

The architecture tests also require every direct dependency import to have a
declaration in its owning distribution's `project.dependencies` or
`project.optional-dependencies`. Transitive and development dependencies do not
satisfy this check. External module ownership is explicit in
`test_imported_dependencies_are_declared` (for example, `yaml` belongs to `PyYAML`);
unknown imports fail until their ownership and dependency declaration are added.
This checks declaration presence across all extras and environment markers, not
version compatibility, extra activation, or whether a base installation works.

## Inspect the guarantees

`prism check` exposes normalized occurrence contracts. `prism run` records
actual producers and upstream ancestry separately from assurance and claim
disposition. The Reasoning Log consumes those same structured fields.

- The strict example returns version `7` and proves a property of that exact
  returned target. Its plan permits literal or computed production.
- The refinement example retains generated narration and computed plan
  ancestry, accepts policy support explicitly, and returns a plan validated
  under its simulator model. It does not prove real-world landing safety.

See [trust boundaries](notes/EPISTEMIC_TRUST_LINK.md) for typed validators,
accepted support, native proof limitations, and complete executable examples.
String-only computation/validator annotations, precomputed Boolean policy
requirements, and rejected `Supported` values have been removed. Pure structural
helpers need no abstract binding. Persisted traces use version `11`; regenerate
older traces instead of interpreting them as current contracts.
