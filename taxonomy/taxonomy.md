# Prism workflow component taxonomy

Status: canonical extension with corpus-derived seed (version 0.6)

## Purpose

This taxonomy describes what a Prism workflow component does without calling
every transformation "reasoning." It was induced from the current catalog of
33 workflows in Physics Discovery, Oncology Discovery, and Hardware
Verification. It is intended for annotation, comparison, and later revision;
it is not a claim that the method names already present in the catalog are a
complete or philosophically settled ontology.

The central design decision is to use **orthogonal facets**, not one forced
tree. Material, formal, and computational describe sources of warrant;
retrieval and extraction describe operations; deduction and abduction describe
reasoning; argument construction describes discourse organization; and
determinism describes execution behavior. A component can therefore receive
several labels without conflating these dimensions.

The principal unit of classification is one occurrence (one typed application
in a workflow), not necessarily a reasoning occurrence and not merely the
method name. Object facets apply to values participating in an occurrence;
topology applies to a workflow or subgraph.

## The model at a glance

Each occurrence receives:

1. exactly one **primary functional family**;
2. one or more **operational roles**;
3. zero or more **reasoning archetypes**;
4. zero or more **discourse-organization forms**;
5. independent **warrant_basis** labels;
6. independent **constraint regime**, **execution determinacy**, **procedure
   family**, and **statefulness** facets;
7. zero or more **knowledge-representation paradigms**;
8. independently recorded **computational mechanisms** and **epistemic force**;
9. where applicable, **uncertainty sources and representations**;
10. typed **epistemic objects** and their roles;
11. a multi-axis **reasoning_realization** profile when authored;
12. workflow-level **topology** where graph relations support it; and
13. evidence, confidence, and any explicit abstentions.

Only the first facet is required and exclusive. Every other facet follows its
declared cardinality and may remain empty when the source does not support it.

## Identifiers, hierarchy, and status

`taxonomy.json` is normative for identifiers and structural metadata. Canonical
facet and taxon identifiers use `lower_snake_case`; prose labels are display
labels, never alternate identifiers. Mappings store the most specific supported
taxon, while consumers derive broader index entries by following `parent`.

Status and corpus support are deliberately coupled:

- `active` means at least one maintained corpus annotation supports the taxon;
- `provisional` means the taxon is defined for testing but is not yet supported
  by a maintained annotation or is not yet mature;
- `deprecated` means compatibility only and requires explicit replacement
  guidance.

This prevents a canonical but currently absent category from appearing to be
empirically established in the Prism corpus.

## Facet 1: primary functional family

Use the component's intended output and success condition, not its verb alone.

### Information and evidence operation (`information_and_evidence_operation`)

Locates, admits, extracts, normalizes, bounds, selects, or represents
information while preserving its declared epistemic ceiling.

- Include: retrieval, extraction, normalization, evidence admission, bounding,
  projection, and typed representation.
- Exclude: producing a new claim, verdict, control decision, or communicative
  artifact as the principal output.

### Core reasoning (`core_reasoning`)

Produces or revises a claim, hypothesis, implication, pattern, explanation,
diagnosis, or model through an epistemic inference.

- Include: deduction, induction, abduction, similarity_based, analogical, causal/mechanistic,
  model_based, contrastive, conceptual, and diagnostic inference.
- Exclude: reshaping information, evaluating an existing candidate, applying a
  route, or packaging a settled artifact.

### Evaluation and judgment (`evaluation_and_judgment`)

Tests, critiques, calibrates, validates, or assigns status to an existing
candidate relative to evidence or criteria.

- Include: refutational review, support assessment, readiness judgment, claim
  calibration, semantic validation, and quality critique.
- Exclude: candidate formation and a route or plan whose primary result is the
  next action. Reasoning-archetype labels may still describe how an evaluation
  reaches its verdict.

### Workflow control and governance (`workflow_control_and_governance`)

Chooses, routes, gates, plans, decomposes, monitors, or revises what the system
should do next.

- Include: continue/pivot/stop routing, planning, workflow decomposition,
  admission gates, feedback control, and capability evolution.
- Exclude: an assessment that a later component happens to use for routing,
  unless this occurrence selects the path.

### Discourse and artifact organization (`discourse_and_artifact_organization`)

Constructs or organizes a communicative, executable, or deliverable artifact
without making inference its dominant product.

- Include: explanation or argument organization, report synthesis,
  claim-bounded presentation, specifications, assertion packages, and
  finalization.
- Exclude: any structured object merely because it contains text, and artifact
  generation whose principal success condition is a new epistemic conclusion.

An occurrence with mixed behavior still gets one primary family, chosen by its
principal output contract. Record the other behaviors as operational roles and,
where justified, secondary families.

## Facet 2: operational roles

Operational roles say how information is acted on. They are not automatically
reasoning types.

| Role | Inclusion test | Important exclusion |
| --- | --- | --- |
| `retrieval` | Locates and returns existing items from an identified external collection. | Supplied evidence and model-generated recall are not retrieval. |
| `extraction` | Copies identifiable fields, spans, facts, or events from a source. | A new interpretation or claim is not extraction. |
| `normalization` | Converts variants into a canonical schema or vocabulary. | Normalization does not assess truth. |
| `boundary_setting` | Establishes admissible domain, evidence, claims, or search limits. | Size truncation alone is not epistemic bounding. |
| `grounding` | Anchors later work to evidence, semantics, context, or provenance. | Forwarding an unexamined value is not grounding. |
| `evidence_admission` | Accepts or rejects supplied evidence under relevance, provenance, or admissibility criteria. | Summarization alone is not admission. |
| `projection` / `transformation` | Maps content under an explicit preservation and omission contract. | A new explanatory claim requires a reasoning label. |
| `selection_or_ranking` | Retains, rejects, or orders alternatives under criteria. | Ranking does not imply probability. |
| `classification` / `detection` | Assigns defined classes or identifies a target pattern, event, fault, or gap. | Explaining a detected condition is diagnostic reasoning. |
| `hypothesis_formation` / `derivation` / `pattern_inference` | Forms candidates, makes consequences explicit, or generalizes a pattern. | Their epistemic archetype must still be separately supported. |
| `analogy_or_transport` | Transfers a relation or candidate conclusion through a source-target correspondence. | Similarity measurement alone licenses no transfer. |
| `model_construction` / `model_probing` | Builds or interrogates an explicit model. | A narrative called a model is insufficient. |
| `falsification_or_pressure_test` / `assessment_or_critique` | Searches for defeaters or evaluates an item against criteria. | A generic review is not automatically refutational. |
| `calibration` / `readiness_gating` | Sets epistemic strength or decides whether requirements for a next action are met. | Claim status and workflow readiness are different products. |
| `decision` / `routing_or_gating` | Chooses an action or controls a concrete next path. | Merely reporting options is not a decision. |
| `planning_or_recommendation` / `forecasting` | Proposes future action or projects a future state. | Description of a current state is neither. |
| `decomposition` / `synthesis_or_construction` | Divides a whole or integrates inputs into a new organized whole. | Unstructured listing or concatenation is insufficient. |
| `refinement` / `finalization` | Revises a prior object or packages a settled deliverable. | Substantive new inference must be labeled separately. |
| `diagnostic_analysis` | Integrates findings into a diagnosis and possibly discriminating probes. | Detection alone is insufficient. |

