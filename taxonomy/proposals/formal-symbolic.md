# Formal and symbolic reasoning branch proposal

Status: proposed canonical extension; not yet merged into `taxonomy.md` or
`taxonomy.json`

## Scope

This proposal refines the formal and symbolic portion of the Prism taxonomy.
It is intentionally broader than the current workflow corpus: a canonical
taxonomy should represent important formal operations even when no present
occurrence instantiates them. The proposal preserves the taxonomy's faceted
design and avoids treating every operation over symbols as reasoning.

The unit remains one workflow occurrence. Classification should answer four
different questions independently:

1. **Reasoning archetype:** what epistemic move, if any, licenses a new
   conclusion?
2. **Information operation:** what is done to the representation or artifact?
3. **Representational regime:** what kind of objects and semantics are acted
   upon?
4. **Computational realization:** how is the operation carried out, and what
   makes its result reproducible or checkable?

For example, an LLM translating prose into first-order logic is primarily an
autoformalizing transformation. It may use generative inference to resolve an
ambiguity, but it is not thereby formal deduction. A proof checker consuming
the result is formal validation, while a prover deriving a theorem is formal
deduction realized by proof search.

## Proposed annotation tuple

Use a tuple rather than one compound class:

```text
primary_family
reasoning_archetype[]
operational_role[]
representational_regime[]
computational_realization[]
warrant_basis[]
preservation_claim
```

`preservation_claim` is one of:

- `truth_preserving`: every admissible execution preserves truth under the
  declared semantics;
- `satisfiability_preserving`: preserves existence or non-existence of a model,
  but not necessarily equivalence;
- `equivalence_preserving`: preserves denotation, solution set, or logical
  equivalence;
- `type_preserving`: preserves a declared typing judgment;
- `meaning_intended`: intended to preserve material meaning, without a
  mechanically checkable guarantee;
- `candidate_generating`: proposes an object whose correctness requires later
  evaluation;
- `none`: no preservation claim is part of the contract;
- `unknown`: the authored evidence is insufficient.

Truth preservation is a semantic claim, not a synonym for determinism. A
deterministic buggy rewriter may fail to preserve equivalence; a stochastic
proof search may return different proofs whose conclusions are all valid.

## Reasoning archetype hierarchy

“Formal reasoning” is an indexing view across archetype, warrant, representation,
and realization—not a single assignable archetype. Its deductive core is the
existing `formal_deductive` specialization of `deductive`; other formally
represented operations remain in their proper facets. Parent relations are
retained for indexing, and multiple inheritance is intentional.

```text
reasoning
├── deductive
│   ├── informal_deductive
│   └── formal_deductive
│       ├── logical_inference
│       ├── equational_inference
│       ├── type_theoretic_inference
│       ├── constraint_entailment
│       └── theorem_proving
├── definitional_reasoning
└── generative_symbolic_reasoning
    ├── equation_conjecture
    ├── invariant_conjecture
    ├── lemma_conjecture
    └── symbolic_model_construction
```

`definitional_reasoning` may also be deductive when a conclusion follows from
an explicit definition. It remains independently searchable because many
definitional acts introduce, refine, or disambiguate a concept rather than
derive a theorem.

### Formal deductive reasoning (`formal_deductive`)

Derives a conclusion that is intended to follow necessarily under an explicit
formal syntax, semantics, calculus, or proof obligation.

- Include when the operative rules and premises are explicit enough in
  principle for an independent checker to assess the inference.
- Exclude when necessity is asserted only in domain prose; use
  `informal_deductive`.
- Exclude a typed input/output declaration with no inferential rule.
- Exclude merely serializing or normalizing a formal artifact.

Formal deduction requires formal warrant. It may additionally have material
warrant because the premises or interpretation of symbols are domain-laden.

### Definitional reasoning (`definitional_reasoning`)

Introduces, unfolds, applies, compares, or revises explicit definitions to
determine category membership, identity conditions, admissible use, or direct
consequences.

Subtypes:

- `definition_formation`: proposes explicit necessary, sufficient, or
  operational conditions for a term;
- `definition_application`: classifies or derives a consequence by applying an
  existing definition;
- `definition_unfolding`: replaces a defined symbol with its definiens, or the
  reverse, under an explicit definitional equality;
- `definition_comparison`: identifies equivalence, subsumption, incompatibility,
  circularity, or scope differences between definitions;
- `definition_revision`: changes a definition while recording which extension,
  commitments, and uses are preserved or rejected.

Inclusion test: the definition, rather than a merely associated fact, is the
inferential license or principal object being constructed or evaluated.

Exclusions:

