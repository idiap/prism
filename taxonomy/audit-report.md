# Prism taxonomy full review — version 0.6

## Outcome

The taxonomy has a sound central idea—a faceted classification that separates
operations, inference, evaluation, control, discourse, representation, and
execution—but version 0.5 had accumulated several category errors while growing
from the corpus-derived seed into a broader canonical vocabulary. Version 0.6
corrects the highest-impact problems while preserving every source workflow and
all 152 occurrence keys.

The maintained artifact now contains 20 facets and 373 taxa. Breadth is not
treated as corpus support: only taxa used in the maintained mapping are
`active`; defined but uninstantiated taxa remain `provisional`; compatibility
labels are `deprecated` with replacements.

## Review scope and method

The review covered:

- all 152 authored occurrences in 33 workflows and 3 projects;
- `taxonomy.md`, `taxonomy.json`, `component-mapping.csv`,
  `corpus-inventory.md`, and `mapping-report.md`;
- the mapping generator and validator;
- inclusion/exclusion boundaries, hierarchy, cardinality, identifier stability,
  annotation level, corpus support, and source-evidence discipline;
- disputed cases inspected against method, input/output types, relations,
  commentary, and workflow context in `catalog/graphs.json`.

The review followed two independent tests. The mechanical audit checked exact
coverage, uniqueness, known identifiers, boundaries, hierarchy cycles, and
cardinality. The conceptual audit asked whether each label answered one clear
question and whether the source evidence satisfied its positive and exclusion
tests.

## Findings and improvements

### 1. Prose identifiers diverged from machine identifiers — high severity

The prose used entries such as `extract`, `formal-deduction`, and
`reporting-presentation`, while the JSON and CSV used identifiers such as
`extraction`, `formal_deductive`, and `presentation`. This made apparently
normative examples impossible to map without interpretation.

Improvement:

- declared `lower_snake_case` as the canonical identifier form;
- made `taxonomy.json` normative for identifiers;
- aligned the operational-role documentation with actual identifiers;
- defined display labels as derived labels, not alternate IDs;
- added validator checks for facet and taxon identifier form.

This follows the useful distinction in the [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/)
between concept identity, notation, preferred labels, and broader/narrower
relations without requiring this project to adopt RDF.

### 2. `evidential` conflated four independent dimensions — critical

The old mapping assigned `evidential` to 38 occurrences spanning evidence
bounding, grounding, selection, claim calibration, readiness, routing, and
decision. That violated the stated rule that reasoning archetypes describe
inference-making or testing rather than every operation that touches evidence.

Improvement:

- deprecated the broad `evidential` archetype;
- introduced `evidential_assessment` with a strict evidence-to-claim-status
  test;
- retained evidence preparation as `evidence_admission`, `boundary_setting`, or
  `grounding`;
- retained evidence dependence as `warrant_basis.empirical_evidential`;
- retained readiness and routing as control operations.

The result is nine mapped `evidential_assessment` occurrences. Evidence
bounding and workflow routing no longer receive a reasoning archetype merely
because their method names begin with “Evidential.”

### 3. Suggestive names were treated as execution evidence — critical

Version 0.5 classified six `Deductive...` methods as
`deterministic_given_premises`, eleven projections/extractions as
`deterministic_structure_preserving`, and three finalizers as
`deterministic_packaging`. The corpus generally specifies contracts and intended
semantics, not complete executable procedures, so these assignments contradicted
the taxonomy's own exclusion tests.

Improvement:

- removed all 20 unsupported deterministic assignments;
- left the six deductive occurrences as `not_explicitly_authored` for execution
  character while preserving the `deductive` reasoning archetype;
- deprecated `computational_character` as a compatibility facet;
- added independent `constraint_regime`, `execution_determinacy`,
  `procedure_family`, and `statefulness` facets;
- strengthened regression tests so a deductive name cannot establish
  determinism.

### 4. Causal and mechanistic reasoning were collapsed and leaked from domain vocabulary — critical

The `causal_mechanistic` label combined intervention-sensitive causal inference
with mechanistic explanation. It was also inferred from words such as
“mechanism,” “circuit,” or “resistance biology,” causing scope-grounding steps
to be classified as core reasoning.