Roles compose. `ExtractSvaSemanticModel`, for example, can be `extraction`,
`normalization`, and `transformation`; that does not force an
epistemic-reasoning label.

`similarity_measurement` computes or records resemblance, distance, or
neighborhood. It remains an operational role unless that relation licenses a
classification, prediction, ranking, retrieval-relevance judgment, or other
epistemic conclusion.

Formalization roles require an additional distinction:

- `formalization` translates informal or differently formal content into a
  declared formal language;
- `autoformalization` performs that translation substantially through an
  automated or learned system;
- `formal_validation` checks syntax, typing, semantics, or proof obligations;
- `symbolic_manipulation` rewrites or normalizes symbolic expressions.

None of these operations is automatically deduction. An LLM may propose a
formalization, a parser may deterministically translate one, and a proof
assistant may validate one; those mechanisms make different guarantees.

Argumentative analysis also begins with two foundational operations:

- `assumption_elicitation` surfaces presuppositions, background commitments,
  boundary conditions, and missing assumptions, preserving whether each was
  stated, requested, or reconstructed;
- `definition_elicitation` surfaces the meaning, identity conditions,
  operationalization, and scope of terms on which an argument depends.

Eliciting an explicit statement is not itself an epistemic inference. Inferring
an unstated premise or term-use commitment is stronger and receives the
corresponding reasoning-archetype label below.

## Facet 3: reasoning archetypes

Apply these only when the occurrence performs an epistemic move. The current
archetype branches are below.

### Deductive reasoning

The conclusion is presented as licensed by premises, constraints, or rules.

- `formal_deductive`: the rule system, formal semantics, proof obligations, or
  certificate is explicit enough that validity is meant to be mechanically
  checkable.
- `informal_deductive`: the conclusion is intended to follow necessarily, but
  the inferential rules or proof object are expressed in domain language rather
  than a complete formal calculus.

A typed input/output signature is not sufficient evidence for formal deduction.
For example, `DeductiveExactTheoremClaimDerivation` is a strong candidate, but
formal status should ultimately depend on its explicit premises and certificate,
not on the word "Deductive" alone.

The canonical formal branch refines `formal_deductive` into:

- `logical_inference`: applies an identified logic;
- `equational_inference`: derives equalities or consequences through equality,
  substitution, congruence, or rewrite semantics;
- `type_theoretic_inference`: derives typing, inhabitation, unification, or
  type-equivalence judgments;
- `constraint_entailment`: establishes what is forced or impossible under a
  declared constraint set;
- `theorem_proving`: constructs a checkable proof or certificate.

Equation conjecture is deliberately outside this truth-preserving branch. A
CAS rewrite may be equational inference; an LLM that proposes a governing
equation performs candidate generation and requires a later check. Symbolic
surface form alone supports an equation object, not an inference archetype.

### Definitional reasoning

`definitional_reasoning` uses an explicit definition as the inferential license
or makes the definition itself the object of construction or evaluation. It
contains:

- `definition_formation`: proposes necessary, sufficient, constitutive, or
  operational application conditions;
- `definition_application`: derives membership, identity, or a direct
  consequence from an existing definition;
- `definition_revision`: changes a definition while tracking preserved and
  rejected extensions, commitments, or uses.

Glossary extraction is not definitional reasoning. Naming a concept without
application conditions remains conceptualization. A stipulated definition may
be useful without being empirically true; deductive force applies only to
consequences licensed after the stipulation.

### Entailment and symbolic candidate generation

`entailment_reasoning` records a consequence relation between premises and a
conclusion. `textual_entailment` is its natural-language specialization: it
depends on meaning, stated context, and inspectable background assumptions, not
lexical overlap or a benchmark label alone. It may be computed by an expert,
LLM, classifier, formal semantic pipeline, or hybrid; the mechanism is recorded
separately.

The former `generative_symbolic_reasoning` label is deprecated because it
combined an operation and a realization medium without identifying an
inferential license. Symbolic candidate production is now decomposed into an
operational role such as `hypothesis_formation`, the
`reasoning_realization.symbolic_generative` profile, and an independently
supported archetype such as `abductive` or `inductive`. The former
`equation_conjecture` composite is likewise retained only as a deprecated
compatibility entry.

### Inductive reasoning

Generalizes a pattern, regularity, or expectation from observations or cases.
It does not entail that the conclusion is probable in a numerically calibrated
sense. `InductiveCrossTumorCircuitInference` and
`InductiveDiscoveryPatternFormation` are corpus examples.

### Abductive reasoning

Proposes or ranks hypotheses that could explain an observation, gap, target, or
failure. The output is defeasible and should expose assumptions or discriminating
tests. `AbductiveConceptualHypothesisFormation` is both abductive and conceptual.

### Similarity-based and analogical reasoning

`similarity_based` reasoning uses an explicit resemblance, distance,
neighborhood, exemplar, or prototype relation as part of the warrant for a
classification, ranking, prediction, relevance judgment, or candidate
conclusion. Its initial subtypes are:

