# Argumentative and generative inference proposal

Status: proposed extension for taxonomy review; not yet canonical

## Scope

This proposal extends the Prism component taxonomy with canonical categories
for textual entailment, argumentation, defeasible and dialectical reasoning,
and generative realizations. It is intentionally broader than the current
workflow corpus. A category may be retained as a useful canonical placeholder
even when no current occurrence supports it.

The proposal preserves the taxonomy's faceted design. In particular:

- an **epistemic archetype** says what inferential move is attempted;
- a **discourse function** says how claims and their support are organized;
- an **operational role** says what observable transformation is performed;
- a **warrant basis** says what licenses acceptance of the result;
- a **computational mechanism** says how a candidate was produced or checked;
- an **epistemic force** says what strength is claimed for the conclusion.

These labels must not substitute for one another. An LLM can verbalize a valid
proof, produce an invalid proof-shaped text, reconstruct a materially strong
argument, or generate candidates without endorsing any of them. Conversely, a
symbolic engine can generate equations without deriving them, and can derive a
formula without expressing it in prose.

Stable IDs below use facet-qualified namespaces. Renaming a display label must
not change its ID. Namespaced references to existing taxa are projections rather
than immediate migrations: for example, `reasoning.deductive` denotes the
current `deductive` taxon, and `operation.extraction` denotes current
`extraction`. The conceptual root `reasoning` has no assignable label of its own.

## Recommended facet addition: epistemic force

The present taxonomy records warrants and computational character, but it has
no direct field for the strength claimed by an inference. Add an orthogonal,
single-valued `epistemic_force` facet. This prevents validity, defeasibility,
probability, and generation mechanism from being collapsed into archetypes.

| Stable ID | Parent | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `force.no_commitment` | — | The output is a candidate, transformation, question, or discourse artifact and makes no claim that its content should be accepted. | Do not use when the contract licenses even provisional acceptance. | active |
| `force.necessary` | — | The conclusion is claimed to follow in every admissible interpretation or execution under explicit premises and rules. | Necessity language, confidence, or an LLM assertion without a semantics is insufficient. | active |
| `force.defeasible` | — | The conclusion is licensed provisionally and can be withdrawn when exceptions, rebuttals, or superior reasons appear. | Do not use merely because an implementation can make mistakes. | active |
| `force.probabilistic` | — | Acceptance strength is expressed by an explicit probability, likelihood, posterior, or probability interval. | Qualitative uncertainty or model confidence alone is insufficient. | provisional |
| `force.statistical` | — | The conclusion has inferential strength defined by a statistical procedure, such as an interval, test, error rate, or estimator. | A descriptive statistic alone is not statistical inferential force. | provisional |
| `force.pragmatic_recommendation` | — | The conclusion recommends action relative to goals, costs, risks, or preferences rather than asserting descriptive truth alone. | Do not apply to an epistemic claim merely used later in a decision. | active |
| `force.unknown` | — | Authored evidence does not establish the claimed inferential strength. | Use a more specific value whenever the contract explicitly supplies it. | active |

Validity is an evaluated relation between premises, rules or semantics, and a
conclusion. It is never inferred from `force.necessary` alone. Record a checked
validity result under an evaluation role and its certificate/provenance, not as
a computational mechanism.

## Reasoning archetypes

### Entailment and deductive inference

| Stable ID | Parent | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `reasoning.entailment_judgment` | `reasoning` | Given explicit premises and an interpretation relation, determines or asserts whether a conclusion is licensed in all relevant models or admissible readings. | Mere semantic similarity, prediction of an entailment label, or plausible continuation is insufficient. | provisional |
| `reasoning.logical_entailment` | `reasoning.entailment_judgment` | Entailment is defined over an explicit formal language and semantics, with a proof, model check, or complete operative decision procedure. Co-label `reasoning.deductive`. | Do not use when premises and conclusion are natural-language strings without a formal interpretation. | provisional |
| `reasoning.textual_entailment` | `reasoning.entailment_judgment` | Determines whether the meaning of a natural-language premise licenses a natural-language hypothesis for the stated context and background assumptions. | Lexical overlap, paraphrase, topic similarity, or an uncalibrated NLI classifier label is not by itself entailment. | provisional |
| `reasoning.material_entailment_judgment` | `reasoning.textual_entailment` | The inference depends on domain meanings, contextual assumptions, or world knowledge that are made inspectable. | If formalization alone fixes the result, use logical entailment; if the relation is only probable, use the appropriate defeasible archetype and force. | provisional |