Improvement:

- deprecated `causal_mechanistic`;
- made `causal_reasoning` and `mechanistic_reasoning` independent roots;
- required mechanistic cases to expose organized entities, activities,
  productive relations, and conditions;
- reclassified `melanoma_resistance/bounded_scope` and
  `sva_generator_complex/establish_design_evidence` as information operations
  without a reasoning archetype;
- retained four genuinely supported mechanistic cases.

### 5. Computational character mixed orthogonal axes — high severity

Labels such as “structured judgment” simultaneously described constraint
strength, non-uniqueness, procedure, and human or model involvement. Meanwhile,
the prose already described these as separate subfacets, but the JSON did not.

Improvement:

- represented constraint regime, determinacy, procedure family, and
  statefulness as separate machine-readable facets;
- added workflow-level topology for sequential, parallel, convergent,
  divergent, iterative, and feedback-controlled structures;
- explicitly scoped topology to workflows or subgraphs so it cannot be
  projected onto every contained occurrence;
- retained the old CSV field only as a migration bridge.

### 6. Reasoning realization mixed generation, medium, formality, and executor — high severity

The realization tree placed `formal_symbolic`, `computational_symbolic`, and
`human_symbolic` under one `symbolic` branch even though they answer different
questions. Candidate generation was also easy to mistake for an inferential
license.

Improvement:

- added explicit `candidate_production`, `representation_medium`, `formality`,
  `executor`, and `integration` axes to every realization taxon;
- deprecated `generative_symbolic_reasoning`, which mixed an operation and
  realization without naming a warrant;
- documented symbolic candidate generation as a combination of operational
  role, realization, and an independently supported reasoning archetype.

### 7. Epistemic-object hierarchy contained category errors — high severity

Four parent relations confused content, status, representation, or target:

- `proposition` was under `formal_symbolic_object`, excluding informal
  propositions;
- `evidence_strength` was under raw evidence despite being an assessment;
- `mechanism` was under `model_object`, conflating a target mechanism with its
  representation;
- `proof_certificate` was under `proof`, although a compact certificate need
  not encode the full proof.

Improvement:

- made `proposition` representation-neutral;
- placed claims and assumptions under propositional content while keeping
  stipulative or descriptive definitions as an independent object type;
- placed evidence strength under `evaluation_decision_object`;
- separated `mechanism` from `mechanistic_model`;
- placed proof certificates directly under `inferential_artifact`.

### 8. Status did not consistently mean corpus support — high severity

Several facets not present in the CSV contained `active` taxa, while some
mapped active values had no current instance. This made “active” ambiguous
between conceptual approval and empirical support.

Improvement:

- formalized status semantics at the schema root;
- changed unpopulated warrant, force, and uncertainty values to `provisional`;
- mapped decomposition and presentation where the corpus already supports them;
- made the validator reject an active mapped taxon with no maintained instance
  and reject a provisional or deprecated value used in the current CSV.

### 9. Validation covered references but not taxonomy quality invariants — high severity

The old validator checked coverage and identifiers in CSV values, but required
decision boundaries only for provisional taxa and did not check facet metadata,
cardinality, identifier form, status-to-use consistency, or conceptual family
constraints.

Improvement:

- require every taxon to have a definition, positive inclusion test, and
  neighboring exclusion test;
- validate facet cardinality, mapping status, annotation level, and ID form;
- require replacement guidance for deprecated taxa;
- require core-reasoning occurrences to have a reasoning archetype;
- prevent reasoning archetypes on information, discourse, or control families;
- validate every realization taxon's declared axis.