- `exemplar_based`: particular retained cases license the target conclusion;
- `prototype_based`: proximity to an abstract or learned prototype licenses
  membership or expectation.

Merely computing cosine similarity, feature overlap, or a nearest neighbor is
`similarity_measurement`. It becomes reasoning only when the similarity result
licenses an epistemic commitment.

`analogical` reasoning instead transfers a relation, constraint, expectation,
explanation, or candidate solution through a structured source-target
correspondence. `structural_analogy` makes this explicit by mapping objects,
roles, and higher-order relations. Shared attributes can help propose a mapping,
but feature resemblance alone does not license the analogical transfer.

`AnalogicalConceptualBridgeRevision`, `AnalogicalConceptualBridgeTransfer`,
`AnalogicalGraphTransportAssessment`, and `AnalogicalCrossTumorConcordance` are
the active corpus anchors. They remain mapped to the broad `analogical` taxon;
the more specific subtype is provisional pending a focused mapping audit.

### Causal and mechanistic reasoning

`causal_reasoning` is the umbrella for causal queries with explicit assumptions:

- `causal_discovery`: learns candidate causal structure while retaining
  equivalence classes and discovery assumptions;
- `causal_identification`: establishes whether and how a causal estimand is
  recoverable from available distributions;
- `causal_effect_estimation`: numerically estimates an identified causal effect;
- `interventional_reasoning`: distinguishes setting a variable from observing it;
- `counterfactual_reasoning`: relates factual evidence to a contrary intervention
  for the same unit or context;
- `mediation_reasoning`: decomposes effects through specified pathways;
- `causal_transportability`: establishes how causal claims transfer across
  populations or environments.

`mechanistic_reasoning` explains behavior through organized entities,
activities, productive relations, and conditions over time or levels. It can
co-occur with causal inference, but a mechanism description and an identified
causal effect are not interchangeable.

The former `causal_mechanistic` label is deprecated. Existing cases have been
reclassified as `causal_reasoning`, `mechanistic_reasoning`, both, or neither.
In particular, a biological scope-setting step is not mechanistic reasoning;
it must itself reason through an explicit productive organization.

A graph is not automatically causal, and a biological topic is not automatically
mechanistic. `ModelBasedCrossTumorCircuitConstruction` is a candidate only to
the extent that its authored relation model specifies productive mechanisms.

### Model-based reasoning

Constructs, executes, or interrogates an explicit model to obtain implications,
diagnoses, or rankings. Co-label with causal, mechanistic, deductive, or
probabilistic reasoning when the model warrants those more specific labels.
`ModelBasedDiscoveryHypothesisProbe` and
`ModelBasedResistanceTargetRanking` are direct corpus examples.

### Probabilistic or statistical reasoning

- `probabilistic`: combines or propagates explicit probabilities, likelihoods,
  distributions, or probabilistic graphical relations.
- `statistical`: estimates or tests population or process properties from data
  with an explicit statistical procedure.

Terms such as "uncertainty," "calibration," "rank," or "evidence-based" are not
enough. The present corpus has many qualitative uncertainty assessments but no
occurrence should receive these labels without authored quantitative semantics.

The extended uncertainty branch distinguishes:

- `bayesian_inference`: prior-likelihood-posterior updating;
- `frequentist_inference`: estimation or testing with repeated-sampling
  semantics;
- `uncertainty_quantification`: characterization of uncertainty in inputs,
  parameters, models, computations, or predictions;
- `uncertainty_propagation`: transmission of represented uncertainties to
  output quantities;
- `uncertainty_calibration`: quantitative checking or adjustment of stated
  uncertainty levels;
- `sensitivity_analysis`: attribution of output changes to varied assumptions,
  inputs, or parameters;
- `imprecise_uncertainty_reasoning`: interval, lower/upper probability,
  possibility, or fuzzy calculi.

Aleatoric, epistemic, measurement, sampling, parameter, model_form, and
numerical uncertainty are sources, not inference types. Probability
distributions, confidence intervals, credible intervals, prediction intervals,
bounds, fuzzy memberships, and ensembles are representations, not sources.

### Argumentative, defeasible, and dialectical reasoning

`argumentative_reasoning` changes the acceptability of a claim by exposing
premises, warrants, burdens, defeaters, or competing arguments. Its canonical
subtypes include:

- `scheme_based_argumentation`: applies a named argumentation scheme with role
  bindings and critical questions;
- `defeasible_reasoning`: licenses a retractable conclusion under stated
  exception or defeat conditions;
- `dialectical_reasoning`: computes or judges acceptability through structured
  attacks, supports, replies, and burdens;
- `practical_argumentation`: supports an action through goals, consequences,
  alternatives, values, costs, or risks;
- `implicit_premise_reconstruction`: infers a missing premise or warrant while
  keeping it distinct from source-stated commitments;
- `definitional_commitment_reconstruction`: infers the term-use commitment an
  argument presupposes and exposes consequential alternative definitions.

Argument construction is still a discourse function. Assumption or definition
elicitation is still an operational role when it only surfaces information.
The reasoning label applies when reconstruction or evaluation changes which
conclusions are licensed.

### Contrastive reasoning

Compares alternatives to identify what would discriminate them or why one
outcome occurred rather than another. `ContrastiveDiscoveryHypothesisProbe` is
the clearest present example.

### Refutational reasoning

Searches for defeaters, counterexamples, contradictions, invalid transfers, or
failed predictions. Non-refutation must not be reclassified as proof.
`RefutationalSolverCoherenceReview` and the catalog's proof-route assessments
instantiate this family.

### Evidential assessment and evidence handling

`evidential_assessment` integrates admitted support, counterevidence, criteria,
and limitations to revise the support status or permissible commitment of a
target claim. It requires an explicit evidence-to-claim relation and an
epistemic result.

The former broad `evidential` archetype is deprecated because it conflated four
independent questions:

- `evidence_admission`, `boundary_setting`, and `grounding` are operational
  roles that prepare or constrain evidence;
- `empirical_evidential` is a warrant basis;
- `evidential_assessment` is a reasoning archetype only when evidence changes
  the support status of a target claim;
- `readiness_gating`, `routing_or_gating`, and `decision` control workflow
  action and do not become reasoning archetypes merely because evidence informs
  them.

