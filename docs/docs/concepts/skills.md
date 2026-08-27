---
# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

id: skills
title: Skills
description: Build Open Agent Skills into typed Prism artifacts and attach them to agents.
slug: /concepts/skills
---

A Prism skill is a checked value with type `Skill[Task]`. The task parameter
connects an Open Agent Skill to the structured input expected by an agent.
Prism builds the external skill once and imports the resulting module during
checking and execution.

## Create the task contract

Define the task in a Prism module that both the application and generated skill
can import.

```prism title="review/contracts.prism"
type ReviewTask:
    repository: String
    change: String
```

The task type should contain the information that the skill instructions may
use. `Skill[ReviewTask]` is invariant, so it cannot fill a
`Skill[SecurityTask]` slot even when both records have similar fields.

## Write an Open Agent Skill

Place `SKILL.md` in a directory whose name matches the frontmatter `name`.

```markdown title="skills/change-review/SKILL.md"
---
name: change-review
description: Review a change against the supplied repository context.
metadata:
  version: "1.0.0"
---

# Change review

Inspect the supplied change and return the requested structured review.

- Ground every finding in the supplied task.
- Separate blocking findings from follow-up suggestions.
- Return only the requested review value.
```

The instruction body must contain content. Supported regular resource files
under the skill directory are embedded into the generated module. Credential
files are rejected. Script files also fail the build because executable
behavior requires a separately declared typed tool.

## Build the typed module

Run the skill builder from the Prism project root.

```bash
/path/to/prism/.venv/bin/prism build skill skills/change-review \
  --contract review.contracts.ReviewTask \
  --out review/generated/change_review_skill
```

The command validates the skill manifest, resolves the qualified Prism task
type, bundles supported resources, checks the generated source, and writes
`review/generated/change_review_skill.prism`. Its exported value is named from
the skill identifier.

```prism
from review.generated.change_review_skill import change_review_skill
```

For the `change-review` identifier, the export has the following type.

```text
change_review_skill: Skill[ReviewTask]
```

The generated module contains the manifest fields, instruction text, and
resource bundle. Execution therefore has no dependency on the original skill
directory.

## Attach the skill to an agent

Declare a persistent list whose task parameter matches the skill.

```prism
agent reviewer(
    task: ReviewTask,
) -> Result[Generated[Review], ModelFailure]
    ! {AI.Generate, Context.Disclose}:
    skills: Skills[ReviewTask] = [change_review_skill]
```

An agent call may add another compatible skill for that invocation.

```prism
result = reviewer(
    task,
    skills = [security_review_skill],
)
```

Persistent and invocation skills are both included in the generation request.
Their instructions and embedded resources become visible to the selected
generation handler. The invocation leaves the agent declaration unchanged.

## Rebuild after a change

Run `prism build skill` again whenever `SKILL.md` or a bundled resource changes.
Then check the importing entry point.

```bash
/path/to/prism/.venv/bin/prism build skill skills/change-review \
  --contract review.contracts.ReviewTask \
  --out review/generated/change_review_skill
/path/to/prism/.venv/bin/prism check main.prism
```

Build failures identify unsupported manifest fields, invalid names, unresolved
task contracts, empty instructions, credential files, and script resources.

Continue with [agents](./agents.md) to use the artifact and [hooks](./hooks.md)
to attach provider lifecycle behavior. [External artifacts](./external-artifacts.md)
explains standalone builds and project conversion.