`reasoning.textual_entailment` names the target semantic relation, not the
mechanism used to judge it. It may be realized by expert judgment, an LLM, a
symbolic semantic parser plus prover, or a hybrid system. For dataset-style
natural-language inference where labels include *neutral* and *contradiction*,
use an operational classification label as well; only the entailed branch is
itself a positive entailment judgment.

### Defeasible and dialectical inference

| Stable ID | Parent | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `reasoning.defeasible` | `reasoning` | Applies a rule, presumption, precedent, or materially supported generalization whose conclusion can be defeated by exceptions or countervailing reasons. | Ordinary uncertainty about a supposedly deductive result is not defeasible reasoning. | provisional |
| `reasoning.default` | `reasoning.defeasible` | Infers a conclusion in the absence of evidence for a named exception or abnormality condition. | A statistical majority pattern without a default rule is inductive, not automatically default reasoning. | provisional |
| `reasoning.presumptive` | `reasoning.defeasible` | Assigns a provisional burden-backed conclusion until an appropriate challenge or defeater is supplied. | Do not use when the conclusion is merely guessed or when no burden/challenge condition exists. | provisional |
| `reasoning.non_monotonic_revision` | `reasoning.defeasible` | Addition of information can retract a previously licensed conclusion under authored revision rules. | Updating prose or changing confidence without a retractable consequence relation is insufficient. | provisional |
| `reasoning.dialectical` | `reasoning.defeasible` | Determines acceptability by relating arguments, counterarguments, attacks, supports, replies, or burdens across positions. | A one-sided critique with no modeled opposition structure is refutational evaluation, not necessarily dialectical reasoning. | provisional |
| `reasoning.argument_acceptability` | `reasoning.dialectical` | Computes or judges which arguments or claims remain acceptable under an explicit attack/support, burden, or dialogue semantics. | Persuasiveness scoring or stylistic quality does not establish acceptability. | provisional |

Defeasible reasoning must use `force.defeasible`. Dialectical organization can
also be a discourse form, but the archetype applies only when the opposition
structure changes which conclusions are licensed.

### Argumentative reasoning and argumentation schemes

| Stable ID | Parent | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `reasoning.argumentative` | `reasoning` | Establishes, challenges, or compares a claim by making premises, warrants, defeaters, burdens, or competing arguments relevant to its acceptability. | A persuasive presentation with no inferential relation is discourse organization only. | provisional |
| `reasoning.scheme_based_argument` | `reasoning.argumentative` | Instantiates a named argumentation scheme with its required roles and associated critical questions or defeat conditions. | A familiar rhetorical pattern without role bindings and challenge conditions is not a scheme instance. | provisional |
| `reasoning.scheme_application` | `reasoning.scheme_based_argument` | Uses a scheme instance to license a defeasible conclusion in the case at hand. | Merely classifying an existing argument by scheme is an operational role, not scheme application. | provisional |
| `reasoning.scheme_critical_questioning` | `reasoning.scheme_based_argument` | Evaluates a scheme instance through its scheme-specific critical questions and records satisfied, open, or defeating answers. | Generic criticism without scheme-specific questions belongs under assessment or refutation. | provisional |
| `reasoning.practical_argumentation` | `reasoning.argumentative` | Supports a proposed action through goals, circumstances, consequences, alternatives, values, or costs. | A causal prediction without an action conclusion is not practical argumentation. | provisional |
| `reasoning.argument_comparison` | `reasoning.argumentative` | Compares competing arguments by explicit priorities, burdens, defeat relations, or warrant strength. | Ranking passages by relevance or rhetorical quality is operational selection, not argumentative reasoning. | provisional |

Do not create one taxon for every named scheme. Represent the scheme itself as
data, for example `scheme_id = expert_opinion`, `causal`, `analogy`,
`practical_reasoning`, or `sign`, while `reasoning.scheme_application` remains
the stable reasoning class. Promote a scheme to a taxon only if repeated corpus
cases need scheme-specific behavior that cannot be expressed by role bindings,
critical questions, warrant, and epistemic force.