This distinction removed reasoning labels from evidence-bounding and routing
steps while retaining them for nine support or claim-status assessments in the
current mapping.

### Conceptual reasoning

Conceptual reasoning changes or evaluates the representational scheme through
which a problem is understood: its categories, distinctions, relations,
interfaces, or explanatory vocabulary. It is not a synonym for open_ended
natural-language work.

Its subclasses are:

- `conceptualization`: creates an explicit concept, schema, or representational
  frame from less organized material;
- `concept_creation`: constructs a reusable conceptual unit with stated
  intension, extension, identity conditions, role, or discriminating use;
- `abstractive_generalization`: retains invariant or relevant structure across
  cases in a higher-level concept or schema while suppressing case-specific
  detail;
- `conceptual_gap_detection`: identifies a missing distinction, mediator,
  definition, interface, or incompatible commitment;
- `conceptual_differentiation`: separates notions that were conflated or makes
  discriminating dimensions explicit;
- `conceptual_integration`: connects concepts or domains through a bridge,
  mapping, or unifying representation;
- `concept_unification`: builds a coherent concept or superordinate schema that
  subsumes, reconciles, or jointly explains prior concepts while preserving
  their mappings and residual differences;
- `conceptual_revision`: repairs or refines the conceptual scheme while tracking
  preserved and rejected commitments;
- `conceptual_evaluation`: assesses coherence, adequacy, scope, or consequences
  of a conceptual scheme.

These are subclasses of conceptual reasoning and may be co-labeled with another
archetype. Thus `AbductiveConceptualHypothesisFormation` is `abductive` plus
`conceptualization`; `AnalogicalConceptualBridgeRevision` is `analogical`,
`conceptual_integration`, and `conceptual_revision`; and a formal consequence of
a conceptual bridge may be both `formal_deductive` and
`conceptual_evaluation`.

Concept creation is narrower than conceptualization: the latter may produce an
entire frame or schema. Concept unification is narrower than conceptual
integration: integration can connect concepts without merging them under a
common conceptual unit. Abstractive generalization is not summarization or
clustering; it constructs a reusable abstraction and may be co-labeled
`inductive` when observations license generalization beyond the source cases.

### Diagnostic reasoning

Infers fault, condition, or explanatory localization from observations, then
identifies discriminating probes or repairs. It may combine abductive,
contrastive, causal, or model_based reasoning. `DiagnoseAndPlanDebugProbes` is a
candidate; its planning behavior remains a separate operational role.

## Facet 4: discourse organization

These labels describe the form imposed on communicative content, independently
of whether the content was inferred:

- `projection` presents a bounded view with declared omissions;
- `classification` organizes content under named categories;
- `decomposition` divides a whole into intelligible parts;
- `ordering_sequencing` arranges material temporally, procedurally, or
  rhetorically;
- `selection_curation` chooses discourse units for inclusion or emphasis;
- `argument_construction` and `explanation_construction` organize their
  respective inferential artifacts for communication;
- `synthesis_or_construction` integrates several sources or perspectives;
- `critique_counterargument` organizes objections, failure modes, or rebuttal;
- `summary_compression` produces a shorter account under a preservation
  contract;
- `presentation` and `finalization` package conclusions, limitations, and
  provenance for an audience or handoff;
- `claim_or_hypothesis_formation` articulates a scoped claim or hypothesis;
- `specification_instruction` and `planning_or_recommendation` organize work
  that another actor can execute;
- `routing_or_gating` communicates a disposition and its basis; and
- `refinement` revises an existing account while tracking commitments.

Do not apply a discourse label merely because a Prism value is serialized as
text. The occurrence must intentionally organize a communicative artifact.

## Facet 5: warrant basis

These labels are independent and may co-occur.

- `formal`: warrant depends on syntax, explicit rules, formal semantics, proof,
  or constraint satisfaction.
- `material`: warrant depends on domain content, meanings, empirical regularities,
  or substantive relations that are not licensed by form alone.
- `computational`: warrant depends on executing a specified algorithm, solver,
  simulation, search, or numerical procedure and retaining its operational
  conditions.
- `empirical_evidential`: warrant depends on observations, measurements, source
  records, or an explicitly bounded evidence base.
- `pragmatic`: warrant for a choice depends on goals, costs, risks, resources,
  or action consequences.
- `testimonial_authoritative`: warrant depends on an identified authority or
  source testimony.
- `none_transfer_only`: the occurrence is intended only to carry, reshape, or
  publish information and introduces no new warrant.

"Computational" does not mean "performed by software or an LLM." It applies only
when execution of a specified computation contributes to the result's warrant.
Likewise, a formal schema does not make a content-dependent inference formal.

## Facet group 6: computational procedure and topology

Version 0.6 decomposes the old `computational_character` field because labels
such as “structured judgment” mixed constraints, determinacy, procedure, and
human involvement. That field remains as a deprecated compatibility column for
the current CSV; new annotations use the independent facets below.

### `constraint_regime`

Use at most one of `formally_specified`, `schema_constrained`,
`criteria_constrained`, `open_ended`, or `unknown`. This facet states how
completely admissible outputs are constrained, not whether one execution is
deterministic.

### `execution_determinacy`

Use at most one of `deterministic`, `stochastic`, `underdetermined`, `mixed`, or
`unknown`. Typed input/output, a deductive method name, a clear workflow, or a
low temperature setting is insufficient to establish determinism. A complete
operative procedure and relevant environment are required.

### `procedure_family`

Multi-label from `rule_application`, `constraint_solving`, `search`,
`optimization`, `simulation`, `statistical_estimation`, `graph_operation`,
`generative_model`, `human_judgment`, `data_transformation`,
`external_retrieval`, and `unspecified`. Procedure describes execution, not
what epistemically licenses the result.

### `statefulness`

Use at most one of `stateless`, `stateful`, or `unknown`, based on whether
retained history or mutable state beyond the explicit current input affects the
result.

### `workflow_topology`

At workflow or subgraph level, multi-label from `sequential`, `parallel`,
`convergent`, `divergent`, `iterative`, and `feedback_controlled`. These labels
come from authored graph relations. They describe composition and control, not
the reasoning type of each contained occurrence.

