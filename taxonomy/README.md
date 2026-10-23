# Prism component taxonomy

This directory develops an initial, evidence-grounded taxonomy of the
functional elements found across the Prism workflow catalog. It is deliberately
outside the viewer and does not change, annotate, or reinterpret the checked
workflow graphs at runtime.

The taxonomy does not assume that every Prism reasoning occurrence performs
reasoning. It first separates operational work, discourse work, evaluation,
control, and inference, then describes applicable dimensions independently.
This avoids category errors such as treating retrieval as deduction or treating
computational implementation as an epistemic warrant.

## Contents

- `taxonomy.md` defines the facets, taxa, boundaries, and initial hypotheses.
- `taxonomy.json` provides the stable machine-readable taxon identifiers.
- `component-mapping.csv` maps every checked occurrence to those identifiers.
- `corpus-inventory.md` summarizes the source corpus and recurring functions.
- `mapping-report.md` reports coverage, ambiguity, and taxonomy extensions.
- `audit-report.md` records the full version 0.6 structural and corpus-mapping
  review, corrections, disputed cases, and remaining work.
- `proposals/` retains the detailed formal, argumentative, causal, and
  uncertainty design analyses behind version 0.2.
- `validate.py` checks catalog coverage, identifiers, and mapping invariants.

## Evidence status

Assignments are analytical annotations derived from authored component names,
commentary, relations, contracts, examples, and attached skill roles. They are
not Prism compiler output and do not establish that a component's inference is
valid, deterministic, causal, probabilistic, or empirically grounded.

Confidence describes the support for the classification, not the quality of
the underlying component. The taxonomy is an initial hypothesis intended to
evolve as new projects expose missing distinctions or counterexamples.

Versions 0.2–0.6 also contain canonical but currently uninstantiated categories.
They remain `provisional`, are not forced into `component-mapping.csv`, and are
distinguished from corpus-supported `active` taxa. `deprecated` taxa are
compatibility entries with explicit replacements and are rejected in current
mappings. Knowledge-representation paradigms and computational mechanisms
describe encoding and execution; they do not by themselves establish reasoning
or validity.

Version 0.6 also decomposes the legacy `computational_character` column into
independent constraint-regime, determinacy, procedure-family, and statefulness
facets. The old column remains populated only as a migration bridge.

## Internal skills

- `$prism-taxonomy-builder` proposes evidence-backed taxonomy changes.
- `$prism-component-classifier` maps new or revised components.
- `$prism-taxonomy-auditor` checks coverage and conceptual consistency.

Validate the maintained artifacts from the repository root:

```sh
python taxonomy/validate.py
```