## Operational roles

These roles describe argument processing and generation independently of
whether an epistemic conclusion is licensed.

| Stable ID | Parent/current analogue | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `operation.argument_unit_extraction` | `operation.extraction` | Identifies text spans or records functioning as claims, premises, conclusions, objections, or replies and retains source provenance. | Inferring an implicit premise or warrant is not extraction; add reconstruction and appropriate reasoning labels. | provisional |
| `operation.argument_relation_identification` | `operation.detection` | Identifies asserted support, attack, rebuttal, undercut, or reply relations among argument units. | Do not use when a relation is invented to improve the argument. | provisional |
| `operation.argument_reconstruction` | `operation.transformation` | Produces an explicit argument structure from incomplete or implicit discourse while marking supplied versus reconstructed content. | Verbatim extraction alone is not reconstruction; endorsing the reconstructed inference requires a reasoning label. | provisional |
| `operation.scheme_classification` | `operation.classification` | Assigns an argument to a defined argumentation scheme and exposes matched roles. | Classification does not imply that the scheme is correctly applied or sound. | provisional |
| `operation.argument_candidate_generation` | `operation.synthesis_or_construction` | Generates one or more candidate claims, premises, warrants, objections, replies, or complete arguments. | Candidate generation alone does not license acceptance or argumentative validity. | active |
| `operation.counterargument_generation` | `operation.argument_candidate_generation` | Generates an attacking, rebutting, or undercutting candidate against a target argument. | Searching for a true defeater requires refutational or dialectical reasoning in addition. | active |
| `operation.argument_evaluation` | `operation.assessment_or_critique` | Evaluates an argument against explicit criteria such as premise acceptability, relevance, sufficiency, scheme questions, validity, or defeat status. | Style, fluency, and persuasiveness alone are not epistemic argument evaluation. | active |
| `operation.validity_checking` | `operation.validate_or_verify` (recommended new generic parent) | Checks a premise-conclusion relation against an explicit formal semantics or proof calculus and emits a result or certificate. | An LLM verdict, answer match, or plausibility score without a formal check is not validity checking. | provisional |
| `operation.entailment_classification` | `operation.classification` | Assigns an entailment, contradiction, or undetermined/neutral label under a declared task protocol. | The classifier's prediction is not itself evidence that the semantic relation holds. | provisional |

## Discourse organization

Argument construction belongs here whenever the principal achievement is a
well-organized communicative object. It receives a reasoning label only if the
same component also establishes, challenges, or revises epistemic commitment.

| Stable ID | Parent/current analogue | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `discourse.argument_construction` | current `argument_construction` | Organizes claims, grounds, warrants, qualifications, objections, and replies into an intelligible argument. | A bare conclusion or unordered evidence bundle is not argument construction. | active (promote existing provisional taxon) |
| `discourse.argument_reconstruction` | `discourse.argument_construction` | Makes an implicit or fragmented argument explicit while marking reconstructed commitments. | Do not present supplied and reconstructed content as equally sourced. | provisional |
| `discourse.argument_scheme_realization` | `discourse.argument_construction` | Expresses an argument using the roles and critical-question structure of a named scheme. | Scheme classification without communicative realization is operational classification only. | provisional |
| `discourse.dialectical_organization` | `discourse.argument_construction` | Organizes positions, challenges, replies, burdens, and unresolved issues across participants or viewpoints. | A list of pros and cons without relations or dialogue roles is insufficient. | provisional |
| `discourse.counterargument_rebuttal` | current `critique_counterargument` | Constructs an objection, rebuttal, undercut, concession, or reply addressed to a specific target. | A defect label or pass/fail result alone is not a counterargument. | active (rename/clarify existing provisional taxon) |
| `discourse.argument_summary` | `discourse.summary_compression` | Compresses an argument while retaining its main conclusion, support structure, qualifications, and salient objections. | A topical abstract that loses inferential structure is ordinary summary. | provisional |

## Computational mechanisms and generative realizations

The existing `generative-model` procedure family should be decomposed. These
mechanisms may realize any operational role or reasoning archetype; none is a
warrant or validity label.