## Facet 7: knowledge-representation paradigm

This facet records how knowledge is encoded. It is orthogonal to inference:
a Prolog program may be stored but never executed; a natural-language argument
may be deductively valid; an LLM may translate between two paradigms without
establishing either representation's truth.

The logical branch is:

```text
logical
├── propositional_logic
├── first_order_logic
├── higher_order_logic
├── logic_programming
│   ├── prolog_horn_clause
│   ├── datalog
│   └── answer_set_programming
├── modal_logic
│   ├── epistemic_doxastic_logic
│   ├── deontic_logic
│   └── temporal_logic
│       ├── linear_temporal_logic
│       └── branching_temporal_logic
├── ontology_description_logic
│   └── temporal_description_logic
├── non_monotonic_logic
│   └── default_logic
├── paraconsistent_logic
├── intuitionistic_constructive_logic
└── probabilistic_logic
```

Key boundaries:

- First-order logic quantifies over individuals; higher-order logic also
  quantifies over predicates, functions, propositions, relations, or types.
- Prolog represents Horn-style facts and rules with unification and
  goal-directed resolution. Datalog restricts the language for finite
  relational/fixpoint evaluation. Answer-set programming instead uses stable
  model semantics for defaults, constraints, and alternative models.
- Modal logic adds operators over accessible worlds or states. Epistemic,
  doxastic, and deontic logics specialize knowledge, belief, and norms;
  temporal logics specialize paths, traces, and state transitions.
- Description logics represent classes, individuals, properties, and ontology
  axioms. Temporal description logics require both ontology semantics and
  temporal qualification; a date-valued property is insufficient.
- Non-monotonic logics permit conclusions to be retracted by added information.
  Paraconsistent logics instead tolerate contradiction without unrestricted
  explosion. These solve different problems.

The wider KR facet also includes `rule_based`, `frame_slot`,
`semantic_network`, `knowledge_graph`, `algebraic_equational`,
`constraint_based`, `probabilistic_graphical`, `fuzzy_possibilistic`,
`temporal_event`, `case_based`, `vector_distributed`, `neural_implicit`,
`executable_program`, and `hybrid_neuro_symbolic` paradigms. Multi-label them
when the interface is explicit—for example, a temporal ontology can be both
`ontology_description_logic` and `temporal_event`.

### Graph-based knowledge representation

`graph_based` is an umbrella for representations whose typed nodes, edges, and
graph structure carry knowledge semantics. Graph shape alone is insufficient:
a directed edge can mean proof dependence, support, attack, causation,
production, temporal transition, provenance, or process flow, and these meanings
must not be interchanged.

```text
graph_based
├── semantic_network
│   ├── knowledge_graph
│   └── conceptual_graph
├── proposition_graph
│   └── proof_dependency_graph
├── argumentation_graph
│   ├── abstract_argumentation_framework
│   ├── bipolar_argumentation_graph
│   ├── structured_argument_graph
│   └── evidence_claim_graph
├── causal_graph
├── mechanistic_graph
├── provenance_graph
├── temporal_transition_graph
├── process_workflow_graph
└── probabilistic_graphical
    ├── bayesian_network
    ├── markov_random_field
    └── factor_graph
```

The principal boundaries are:

- A `proposition_graph` connects proposition-level contents through entailment,
  contradiction, equivalence, compatibility, or dependency. A
  `proof_dependency_graph` adds formal premises, lemmas, obligations, inference
  steps, and proof/certificate references.
- An `argumentation_graph` represents dialectical or justificatory roles:
  support, attack, rebuttal, undercut, burdens, schemes, and replies. Abstract
  frameworks treat arguments as opaque nodes; structured argument graphs expose
  premises, conclusions, rules, assumptions, and defeaters. An
  `evidence_claim_graph` specializes the latter for evidence, counterevidence,
  provenance, scope, and limitations.
- A `causal_graph` requires intervention-sensitive causal semantics and stated
  structural assumptions. Direction, temporal precedence, correlation, or data
  flow alone does not make an edge causal.
- A `mechanistic_graph` represents entities, activities, organization,
  conditions, and productive relations. It may complement a causal graph but
  adds constitutive detail that a variable-level causal edge need not contain.
- A `conceptual_graph` connects concepts and conceptual relations. A
  `knowledge_graph` primarily makes entity-level typed assertions, while a
  `semantic_network` is the broader typed semantic_network family.
- A `provenance_graph` traces entities, activities, agents, attribution, and
  derivation. A `temporal_transition_graph` constrains states, events, and
  transitions. A `process_workflow_graph` represents control/data flow,
  branches, joins, iteration, and feedback; workflow connectivity is not
  automatically inference, argumentation, causality, or mechanism.
- Probabilistic graphical models require probability factorization semantics.
  Bayesian networks, Markov random fields, and factor graphs differ in directed,
  undirected, and bipartite variable-factor structure. A Bayesian network is not
  automatically a causal graph.

Current corpus candidates include `ModelBasedContextualGraphConstruction` for
causal or mechanistic graph representation, the conceptual-bridge workflows for
conceptual graphs, the proof-route workflows for proposition/proof-dependency
graphs, and the Prism diagrams themselves for process-workflow graphs. Their
present contracts do not expose enough graph semantics to populate this facet
automatically, so all graph taxa remain provisional and the maintained mapping
is unchanged.

## Facet 8: computational mechanism

Mechanism describes realization, never validity or epistemic warrant:

- `llm_generation` and `llm_constrained_generation`;
- `neural_discriminative` scoring or classification;
- `symbolic_rule_derivation` and `equational_rewriting`;
- `formal_solver` for theorem provers, model checkers, SAT/SMT, constraints,
  or computer algebra under explicit semantics;
- `argumentation_engine` for attack/support, dialogue, burden, or extension
  semantics;
- `hybrid_generate_then_verify` when candidate generation and independent
  checking are both authored.

Thus “LLM-based deduction” is annotated as a deductive target plus an LLM
mechanism, with `unknown` epistemic force until premises, rules, and a check
support a stronger claim. LLM-based equation generation is normally
an equation candidate operation; verified equational consequences are
separately `equational_inference`.