- Assigning an item to a class using a learned similarity model is
  classification, not necessarily definitional reasoning.
- Extracting glossary entries is extraction.
- Inventing a useful label without identity or application conditions is
  conceptualization, not yet definition formation.
- A stipulated definition may be generated rather than truth-apt; label its
  formation as conceptual/generative and reserve deduction for consequences
  subsequently licensed by it.

### Logical inference (`logical_inference`)

Applies rules of a stated logic to derive a formula, judgment, contradiction,
model consequence, or non-consequence.

- Include propositional, predicate, modal, temporal, deontic, description,
  non-monotonic, and other logics only when their operative semantics or rules
  are identified.
- Exclude argumentation expressed with premise/conclusion vocabulary when no
  formal calculus is operative; that is argumentative organization and perhaps
  informal deduction.
- Record the logic family as a representational-regime refinement, not as a new
  reasoning archetype for every notation.

### Equational inference (`equational_inference`)

Derives an equality or consequence using explicit equality axioms, equations,
rewrite rules, substitution, congruence, or an equational theory.

- Parent: `formal_deductive`.
- Include when each step is licensed by equality or rewrite semantics.
- Exclude numerical estimation, curve fitting, or merely printing an equation.
- Exclude equation proposal unless the proposed equation is subsequently
  derived or validated.

Useful refinements are `equational_derivation`, `equational_simplification`,
`equational_normalization`, `symbolic_solution`, and
`equational_equivalence_checking`. The latter three often pair with operational
transformation or evaluation roles.

### Type-theoretic inference (`type_theoretic_inference`)

Derives a typing, subtyping, kinding, inhabitation, unification, or type
equivalence judgment under an explicit type system.

- Include type synthesis, type checking with derivation, dependent-type proof,
  and type-directed elaboration when the typing rules license the result.
- Exclude schema validation that checks only field presence or serialization.
- Exclude Prism's typed edges by themselves; types are evidence about
  interfaces, not proof that type-theoretic reasoning occurred.

### Constraint entailment (`constraint_entailment`)

Derives that a proposition is forced, impossible, or conditionally admissible
under an explicit constraint set.

- Include satisfiability/unsatisfiability consequences, implication between
  constraints, and certified bound propagation.
- Exclude finding any satisfying assignment when no epistemic conclusion is
  asserted; that is `constraint_solving` as a computational realization.
- Exclude qualitative criteria-based assessment whose criteria do not compile
  to formal constraints.

### Theorem proving (`theorem_proving`)

Constructs a proof, proof certificate, or derivation establishing a theorem in
a specified formal system.

- Parents: `formal_deductive` and, when search is essential, `model_based` may
  be co-applied but is not entailed.
- Include when the output contains or denotes a checkable proof/certificate,
  not just a plausible theorem statement.
- Exclude theorem-statement generation, proof-plan generation, proof retrieval,
  and proof checking; those are separate operations.
- Exclude a solver's `sat` result from theorem proving unless the reduction and
  certificate support the claimed theorem.

Proof by calculation, rewriting, induction, contradiction, model checking, or
deduction can be recorded as method facets beneath theorem proving without
turning each proof tactic into a top-level archetype.

### Generative symbolic reasoning (`generative_symbolic_reasoning`)

Proposes a novel symbolic candidate—such as an equation, invariant, lemma,
formal model, or rewrite rule—whose validity is not guaranteed by the generation
procedure.

- Include when generation is guided by patterns, examples, goals, heuristics,
  or a learned model and the output changes epistemic possibilities.
- Exclude deterministic enumeration when no candidate is privileged; use
  search/enumeration.
- Exclude a truth-preserving derivation of an equation; use equational
  inference.
- Require later validation before the generated candidate is treated as
  established.

This category may co-label abduction, induction, analogy, or model-based
reasoning according to the candidate's license. “Generative” describes the
candidate-forming move; it does not establish a distinct source of warrant.

## Equational work: derivation versus generation

An equation in the output is not enough to classify the operation. Apply this
decision table:

| Case | Reasoning archetype | Operational role | Preservation claim |
| --- | --- | --- | --- |
| Rewrites `x + 0` to `x` under declared algebraic laws | equational inference | symbolic manipulation | equivalence preserving |
| Solves an equation by reversible transformations | equational inference | symbolic solving | equivalence preserving |
| Derives a new equality from premises | equational inference | derivation | truth preserving |
| Fits parameters to observations | statistical/model-based as supported | optimization or estimation | none or approximate |
| Guesses a governing equation from trajectories | generative symbolic, often abductive or inductive | equation conjecture | candidate generating |
| LLM proposes an intermediate identity for a proof | generative symbolic | lemma/equation conjecture | candidate generating |
| Checker verifies the proposed identity | none required, unless it derives a new consequence | formal validation | none |
| Formats an equation in another notation | none | representational transformation | meaning intended or equivalence preserving |