This treats validation as a first-class artifact in the same spirit as the
[W3C SHACL specification](https://www.w3.org/TR/shacl/): constraints are
explicit, reusable, and produce inspectable failures rather than remaining
prose expectations.

## Disputed occurrence decisions

| Occurrence | Previous classification | Competing interpretation | Source evidence | Version 0.6 action |
| --- | --- | --- | --- | --- |
| `melanoma_resistance/bounded_scope` | core reasoning; evidential + causal/mechanistic | evidence and scope preparation | Output is `BoundedMelanomaScope`; commentary says bounding occurs *before* resistance inference | information operation; `boundary_setting`; no reasoning archetype |
| `sva_generator_complex/establish_design_evidence` | core causal/mechanistic reasoning | grounding of a design-evidence model | Commentary says it unifies supplied facts, contracts, mechanisms, and testability pressure before assertion design | information operation; `grounding`; no reasoning archetype |
| `bounded_ebr/bounded_evidence` | evidential reasoning | evidence boundary construction | Output is bounded evidence; no evidence-to-claim status is inferred | information operation; no reasoning archetype |
| `bounded_ebr/claim_status` | broad evidential label | evidence-to-claim support assessment | Candidate and refutation record jointly calibrate a bounded claim status | `evidential_assessment` |
| `theorem_proof_delivery/exact_theorem_claim` | deterministic deduction | deductive intent with unspecified procedure | The contract names deduction, but no complete calculus or executable procedure is retained | keep `deductive`; execution `not_explicitly_authored` |
| `cross_tumor/circuit_model` | causal/mechanistic composite | mechanistic model construction | Commentary requires a circuit model preserving pattern and divergence | `model_based` + `mechanistic_reasoning` |
| `verification_debug_diagnosis/represent_and_detect_debug_findings` | analytical reasoning | compound representation and detection | It constructs typed findings and detects supported findings but does not yet synthesize the diagnosis | information operation; no reasoning archetype |

## Mapping impact

| Measure | Version 0.5 | Version 0.6 |
| --- | ---: | ---: |
| Occurrence keys covered | 152 | 152 |
| Components with a reasoning archetype | 97 | 66 |
| Broad `evidential` assignments | 38 | 0 |
| Specific `evidential_assessment` assignments | 0 | 9 |
| Composite `causal_mechanistic` assignments | 6 | 0 |
| Specific `mechanistic_reasoning` assignments | 0 | 4 |
| Unsupported deterministic compatibility assignments | 20 | 0 |
| Primary core-reasoning components | 40 | 38 |
| Primary information/evidence operations | 22 | 24 |

The reduction in reasoning labels is intentional. It reflects a sharper
commitment-change test rather than lost coverage.

## Remaining opportunities

1. Populate the currently uninstantiated facets only through focused audits.
   Warrant, object type/role, KR, mechanism, force, uncertainty, realization,
   and the new computational facets should not be inferred automatically from
   type names.
2. Audit workflow topology directly from graph relations. Parallelism,
   convergence, and feedback are supported visually in the viewer but not yet
   maintained as taxonomy annotations.
3. Split compound Hardware Verification occurrences where generation,
   evaluation, detection, synthesis, and routing have independent success
   criteria.
4. Replace name-led generation rules with reviewed occurrence overrides or an
   annotation source file. The current generator is reproducible, but names are
   still one of its strongest cues and confidence remains too coarse.
5. Add negative-evidence records to the mapping so rejected labels such as
   probabilistic, formal, causal, or deterministic can be audited per
   occurrence rather than reconstructed from prose.
6. Add independent review or inter-annotator agreement for ambiguous
   conceptual, model-based, comparative, and mechanistic cases.
7. Consider a SKOS export for identifiers, labels, hierarchy, and mappings and
   a provenance layer aligned with [PROV-O](https://www.w3.org/TR/prov-o/) for
   annotation sources and revisions. These would be exports; the JSON remains
   the project source of truth.

## Acceptance checks

Version 0.6 is acceptable when:

- every catalog occurrence has exactly one unique mapping row;
- every used mapping value is an active known taxon;
- no information, discourse, or control occurrence carries a reasoning
  archetype;
- all facets declare cardinality, mapping status, annotation level, and a
  definition;
- every taxon has positive and exclusion boundaries;
- deprecated taxa have replacements and are unused by current mappings;
- hierarchy cycles and unknown parents are rejected;
- tests prevent method names from establishing determinism or mechanism.

Run `python taxonomy/validate.py` and `python -m unittest tests.test_taxonomy`
from the repository root to verify these conditions.