## Facet 9: epistemic force

Use at most one: `no_commitment`, `necessary`, `defeasible`, `probabilistic`,
`statistical`, `pragmatic_recommendation`, or `unknown`. Force states what the
component claims for its output, not whether the implementation is reliable.
A generated candidate normally has `no_commitment`; a checked formal
consequence may have `necessary`; a scheme-based argument normally has
`defeasible`.

## Facets 10–11: uncertainty source and representation

Record uncertainty sources independently from their representation and from
the procedure acting on them.

- Source: `aleatoric`, `epistemic`, `measurement`, `sampling`, `parameter`,
  `model_form`, or `numerical`.
- Representation: `probability_distribution`, `posterior_distribution`,
  `confidence_interval`, `credible_interval`, `prediction_interval`,
  `deterministic_bounds`, `imprecise_probability`, `fuzzy_membership`,
  `ensemble`, or `qualitative`.

For example, parameter uncertainty may have a posterior distribution or
deterministic bounds; aleatoric outcome uncertainty may have a prediction
interval. A confidence interval is not a Bayesian credible interval, even when
their numerical endpoints coincide.

## Facets 12–13: epistemic object type and role

Epistemic object type records what reasoning consumes, constructs, evaluates,
or emits. It is independent of the method applied to the object. Object role
records how that typed object participates in one occurrence:

- `focal_target`: the principal object reasoned about or transformed;
- `premise_or_input`: supplied content used by the reasoning;
- `context`: conditions fixing interpretation or applicability;
- `constraint_or_criterion`: admissibility restriction or evaluation standard;
- `evidence_or_warrant`: explicit support for another object;
- `candidate`: proposed but not yet accepted content;
- `conclusion_or_output`: the principal emitted result;
- `defeater_or_counterevidence`: an explicit challenge or limiting case;
- `action_or_intervention`: an operation whose consequences or choice matter;
- `certificate_or_trace`: auditable derivation, verification, or provenance.

The same typed object can change roles across a workflow. A hypothesis can be a
candidate when formed, a focal target when pressure-tested, and a premise when
used to derive a prediction.

### Formal and claim-bearing objects

```text
proposition
├── theorem
├── lemma
├── claim_object
│   ├── hypothesis
│   ├── prediction
│   ├── causal_claim
│   ├── counterfactual_claim
│   └── normative_claim
└── assumption

definition_object

formal_symbolic_object
├── logical_formula
├── mathematical_expression
│   ├── equation
│   ├── inequality_or_bound
│   └── invariant
├── constraint
├── type_judgment
└── proof_obligation
```

A proposition is truth-evaluable content; a claim adds assertion, proposal, or
evaluation status. A definition is separate because a stipulation can fix use
without being a truth-evaluable claim. A theorem is a proposition designated as
established or as a target for establishment within a formal theory. A proof is
a separate inferential artifact. Likewise, an equation is a typed mathematical
object; equational reasoning is a method applied to it.

### Inferential and evidential artifacts

```text
inferential_artifact
├── derivation
├── proof
├── proof_certificate
├── argument
│   ├── argument_scheme_instance
│   └── counterargument
├── explanation
│   ├── causal_explanation
│   └── mechanistic_explanation
└── counterexample

evidence_object
├── evidence_item
├── evidence_bundle
├── observation_or_measurement
└── provenance_record

evaluation_decision_object
├── evidence_strength
│   └── support_assessment
├── evaluation_criterion
├── verdict
├── epistemic_status
├── ranking
├── plan_or_recommendation
└── route_or_disposition
```

`evidence_strength` is an assessment object relating evidence to a target claim;
it is not raw evidence and not an uncalibrated confidence score. Arguments and
proofs are also distinct: arguments can be defeasible, materially warranted,
and dialectically attacked, whereas proofs purport to establish a theorem under
a formal system.

### Context, causal, model, discourse, and decision objects

- Context objects: `scoping_context`, `boundary_condition`, `assumption_set`,
  `interpretation_context`, `domain_context`, `population_context`, and
  `temporal_context`. `ScopingContext` means the explicit conditions under which
  a statement, model, inference, or result is intended to hold—not just a topic
  label or execution configuration.
- Causal objects: `intervention`, `causal_query`, `causal_estimand`,
  `counterfactual_scenario`, and `mediator_or_pathway`.
- Model objects: `conceptual_model`, `formal_model`, `causal_model`,
  `probabilistic_or_statistical_model`, `simulation_model`, and
  `mechanistic_model`. A `mechanism` is the organized target system; a
  `mechanistic_model` is its representation.
- Discourse objects: `discourse_unit`, `discourse_relation`,
  `rhetorical_relation`, and `dialogue_move`. Discourse relations organize
  communication; they are not automatically causal, logical, or argumentative
  relations outside that discourse.
- Evaluation and decision objects: `evidence_strength`, `support_assessment`,
  `evaluation_criterion`, `verdict`, `epistemic_status`, `ranking`,
  `plan_or_recommendation`, and `route_or_disposition`.

Corpus anchors include `ExplicitPremises → ExactTheoremClaim`,
`BoundedEvidence → CandidateClaim`, `DomainScopeGrounding`,
`ContextualCandidateExplanation`, `CrossTumorCircuitModel`, the proof-route
assessment objects, and the many calibrated claim-status and routing objects.
These anchors support the object vocabulary, but the new facet remains
unpopulated until a row-level input/target/output-role audit is performed.

## Facet 14: reasoning realization

Reasoning realization is a compatibility profile describing how reasoning or
candidate formation is carried out. Each taxon declares one of five axes:
`candidate_production`, `representation_medium`, `formality`, `executor`, or
`integration`. It does not say what inference is attempted, whether it is
valid, or what licenses acceptance.

```text
generative
├── llm_generative
│   ├── unconstrained_llm_generative
│   ├── constrained_llm_generative
│   ├── retrieval_augmented_llm_generative
│   └── tool_augmented_llm_generative
├── neural_generative
├── symbolic_generative
│   └── program_synthesis_generative
└── hybrid_generative

symbolic
├── formal_symbolic
├── semi_formal_symbolic
├── informal_symbolic
├── computational_symbolic
├── human_symbolic
└── hybrid_symbolic
```

