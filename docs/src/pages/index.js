// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import CodeBlock from '@theme/CodeBlock'
import Heading from '@theme/Heading'
import Layout from '@theme/Layout'
import Link from '@docusaurus/Link'
import ThemedImage from '@theme/ThemedImage'
import useBaseUrl from '@docusaurus/useBaseUrl'

const reasoningExample = `from prism.reasoning.methods.deductive import DeductionInput, Deductive
from prism.reasoning.methods.evidential import Evidential
from release.types import Decision, DecisionInput, Review, ReviewTask

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
    return decision`

const materializationExample = `from release.reasoning import (
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
)`

function HomepageHeader() {
  return (
    <header className="hero hero--primary">
      <div className="container text--center padding-vert--xl">
        <Heading as="h1" className="hero__title">
          Build agentic systems
          <br />
          with <span className="hero__title-gradient">reasoning</span> you can see.
        </Heading>
        <p className="hero__subtitle">
          <b>Prism </b>
          keeps reasoning explicit and interpretable, so agents, skills, and
          workflows can scale while you stay in control.
        </p>
        <div>
          <Link className="button button--secondary button--lg margin-right--md" to="/docs/quick-start">
            Quick start
          </Link>
          <Link className="button button--outline button--secondary button--lg" to="/docs/installation">
            Installation
          </Link>
        </div>
      </div>
    </header>
  )
}

function HomepageContent() {
  const prismImageSources = {
    light: useBaseUrl('/img/prism-light.png'),
    dark: useBaseUrl('/img/prism-dark.png'),
  }

  return (
    <main>
      <section className="container margin-vert--xl">
        <article className="home-content markdown">
          <div className="home-introduction">
            <div className="home-introduction__art">
              <ThemedImage
                alt="Prism spectrum illustration"
                className="home-introduction__image"
                sources={prismImageSources}
              />
            </div>

            <div className="home-introduction__copy">
              <p>
                <strong>
                  Keep complex agentic systems understandable and governable.
                </strong>
              </p>

              <p>
                As agentic systems scale, reasoning gets buried across prompts
                and orchestration logic. The result is a system that becomes
                increasingly difficult to understand and control as a whole.
              </p>

              <p>
                Prism makes reasoning explicit and declarative. It decomposes
                reasoning into reusable, general-purpose types and materializes
                them as agents, skills, and workflows, preserving interpretability
                and control as systems scale.
              </p>
            </div>
          </div>

          <ul>
            <li>
              <strong>Reason at a high level of abstraction.</strong>
              Describe epistemic intent and reasoning topology before selecting
              the agents, skills, models, and workflows that materialize them.
            </li>
            <li>
              <strong>Separate reasoning from implementation.</strong>
              Declare the reasoning strategy and data flow independently from
              the agents, models, policies, and functions that execute it.
            </li>
            <li>
              <strong>Keep complex systems interpretable.</strong>
              Inspect explicit dependencies, capabilities, failures, provenance,
              and assurance boundaries from source code through the execution
              trace.
            </li>
          </ul>

          <Heading as="h2">Describe the reasoning</Heading>

          <p>
            A <code>reasoning.prism</code> file captures what must be reasoned
            about before the program selects an agent, model, or runtime.
          </p>

          <CodeBlock language="prism">{reasoningExample}</CodeBlock>

          <p>
            This topology requires an evidential review followed by a
            deterministic deduction. Execution remains unspecified at this
            layer.
          </p>

          <Heading as="h2">Materialize the implementation</Heading>

          <p>
            Materialization binds each abstract occurrence to executable code.
            The agent below applies one typed Open Agent Skill inside a workflow.
            A pure function then applies the release policy.
          </p>

          <CodeBlock language="prism">{materializationExample}</CodeBlock>

          <p>
            Calling <code>assess_release(task)</code> constructs an executable
            workflow that preserves the declared reasoning topology. Prism
            checks its types, effects, failures, and capabilities before the
            runtime invokes the model.
          </p>

          <Heading as="h2">Bring your existing skills and code</Heading>

          <p>
            Prism can serve as the reasoning layer for an existing codebase. The
            skill builder compiles an Open Agent Skill into a typed{' '}
            <code>Skill[Task]</code>. A typed{' '}
            <Link to="https://github.com/idiap/prism/-/blob/main/packages/prism-adapter-python/README.md">
              <code>Python.Call</code>
            </Link>{' '}
            adapter exposes an existing Python operation. Ordinary Prism
            functions and workflows compose both. Provider credentials, model
            selection, and deployment details live in runtime configuration and
            stay outside application source.
          </p>
        </article>
      </section>
    </main>
  )
}

export default function Home() {
  return (
    <Layout
      title="Explicit, typed, and verifiable reasoning"
      description="Documentation for Prism, an agentic reasoning programming language.">
      <HomepageHeader />
      <HomepageContent />
    </Layout>
  )
}