| Stable ID | Parent | Positive test | Exclusion test | Recommended status |
| --- | --- | --- | --- | --- |
| `mechanism.generative_procedure` | — | The procedure constructs one or more outputs not fixed as copied source units. | Deterministic derivation can produce a novel expression; add the specific mechanism and do not assume stochasticity. | active |
| `mechanism.llm_generation` | `mechanism.generative_procedure` | An autoregressive or equivalent language model generates natural-language or serialized content. | Embeddings, classification heads, retrieval, or symbolic engines are not LLM generation merely because an LLM ecosystem is used. | active |
| `mechanism.llm_constrained_generation` | `mechanism.llm_generation` | LLM output is restricted by a grammar, schema, decoder, verifier, tool protocol, or iterative repair loop. | Prompt instructions alone do not establish hard constraint satisfaction. | provisional |
| `mechanism.llm_self_consistency` | `mechanism.llm_generation` | Multiple generated candidates are sampled and aggregated or selected under an authored consistency procedure. | A single chain-of-thought-like response is not self-consistency, and agreement does not establish truth. | provisional |
| `mechanism.symbolic_expression_generation` | `mechanism.generative_procedure` | A procedure constructs symbolic formulas, equations, rules, proof candidates, or programs. | If every expression follows by a validity-preserving rule, also label the applicable derivation mechanism; generation alone says nothing about correctness. | active |
| `mechanism.symbolic_rule_derivation` | — | Explicit symbolic rules derive consequences, ideally with a trace or certificate. | Symbolic output format alone is insufficient. | active |
| `mechanism.equational_rewriting` | `mechanism.symbolic_rule_derivation` | Applies declared equalities or rewrite rules to transform expressions while preserving the stated semantics. | Guessing an equivalent-looking equation or fitting coefficients is not equational rewriting. | provisional |
| `mechanism.formal_solver` | — | A SAT/SMT, theorem-proving, model-checking, constraint, or algebraic solver computes a result under explicit semantics. | Calling an LLM a solver or checking only syntax does not qualify. | active |
| `mechanism.argumentation_engine` | — | A rule, graph, dialogue, or structured-argument engine computes attacks, supports, extensions, burdens, or acceptability status. | Rendering an argument graph without computing its semantics is representation only. | provisional |
| `mechanism.neural_discriminative_model` | — | A learned model scores or classifies supplied candidates without generatively constructing the principal output. | Do not label autoregressive candidate production as merely discriminative. | provisional |
| `mechanism.hybrid_neuro_symbolic` | — | Neural or LLM generation/interpretation and symbolic checking/derivation are both essential and their interface is explicit. | Post-hoc formatting of an LLM answer as symbols is not a hybrid validity pipeline. | provisional |
| `mechanism.human_deliberation` | — | Human judgment, dialogue, or review is an authored part of producing or accepting the result. | Human availability as a fallback is insufficient. | provisional |

Examples of valid facet compositions:

- An LLM drafts objections: `operation.counterargument_generation` +
  `discourse.counterargument_rebuttal` + `mechanism.llm_generation` +
  `force.no_commitment`. It is not yet refutational reasoning.
- An LLM judges an NLI pair: `operation.entailment_classification` +
  `mechanism.llm_generation` or `mechanism.neural_discriminative_model` +
  `force.unknown`. Add `reasoning.textual_entailment` only if the component's
  contract performs and evidences the semantic judgment, not merely predicts a
  benchmark label.
- A prover checks an LLM-produced proof: `operation.validity_checking` +
  `reasoning.logical_entailment` + `mechanism.formal_solver` + `warrant.formal`
  + `force.necessary`, with the checked result and certificate retained.
- An LLM proposes equations that a CAS later checks: the proposal component is
  `mechanism.llm_generation` + `mechanism.symbolic_expression_generation` +
  `force.no_commitment`; the checker uses `mechanism.equational_rewriting` or
  `mechanism.formal_solver`. Only checked consequences receive formal warrant.
- A structured argumentation engine applies an expert-opinion scheme and tests
  its critical questions: `reasoning.scheme_application` +
  `reasoning.scheme_critical_questioning` + `reasoning.argument_acceptability`
  + `mechanism.argumentation_engine` + `force.defeasible`.