Additional realization families are `natural_language_deliberative`,
`numerical_computational`, `diagrammatic_spatial`, and
`hybrid_neuro_symbolic`.

These labels are intentionally multi-label across axes. A theorem prover can be
`symbolic` (medium), `formal_symbolic` (formality), and
`computational_symbolic` (executor); a domain expert can combine `symbolic`,
`semi_formal_symbolic`, and `human_symbolic`; an LLM proposing equations can
combine `generative`, `llm_generative`, `symbolic_generative`, and `symbolic`,
followed by a separately recorded formal solver or verification step.

“Non-formal symbolic” is divided into `semi_formal_symbolic`, where schemas or
notations constrain interpretation, and `informal_symbolic`, where domain
practice supplies most of the meaning. `computational_symbolic` is not a third
formality level: it can co-occur with formal, semi-formal, or hybrid symbolic
work.

## Multi-label and precedence policy

1. Assign one primary functional family based on the intended product.
2. Add every operational role directly supported by the occurrence.
3. Add a reasoning archetype only if a new or revised epistemic commitment is
   part of the contract.
4. Store the most specific supported subtype. Derive broader index entries by
   following `parent`; do not duplicate every ancestor in the mapping.
5. Co-label genuinely independent moves. An abductively proposed mechanistic
   explanation may be `abductive`, `mechanistic_reasoning`, and
   `explanation_construction`.
6. Do not turn pipeline position into semantics. An operation before a reasoner
   is not necessarily retrieval; an operation after a reasoner is not
   necessarily validation.
7. For compound occurrences, annotate all demonstrated roles and name the
   dominant one. If different success criteria cannot be separated, mark the
   occurrence `compound` and recommend later decomposition.
8. Never infer probabilistic, deterministic, formal, causal, or mechanistic
   semantics solely from suggestive naming.

## Classification procedure

For each occurrence:

1. Read its input and output types, invocation, relation/certificate,
   commentary, sample output, and bound skill description.
2. Write a one-sentence function: “Given X, this component does Y so that Z.”
3. Apply the **commitment-change test**: does the output introduce or revise a
   claim/status/explanation, or only locate, select, reshape, control, organize,
   or publish content?
4. Select the primary family and operational roles.
5. If it changes epistemic commitment, apply each archetype's inclusion and
   exclusion test.
6. Apply discourse labels only when communicative organization is an intended
   output property.
7. Record object types and distinguish focal target, inputs, context, criteria,
   evidence, candidate, output, defeaters, interventions, and certificates.
8. Record warrant bases, realization style, and each computational subfacet
   independently.
9. Attach evidence and confidence. Explicitly record labels considered but not
   supported when the distinction is important.

## Evidence and confidence

Every annotation should contain at least one source locator and a short evidence
statement. Evidence priority is:

1. explicit formal definition, relation, certificate, or executable procedure;
2. occurrence commentary and declared input/output semantics;
3. materialization/skill role and authored example;
4. method or field name;
5. workflow position or domain expectation.

Confidence levels:

- `high`: an explicit definition/procedure plus corroborating contract or
  example supports the label and no source conflicts;
- `medium_high`: multiple authored cues support the label with limited residual
  ambiguity;
- `medium`: two independent authored cues support the label, but operational
  semantics remain partly implicit;
- `low`: only naming, example interpretation, or workflow position supports it;
- `abstain`: evidence is absent, contradictory, or too coarse. Use `unknown` in
  computational subfacets.

Names such as `Evidential...`, `Deductive...`, or `Extract...` are hypotheses,
not ground truth. A future annotation process should flag disagreement between
the name and the implemented function.

## Corpus-grounded seed classifications

These examples demonstrate the model; they are not yet a complete annotation of
all occurrences.

| Occurrence | Primary family | Supported facets | Initial confidence |
| --- | --- | --- | --- |
| `EvidentialEvidenceBounding` | information and evidence operation | `boundary_setting`; no reasoning archetype; execution unspecified | high |
| `AbductiveConceptualHypothesisFormation` | core reasoning | `abductive`; `hypothesis_formation`; `claim_or_hypothesis_formation` | medium |
| `AnalogicalConceptualBridgeRevision` | core reasoning | `analogical`; `analogy_or_transport` | high |
| `DeductiveExactTheoremClaimDerivation` | core reasoning | `deductive`; `derivation`; determinacy not established | high |
| `InductiveCrossTumorCircuitInference` | core reasoning | `inductive`; `pattern_inference` | high |
| `ModelBasedResistanceTargetRanking` | core reasoning | `model_based`, `mechanistic_reasoning`; `selection_or_ranking` | high |
| `RefutationalSolverCoherenceReview` | evaluation and judgment | refutational, assessment_or_critique; formal and computational warrant if solver semantics are retained | high |
| `FrameworkWorkflowDecompositionSynthesis` | discourse and artifact organization | `decomposition`, `synthesis_or_construction` in both operation and discourse facets | medium-high |
| `ExtractSvaSemanticModel` | information and evidence operation | `extraction`; heuristic structured transformation in the legacy field | high |
| `RepresentAndDetectDebugFindings` | information and evidence operation (compound) | `synthesis_or_construction`, `detection`; no reasoning archetype | medium-high |
| `DiagnoseAndPlanDebugProbes` | core reasoning | `diagnostic`, `mechanistic_reasoning`; `diagnostic_analysis`, `planning_or_recommendation` | medium-high |
| `FinalizeVerificationPackage` | discourse and artifact organization | `finalization` in operation and discourse facets; no new warrant inferred | high |

Representative sources include:

- `catalog/abducer-prism/workflows/conceptual_frontier_deepening/occurrences.prism`
- `catalog/abducer-prism/workflows/theorem_proof_delivery/occurrences.prism`
- `catalog/oncology-agents/general/bounded_ebr/occurrences.prism`
- `catalog/oncology-agents/specific/cross_tumor/occurrences.prism`
- `catalog/oncology-agents/specific/melanoma_resistance/occurrences.prism`
- `catalog/spectra/sva_generator/occurrences.prism`
- `catalog/spectra/verification_debug_diagnosis/occurrences.prism`

## Known limitations and extension points