“Symbolic equational reasoning” should therefore be represented as the
combination `equational_inference + symbolic representation`; it should not be
a single opaque label. “Generative equational reasoning” should normally be
`generative_symbolic_reasoning + equation_conjecture`, optionally followed by
`equational_inference` or validation in a separate occurrence.

## Information operations over formal artifacts

These extend the operational-role facet and do not imply reasoning.

### Symbolic manipulation (`symbolic_manipulation`)

Transforms formal expressions by substitution, rewriting, expansion,
factorization, normalization, simplification, elimination, or canonicalization.

- Use alone when the task is representation-level transformation.
- Add `equational_inference` only when the transformation constitutes an
  epistemically asserted derivation under explicit laws.
- Add `formal_validation` when preservation is checked rather than presumed.

### Formalization (`formalization`)

Maps an informal, semi-formal, or differently formalized source into a target
formal language with declared syntax and semantics.

- Include manually specified or algorithmic translations.
- The primary family is normally information operation when commitments are
  intended to be preserved.
- Add conceptual reasoning if the operation resolves genuine conceptual gaps
  or introduces a new ontology.
- Add reasoning labels only for actual inferential moves used to resolve the
  translation, not because the output is formal.

### Autoformalization (`autoformalization`)

Formalization performed substantially by an automated or learned system. It is
a computational realization of `formalization`, not a reasoning archetype.

Record at least:

- source regime: natural language, diagram, code, semi-formal specification,
  or another formal language;
- target formalism and semantics;
- ambiguity policy: preserve alternatives, request clarification, choose one,
  or abstain;
- traceability from source claims to formal declarations;
- validation status and round-trip or proof obligations.

An LLM-backed autoformalizer is `generative_model` realization and typically
`underdetermined`; a parser/compiler-based translation may be deterministic.
Neither implementation choice establishes truth preservation.

### Formalization validation (`formalization_validation`)

Evaluates whether a formalization is syntactically valid, well typed,
semantically faithful, complete relative to its declared scope, and traceable to
the source.

- Primary family: evaluation and judgment.
- Operational parent: `validate_verify`.
- Separate the verdict dimensions: syntax, typing, internal consistency,
  semantic adequacy, coverage/completeness, and source traceability.
- A parser can establish syntax; a type checker can establish typing; neither
  alone establishes semantic faithfulness to prose.
- Round-trip paraphrase is evidence of intended meaning, not a formal proof of
  equivalence unless a semantics connects both representations.

## Representational regimes

Replace the overly broad `symbolic` value only through compatible refinements;
retain `symbolic` as their parent:

- `logical_formula`: formulas and sequents under a declared logic;
- `equational_expression`: terms, equations, rewrite systems, and algebraic
  structures;
- `typed_formal_term`: types, terms, judgments, and proof objects;
- `constraint_system`: variables, domains, constraints, and objectives;
- `formal_specification`: transition systems, contracts, temporal properties,
  state machines, or executable specifications;
- `proof_artifact`: derivations, certificates, tactics, and proof traces;
- `program_or_code`: executable or compilable symbolic artifact;
- `natural_language`: materially interpreted prose;
- `hybrid_formal_natural_language`: linked prose, symbols, assumptions, and
  provenance.

The formalism should also be recorded when known: first-order logic, SMT-LIB,
Lean, Coq, Isabelle, SVA, temporal logic, algebraic specification, and so on.
These are values of a `formal_language` field, not new reasoning archetypes.

## Computational realization

The implementation mechanism remains independent of the reasoning label:

- `symbolic_rule_engine`: applies explicit inference or rewrite rules;
- `computer_algebra_system`: performs algebraic manipulation and solving;
- `proof_assistant_kernel`: checks proof terms against a trusted calculus;
- `automated_theorem_prover`: searches for formal proofs;
- `sat_smt_constraint_solver`: searches models or proves unsatisfiability;
- `model_checker`: explores a state model against a formal property;
- `type_checker_or_inferencer`: establishes typing judgments;
- `compiler_or_translator`: carries out specified formal transformations;
- `generative_model`: proposes non-unique symbolic or textual candidates;
- `hybrid_neuro_symbolic`: combines learned generation with explicit symbolic
  execution or checking;
- `human_formal_reasoning`: a person constructs or checks the formal artifact;
- `unspecified`.

Also annotate:

- execution determinacy: deterministic, stochastic, underdetermined, or mixed;
- search completeness: complete, bounded, heuristic, anytime, or unknown;
- certificate posture: proof-producing, model-producing, verdict-only, or none;
- trusted base: rules, kernel, solver assumptions, numerical tolerances,
  libraries, and environment versions where relevant.

An LLM can perform informal deduction, propose formal expressions, or orchestrate
a theorem prover. “LLM-based” therefore belongs only in computational
realization; “traditional symbolic” describes an explicit-rule realization,
not a separate epistemic archetype.

## Boundary tests for neighboring categories

| Candidate label | Include when | Do not infer from |
| --- | --- | --- |
| formal deduction | Explicit rules/semantics license a necessary conclusion | Formal-looking notation or typed I/O |
| definitional reasoning | A definition is the license or object of substantive construction/evaluation | Glossary extraction or ordinary classification |
| equational inference | Equality/rewrite laws license a derived equality or consequence | Any output containing an equation |
| symbolic manipulation | Symbols are transformed according to explicit operations | Natural-language editing with variable names |
| theorem proving | A checkable proof or certificate establishes a theorem | Theorem statement or proof-shaped prose |
| constraint entailment | Constraints force or exclude a proposition | Merely finding one feasible assignment |
| type-theoretic inference | Explicit typing rules license a judgment | Schema validation or typed workflow edges |
| autoformalization | Automation maps content into a declared formal language | Any LLM generation of structured text |
| formalization validation | A formalization is checked along named validity dimensions | Successful parse alone |
| generative symbolic reasoning | A novel symbolic candidate is epistemically proposed | Truth-preserving derivation or exhaustive enumeration |

## Corpus anchors and abstentions

The current corpus supplies useful candidates, but most lack enough visible
procedure to receive the narrowest formal labels with high confidence:

- `DeductiveExactTheoremClaimDerivation` supports `deductive`; assign
  `formal_deductive` or `theorem_proving` only if explicit premises, rules, and
  a proof/certificate are exposed. A generated exact claim is not itself a
  proof.
- `DeductiveFormalClaimDerivation` and
  `DeductiveConceptualBridgeConsequenceDerivation` are candidates for formal
  deduction. Their typed contracts and names are supporting evidence, not a
  mechanically checkable license.
- `DeductiveConsequenceMaterialization` may combine formal deduction with
  materialization. Confirm the admitted rules and derivation before assigning
  equational or logical subtypes.
- `RefutationalSolverCoherenceReview` may use constraint or logical reasoning;
  solver use alone establishes computational realization, not the exact
  reasoning archetype or correctness of the encoded premises.
- Hardware Verification formal-artifact components can instantiate
  formalization, formal validation, temporal logical inference, or artifact
  generation. Separate these functions even when a present occurrence bundles
  them.
- `EvidentialFormalizationReadinessAssessment` is a readiness judgment about
  whether formalization should proceed; it is neither autoformalization nor
  formal validation.

No current occurrence should be force-labeled as equational inference,
definition formation, or autoformalization solely to populate the new branch.
These classes are canonical extension points until authored cases provide
positive evidence.

## Recommended integration rules

1. Add the new labels as provisional taxa first; do not rewrite existing
   component mappings automatically.
2. Preserve `deductive` as a broad parent and make `formal_deductive` the parent
   of logical, equational, type-theoretic, constraint-entailment, and
   theorem-proving forms.
3. Add `definitional_reasoning` independently, permitting co-labeling with
   conceptual reasoning and formal deduction.
4. Add `generative_symbolic_reasoning` for candidate formation, never as a
   substitute for the archetype that explains the candidate's warrant.
5. Add formalization, autoformalization, symbolic manipulation, and validation
   under operational/computational facets rather than reasoning archetypes.
6. Replace compound labels such as “LLM equational reasoning” with faceted
   combinations that expose representation, epistemic move, and realization.
7. Require a preservation claim and evidence locator whenever a component is
   labeled formal, equational, or theorem proving.
8. Keep candidate generation and checking in separate occurrences where
   possible. This makes epistemic status and failure localization explicit.

## Open design questions

- Whether `theorem_proving` should be indexed only as formal deduction or also
  represented as a procedure family. The proposal recommends both facets when
  the occurrence both constructs a proof and uses proof search.
- Whether definition formation is always conceptual reasoning. The proposal
  permits but does not require that co-label: some definitions are conservative
  abbreviations with no conceptual revision.
- Whether solver-produced unsatisfiability without a replayable certificate is
  enough for formal warrant. This depends on the declared trust model and should
  be recorded rather than silently assumed.
- How to express approximate symbolic work, such as numerical equivalence over
  a tolerance. It should not inherit exact equational truth preservation without
  an explicit approximation semantics.