## Warrant alignment

No new warrant category is required for “LLM-based” or “generative.” Apply the
existing warrant facet as follows:

- `warrant.formal`: explicit rules or semantics license the result; retain the
  proof, certificate, solver result, or validity trace.
- `warrant.material`: domain meanings, substantive relations, or background
  knowledge license the inference.
- `warrant.empirical_evidential`: observations or bounded source records license
  the inference.
- `warrant.testimonial_authoritative`: a cited speaker or authority is itself a
  premise under an appropriate scheme; authority is not automatically reliable.
- `warrant.pragmatic`: goals, values, risks, or consequences license an action
  recommendation.
- `warrant.computational`: executing the specified computation under retained
  conditions contributes to warrant. Merely running an LLM is not enough.
- `warrant.none_transfer_only`: generation, reconstruction, or presentation
  introduces no endorsed epistemic commitment.

For argumentation schemes, record the actual warrant basis in addition to the
scheme identifier. “Expert opinion,” for example, normally combines material
and testimonial warrant and remains defeasible; the presence of a scheme does
not manufacture formal validity.

## Current-corpus hypotheses, not assignments

The inspected corpus contains useful review targets but does not yet justify
automatic remapping:

- `DeductiveExactTheoremClaimDerivation` and
  `DeductiveProofRouteConsequenceDerivation` are candidates for logical
  entailment only if their explicit rules, semantics, or proof traces survive
  inspection. Their names and typed contracts establish derivation intent, not
  validity.
- `RefutationalExactTheoremClaimAssessment` and the proof-route refutation
  components are candidates for argument evaluation, counterargument
  generation, or dialectical reasoning only when their outputs expose premises,
  defeaters, attacks, and replies. A counterexample search alone remains the
  existing refutational archetype.
- The discovery and oncology pressure-test components clearly search for
  defeaters, but the authored mappings do not establish a formal argumentation
  framework, scheme semantics, or dialogue protocol.
- Several generated skills explicitly warn against treating candidate text as
  entailment or proof. This supports `force.no_commitment` and separate checking
  stages, but does not by itself identify the underlying generation mechanism
  as an LLM.
- No current occurrence should be assigned an argumentation scheme merely from
  domain phrasing. Scheme roles and critical questions need to be authored or
  recoverable from retained outputs.

## Adoption and corpus recommendations

1. Add `epistemic_force` before annotating entailment or argument acceptability.
   Without it, necessary, defeasible, and no-commitment outputs remain
   dangerously ambiguous.
2. Promote the existing discourse taxon `argument_construction` to active.
   Clarify or migrate `critique_counterargument` to
   `discourse.counterargument_rebuttal`, retaining the old ID as an alias for
   annotation compatibility.
3. Add the active operational generation/evaluation roles now. They are useful
   even when the underlying archetype cannot be established.
4. Keep all new reasoning subtypes provisional until definitions, occurrence
   contracts, or retained certificates support at least one clear corpus case.
5. Treat the computational mechanisms as canonical extension points even when
   corpus implementations are hidden. Annotate `unknown` rather than inferring
   LLM use from prose-like outputs or generative skill names.
6. Do not retrofit current workflow mappings from method names. Candidate
   argument/proof occurrences should be reviewed against relations,
   commentary, examples, skills, and any proof or evaluation artifact.
7. Store scheme IDs, premise/conclusion roles, attack/support relations,
   critical questions, and their answers as instance-level attributes rather
   than proliferating taxonomy classes.

## Minimum annotation evidence

For any new label, retain:

- the target claim or artifact;
- supplied premises/evidence and reconstructed assumptions separately;
- the intended inferential force;
- argument roles and support/attack relations where applicable;
- rules, semantics, scheme ID, critical questions, or evaluation criteria;
- computational mechanism and version, if known;
- output status: proposed, checked, accepted, defeated, unresolved, or rejected;
- a certificate, trace, source locator, or concise evidence statement; and
- confidence plus explicit abstentions.

This evidence makes the central distinction auditable: **generation proposes an
object; reasoning purports to license a commitment; evaluation tests that
license; discourse organization makes the structure communicable.**