- The seed corpus is authored and curated, not an unbiased sample of reasoning.
  Its method names already encode a preferred vocabulary, which can create
  circular classifications.
- Many occurrences specify typed boundaries and commentary but not an executable
  algorithm. Determinism, formal validity, and computational warrant will often
  remain unknown.
- The catalog emphasizes qualitative epistemic calibration. It currently offers
  weak evidence for probabilistic, statistical, numerical, optimization, and
  simulation subclasses; these should remain in the taxonomy as hypotheses to
  test against future workflows, not labels to force onto present cases.
- Compound operations in Hardware Verification combine extraction,
  interpretation, generation, validation, and publication. Later versions may
  decompose these into finer occurrences rather than multiplying labels.
- Material and formal warrant can interact. A formally valid derivation can
  still rely on materially justified premises; annotations should record both.
- Discourse organization is underdescribed in occurrence contracts. Sample
  outputs and presentation requirements are needed before assigning fine-grained
  rhetoric labels confidently.
- Retrieval is rare or implicit in the current corpus. A skill description that
  mentions a knowledge base is not proof that an occurrence executed retrieval.
- Workflow-level feedback, convergence, and parallelism require graph analysis
  and should not be projected onto each contained occurrence.
- The canonical logical KR branch is substantially broader than the current
  corpus. Spatial, commonsense, social, and metacognitive representation and
  reasoning still require additional boundary work.

## Change log

### Version 0.6

- Completed a corpus-backed structural and mapping audit over all 152
  occurrences and documented the findings in `audit-report.md`.
- Standardized canonical identifiers as `lower_snake_case` and made facet
  cardinality, annotation level, mapping status, taxon status, and replacement
  policy machine-checkable.
- Replaced the broad `evidential` mapping with `evidential_assessment` only for
  evidence-to-claim status inferences; evidence bounding, grounding, readiness,
  and routing retain their operational or control roles without a reasoning
  archetype.
- Deprecated the composite `causal_mechanistic` and
  `generative_symbolic_reasoning` labels in favor of independent specific
  facets.
- Split the conceptual computational-character model into
  `constraint_regime`, `execution_determinacy`, `procedure_family`, and
  `statefulness`, and added workflow-level `workflow_topology`. The old CSV
  field remains as a compatibility field during migration.
- Corrected object hierarchy category errors: propositions may be formal or
  informal; evidence strength is an assessment object; mechanisms are targets
  distinct from mechanistic models; and proof certificates need not be full
  proofs.
- Removed unsupported deterministic classifications inferred from words such as
  “Deductive,” “Projection,” or “Finalize,” and added validator regressions for
  these exclusions.

### Version 0.5

- Added epistemic-object types for equations, propositions, theorems, claims,
  proofs, arguments, explanations, evidence strength, scoping contexts,
  interventions, mechanisms, discourse relations, models, and decision objects.
- Added object-role labels so focal targets, premises, contexts, criteria,
  evidence, candidates, conclusions, defeaters, interventions, and certificates
  can be distinguished within an occurrence.
- Added a reasoning_realization facet with generative, LLM-generative, neural,
  symbolic_generative, formal/semi-formal/informal symbolic, computational and
  human symbolic, numerical, natural-language, diagrammatic, and neuro-symbolic
  branches.
- Kept object type, reasoning archetype, KR paradigm, realization, mechanism,
  warrant, and epistemic force orthogonal; no existing row mappings were
  inferred from type names alone.

### Version 0.4

- Added a graph_based KR family with proposition, proof-dependency,
  argumentation, evidence-claim, causal, mechanistic, conceptual, provenance,
  temporal-transition, process-workflow, and probabilistic graph paradigms.
- Added abstract, bipolar, and structured argumentation graph subtypes.
- Added Bayesian-network, Markov-random-field, and factor_graph subtypes while
  explicitly separating probabilistic and causal semantics.
- Preserved current component mappings because graph topology or naming alone
  does not establish the required node and edge semantics.

### Version 0.3

- Added similarity_based reasoning with exemplar- and prototype_based subtypes,
  while separating similarity measurement from epistemic inference.
- Refined analogical reasoning and added structural analogy, preserving the
  distinction between feature resemblance and relation-preserving transfer.
- Added concept creation, concept unification, and abstractive generalization
  as specific conceptual-reasoning categories.
- Preserved existing occurrence mappings; the new fine-grained taxa remain
  provisional until directly supported by audited workflow contracts.

### Version 0.2

- Added definitional reasoning with formation, application, and revision.
- Added formal logical, equational, type-theoretic, constraint_entailment, and
  theorem_proving branches, plus generative symbolic conjecture.
- Added autoformalization, formal validation, and symbolic manipulation as
  non-inferential or evaluative operations rather than automatic deduction.
- Added textual entailment, argumentative, scheme-based, defeasible,
  dialectical, practical, implicit-premise, and definitional-commitment
  reasoning.
- Added assumption and definition elicitation as foundational argumentative
  operations.
- Expanded causal inference through discovery, identification, estimation,
  intervention, counterfactual, mediation, transportability, and mechanism.
- Expanded uncertainty through Bayesian/frequentist inference, quantification,
  propagation, calibration, sensitivity, sources, and representations.
- Added an independent KR paradigm facet, including Prolog/Horn clauses,
  first- and higher-order logic, modal and temporal logics, description logics,
  non-monotonic and paraconsistent logics, and non-logical KR families.
- Added computational_mechanism and epistemic_force facets so LLM-based,
  symbolic, and hybrid generation do not imply validity or commitment.
- Preserved all 152 corpus mappings; uninstantiated canonical categories remain
  provisional rather than being inferred from names.

### Version 0.1

- Established the corpus-derived functional families, operations, reasoning
  archetypes, discourse functions, warrants, substrate, and computational
  character.

## Revision protocol

Extend the taxonomy from cases, but do not add a class for every method name.
A new class should have at least two plausible instances (or one strategically
important counterexample), a positive inclusion test, a neighboring exclusion
test, and a stated parent. Record versioned changes and retain prior labels so
annotation drift can be audited. Periodically review low-confidence and compound
occurrences first: they are the best evidence that the taxonomy or the workflow
decomposition needs refinement.
