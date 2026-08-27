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
selects an agent, model, or runtime.

```prism
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

This topology requires an evidential review followed by a deterministic
deduction. Execution remains unspecified at this layer.

## Materialize the implementation

Materialization binds each abstract occurrence to executable code. The agent
below applies one typed Open Agent Skill inside a workflow. A pure function then
applies the release policy.

```prism
from release.reasoning import (
    AssessRelease,
    Decision,
    DecisionInput,
    Review,
    ReviewTask,
)
from release.release_review_skill import release_review_skill
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
