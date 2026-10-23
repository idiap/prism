# Prism workflow corpus inventory and initial functional taxonomy

## Purpose and method

This document inventories the authored occurrence nodes in `catalog/graphs.json`
without changing or reinterpreting the workflows. Inputs and result nodes are
excluded because they are workflow boundaries, not component functions. The
unit of analysis is therefore one node whose authored `kind` is `occurrence`.

The corpus contains **3 projects, 33 workflows, 152 occurrences, and 140 unique
method names**. Physics Discovery contributes 19 workflows / 65 occurrences;
Oncology Discovery contributes 11 / 72; Hardware Verification contributes
3 / 15. Of the 152 occurrences, 137 have authored commentary and 134 have at
least one mapped skill.

The classification below records an independent exploratory pass, not the
canonical row-level assignment and not a claim that the current Prism schema
already encodes these categories. The maintained mapping in
`component-mapping.csv` later resolves its combined control/evaluation family
into separate families and retains refutation as a reasoning archetype whose
primary workflow function is evaluation. After the version 0.6 audit, its final
counts are 24 information operations, 38 core reasoning components, 39
evaluations, 39 control/governance components, and 12 discourse/artifact
components. The exploratory pass uses the
method name, typed input/output contract, and authored commentary as evidence. A primary
class is assigned for comparison, while the proposed taxonomy itself is faceted:
one component can, for example, be `model-based` in epistemic mode,
`transformational` in information operation, `explanatory-model construction`
in discourse role, and `generative` in execution mode.

## Initial four-way functional partition

| Code | Primary function | Operational test | Corpus count |
|---|---|---|---:|
| O | Information operation | Admits, bounds, projects, extracts, normalizes, represents, or retrieves information without itself licensing a new object-level conclusion | 19 |
| D | Discourse / artifact formation | Organizes claims, plans, specifications, reports, presentations, tests, or release packages for use or communication | 16 |
| R | Core reasoning | Produces a conclusion by an identifiable inferential mode: abductive, deductive, inductive, analogical, contrastive, model-based, or diagnostic | 38 |
| C | Control / evaluation | Tests, critiques, judges, calibrates, selects, gates, routes, forecasts, or audits another product or process | 79 |

These counts are deliberately conservative. In particular, an occurrence named
`Evidential…Bounding` is classified as O when its stated function is admission
and claim-boundary preservation, while an `Evidential…Assessment` is C. A
refutational test is C because its workflow role is adversarial evaluation,
even though refutation is itself a reasoning process. The facets below retain
that secondary epistemic identity.

## Proposed faceted taxonomy

### 1. Epistemic basis: what licenses the conclusion?

- **Formal inference**: rule- or contract-preserving deduction, consequence
  materialization, theorem derivation, temporal assertion validation, and typed
  solver coherence. Formality requires explicit premises/rules/contracts; a
  method name containing “deductive” is supporting evidence, not by itself a
  proof that an implementation is sound.
- **Material inference**: conclusions constrained by domain evidence and causal
  content—biological contexts, proof evidence, manuscripts, experimental
  patterns, circuit mechanisms, or debug traces. Evidential bounding and claim
  calibration belong here as an epistemic basis but remain O or C functionally.
- **Computational inference**: conclusions obtained by simulation, solver
  synthesis, model probing, assertion generation/validation, or debug detection.
  This axis describes the mechanism, not whether the result is deductively
  guaranteed.
- **Probabilistic / statistical inference**: a necessary category, but **not
  explicitly instantiated in this corpus**. Ranking, uncertainty, empirical
  support, and “best explanation” occur, yet no occurrence contract authors a
  probability distribution, likelihood, posterior, estimator, confidence
  interval, or statistical test. Those cases must not be relabeled probabilistic
  without additional evidence.
- **Conceptual / semantic inference**: identifies obstructions, forms or revises
  conceptual hypotheses, transfers conceptual bridges, or derives consequences
  from them. It is cross-cutting: the corpus realizes abductive, analogical, and
  deductive subclasses of conceptual reasoning.

### 2. Inferential archetype: what transformation of warrant occurs?

The corpus explicitly names 12 abductive, 6 deductive, 5 inductive, 4 analogical,
6 model-based, 2 contrastive, and 16 refutational occurrences. It also contains
38 `Evidential…` methods and 9 `Unresolved…Projection` methods; these are not
parallel inference archetypes. “Evidential” marks grounding or assessment
against evidence, while “unresolved projection” explicitly marks a
claim-conserving information transformation.

- **Abduction**: propose an explanatory, mediating, repair, proof-route,
  extension, or contribution hypothesis.
- **Deduction**: derive an explicit claim or consequence from a hypothesis,
  bridge, premise set, or admitted solver payload.
- **Induction**: generalize a provisional support, discovery, circuit, or
  resistance pattern from bounded observations.
- **Analogy / transport**: map a conceptual bridge or assess correspondence
  across contexts while retaining divergence and transport limits.
- **Model-based reasoning**: construct a causal/mechanistic model, simulate or
  probe implications, synthesize a solver result, or rank targets under a model.
- **Contrastive reasoning**: compare a focal hypothesis against alternatives and
  identify discriminating observations.
- **Refutational reasoning**: seek defeaters, counterexamples, incoherence,
  unsupported edges, bypass mechanisms, or failed predictions. Its primary
  workflow function is evaluation (C), not positive conclusion formation.
- **Diagnostic reasoning**: explain observed failure and select discriminating
  probes. `DiagnoseAndPlanDebugProbes` is the clearest explicit corpus instance.
- **Explanatory / mechanistic reasoning**: a discourse-level goal realized by
  combinations of abduction, induction, causal-graph construction, model probing,
  and refutational pressure; it should not replace those more precise modes.

### 3. Information operation: what happens to the representation?

- **Retrieval**: fetch an external item by query or key. This category is needed
  in the taxonomy, but no occurrence explicitly performs retrieval. Several
  skills may use sources, yet the authored occurrence contracts start from
  already supplied requests, evidence, or contexts.
- **Admission / filtering**: accept relevant evidence or premises while retaining
  exclusions (`…EvidenceBounding`, `…PayloadAdmission`).
- **Extraction**: recover symbols, timing, relations, or semantic intent from an
  input (`ExtractSvaSemanticModel`).
- **Selection / ranking**: choose among hypotheses, targets, routes, or options.
  Selection may be evaluative; ranking may be model-based. Neither is mere
  extraction.
- **Projection / transformation**: reshape a source into a bounded frontier,
  packet, presentation, proposal, dependency map, or audit input without adding
  warrant. The nine `Unresolved…Projection` occurrences make this distinction
  unusually explicit.
- **Normalization / representation**: standardize heterogeneous evidence or
  build typed findings (`IntakeAndNormalizeDebugEvidence`,
  `RepresentAndDetectDebugFindings`). Detection makes the latter a composite
  boundary.
- **Aggregation / synthesis**: join independently produced streams into a model,
  assessment, closure record, or package. Aggregation should be separately
  tagged from the reasoning applied after the join.

### 4. Discourse and artifact function: what communicative object is formed?

- **Conceptualization**: bound a conceptual frontier, identify an obstruction,
  form a mediating concept, build/revise a bridge, and state its formal
  consequence.
- **Claim formation**: turn evidence or hypotheses into candidate, exact, or
  contribution claims with explicit scope.
- **Explanation formation**: construct explanatory hypotheses and contextual or
  mechanistic graphs, preserving alternatives and limitations.
- **Argument / proof organization**: order premises, derived consequences,
  refutation records, proof entrypoints, and disposition certificates.
- **Discourse selection and curation**: maintain hypothesis memory, choose
  bounded manuscript claims, and decide what can enter a presentation.
- **Presentation / publication**: form claim-bounded presentations, manuscript
  readiness decisions, and final reviewed packages.
- **Specification and planning**: decompose workflows; specify skills, hooks,
  acceptance criteria, tests, remediation, and evolution plans.
- **Account / report formation**: document implementation, validation, review,
  reflection, and closure without conflating the report with the work reported.

### 5. Control and evaluation function: what decision is made?

- **Grounding and scope control**: freeze evidence, provenance, domain, target,
  and claim ceilings before generative reasoning.
- **Quality / readiness assessment**: judge auditability, formalization,
  manuscript release, assertion validity, or testability.
- **Adversarial evaluation**: refutation, critical review, coherence review,
  validity pressure, drift critique, and independent portfolio critique.
- **Epistemic calibration**: assign claim status or release ceiling from both a
  candidate and its bounded review record.
- **Routing / gating**: choose continue, pivot, stop, promote, reframe, retarget,
  repair, or invoke another workflow.
- **Meta-control**: classify intent/novelty, assess capability sufficiency,
  establish acceptance/stop criteria, monitor goal closure, and guard monotonic
  skill evolution.
- **Feedback control**: compare current state with criteria, localize defects,
  propose bounded repair, validate it, and retain residual findings. This is the
  taxonomy location for feedback cycles; feedback is a topology, not one
  reasoning archetype.

## Execution and certainty facets

The user-requested deterministic/probabilistic distinction cannot safely be
inferred from names alone. The following tags should be authored or derived from
implementation evidence:

| Facet value | Meaning | Corpus evidence / limitation |
|---|---|---|
| Deterministic | Same valid input and fixed rules imply the same output | Plausible for projection, normalization, typed compilation, and rule checks, but `Generated[...]` contracts do not guarantee it |
| Generative | Produces a candidate whose content may vary | Many occurrences have mapped generative skills; candidate/hypothesis formation is the clearest case |
| Search-based | Explores alternatives or counterexamples | Abduction, counterexample hunting, contrastive probes, and target ranking |
| Simulation-based | Executes or approximates a model | Model probes, logical-combination simulation, and hardware emulation/test design |
| Probabilistic | Represents or updates quantitative uncertainty | Taxonomy placeholder only; no explicit corpus contract |
| Human-/review-gated | Requires judgment before promotion | Readiness, release, monotonicity, acceptance, and closure gates; implementation details still need confirmation |

## Recurring functional families and extensions supported by the corpus

1. **Bound → form → pressure-test → calibrate** recurs in physics and oncology.
   It motivates separate `scope-control`, `candidate-formation`, `adversarial-
   evaluation`, and `epistemic-calibration` concepts rather than one generic
   “reasoning” label.
2. **Parallel abduction and induction → model/contrast probes → refutation →
   route** appears in both Discovery Marathon and Discovery Control. The
   taxonomy therefore needs `parallel evidence independence`, `convergence`,
   and `joint calibration` as topology tags.
3. **Pattern → analogy/transport → mechanistic model → external-validity
   review** appears in cross-context oncology workflows. This supports distinct
   `transport reasoning` and `mechanistic construction` classes.
4. **Projection → readiness gate** recurs across the Cohere Fast family. The
   projection commentary repeatedly says that no warrant is added. This is the
   strongest evidence for separating information transformation from reasoning.
5. **Specify/implement → critique/validate → abductively interpret → refine →
   closure guard** characterizes meta-framework workflows. It adds lifecycle,
   feedback-control, and artifact-accounting categories that a classical
   inference taxonomy would miss.
6. **Extract/represent → generate → validate/test/critique → synthesize →
   publish** characterizes hardware verification. Several nodes are composite,
   motivating multi-label decomposition or finer future Prism occurrences.

## Ambiguous and composite cases

- `EvidentialConceptualFrontierGrounding`, `EvidentialReviewStateGrounding`, and
  `EvidentialDiscoveryScopeGrounding` combine information bounding with an
  epistemic judgment. They are counted C because the output is an assessed
  state, but should also carry O:`grounding`.
- `EvidentialConceptualHypothesisSelection` is selective and evaluative, not a
  new hypothesis inference. It should carry C:`selection` and O:`selection`.
- `DeductiveConsequenceMaterialization` combines formal deduction (R) with
  explicit artifact materialization (O).
- `ModelBasedContextualGraphConstruction` and
  `ModelBasedCrossTumorCircuitConstruction` are both mechanistic reasoning (R)
  and explanatory discourse construction (D).
- `HypothesisMemorySynthesis` is counted D because it curates a discourse state;
  “synthesis” does not establish a new inferential warrant.
- `FrameworkOutcomeAbduction` is genuine abduction despite lacking the common
  `Abductive…` prefix.
- `EpistemicModelRefinement` is counted R because it revises assumptions and an
  epistemic model, but it also participates in meta-control.
- `GenerateAndAssessSvaCandidate`, `CritiqueAndRouteSvaRefinement`,
  `PlanAndGenerateAssertions`, `DesignAssertionGuidedTests`,
  `RepresentAndDetectDebugFindings`, and `DiagnoseAndPlanDebugProbes` each join
  two or more materially different functions. They should eventually be split
  into occurrences or receive multiple function tags.
- `SynthesizeReflectionClosure` aggregates evidence, localizes defects, refines,
  and audits repair. It is counted C, but aggregation (O) and account formation
  (D) are also present.
- `Finalize…Package` methods are counted D because their authored function is
  publication of reviewed artifacts. “Finalize” alone does not establish that
  validation occurred inside the node.
- `SkillMonotonicityJudgment` appears in five workflows with different input
  types. The recurring method is a control invariant, not domain reasoning.

## Recommended taxonomy record

For a future taxonomy artifact, each occurrence should be described by separate
fields rather than one `reasoning_type` string:

```yaml
primary_function: reasoning | information_operation | discourse_artifact | control_evaluation
epistemic_basis: [formal, material, computational, conceptual, probabilistic]
inference_mode: [abductive, deductive, inductive, analogical, contrastive, model_based, refutational, diagnostic]
information_operation: [retrieve, admit, extract, select, rank, project, normalize, represent, aggregate, transform]
discourse_function: [conceptualize, form_claim, explain, construct_model, organize_argument, curate, specify, plan, report, publish]
control_function: [ground, assess, critique, calibrate, gate, route, validate, audit, close_loop]
execution_mode: [deterministic, generative, search_based, simulation_based, human_gated, unknown]
topology_role: [source, branch, parallel, converge, feedback, sink]
certainty: authored | strongly_inferred | provisional | unknown
evidence: {project, workflow, occurrence, method, commentary, input_type, output_type}
```

This structure permits “formal deduction” and “computational model probing” to
coexist with extractive, selective, or discourse-organizing functions without
calling every workflow element reasoning.

## Complete occurrence inventory

The appendix uses the primary codes above. Commentary is quoted from the graph
bundle; `—` means no node commentary was authored. Types preserve the authored
`Generated[...]` wrapper.

### Physics Discovery

#### Abducer Work Loop (`abducer_work_loop`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| R | `route_hypothesis`<br>`AbductiveProofRouteHypothesisFormation` | `ActiveProofGap` → `Generated[ProofRouteHypothesis]` | Formation and deduction turn the gap into a concrete claim that can fail. |
| R | `derived_claim`<br>`DeductiveProofRouteClaimDerivation` | `ProofRouteHypothesis` → `Generated[ProofRouteDerivedClaim]` | — |
| C | `refutation_assessment`<br>`RefutationalProofRouteClaimAssessment` | `ProofRouteDerivedClaim` → `Generated[ProofRouteRefutationAssessment]` | Refutation tests the claim; calibration uses claim and test, not either alone. |
| C | `work_routing`<br>`EvidentialProofWorkRoutingAssessment` | `ProofWorkRoutingInput` → `Generated[ProofWorkRoutingAssessment]` | — |

#### Cohere Fast (`cohere_fast`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `scope_activation`<br>`UnresolvedCohereScopeProjection` | `CohereDomainTarget` → `Generated[CohereScopeActivation]` | The projection only activates a scope; it contributes no object-level warrant. |
| C | `intake_disposition`<br>`EvidentialCohereIntakeDispositionAssessment` | `CohereScopeActivation` → `Generated[CohereIntakeDisposition]` | Intake evaluates that activation and emits the pipeline-routing alternative. |

#### Cohere Fast Adaptive Frontier (`cohere_fast_adaptive_frontier`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_frontier`<br>`UnresolvedDomainFrontierProjection` | `DomainScopeGrounding` → `Generated[BoundedDomainFrontier]` | Frontier construction must preserve the grounding's domain and claim ceiling. |
| C | `frontier_readiness`<br>`EvidentialFrontierReadinessAssessment` | `BoundedDomainFrontier` → `Generated[FrontierReadinessDisposition]` | Readiness gates use of the bounded frontier; they do not promote its claims. |

#### Cohere Fast Derivation And Proof (`cohere_fast_derivation_and_proof`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `conditional_derivation`<br>`UnresolvedConditionalDerivationProjection` | `BoundedDomainFrontier` → `Generated[ConditionalDerivationPacket]` | The unresolved projection produces a conditional packet with obligations intact. |
| C | `derivation_readiness`<br>`EvidentialDerivationReadinessAssessment` | `ConditionalDerivationPacket` → `Generated[DerivationReadinessDisposition]` | Readiness assesses auditability, not truth or continuum-level completion. |

#### Cohere Fast Independent Audit (`cohere_fast_independent_audit`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `refutation_assessment`<br>`RefutationalIndependentDerivationAudit` | `ConditionalDerivationPacket` → `Generated[IndependentRefutationAssessment]` | The audit searches for a defeater but cannot turn non-refutation into proof. |
| C | `audit_disposition`<br>`EvidentialIndependentAuditDispositionAssessment` | `IndependentAuditDispositionInput` → `Generated[IndependentAuditDisposition]` | Calibration explicitly joins source packet and audit result before routing. |

#### Cohere Fast Manuscript Release (`cohere_fast_manuscript_release`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `claim_bounded_presentation`<br>`UnresolvedClaimBoundedPresentationProjection` | `IndependentAuditPacket` → `Generated[ClaimBoundedPresentation]` | Presentation construction preserves source audit identity and claim ceiling. |
| C | `release_disposition`<br>`EvidentialManuscriptReleaseDispositionAssessment` | `ClaimBoundedPresentation` → `Generated[ManuscriptReleaseDisposition]` | Release evaluates the bounded presentation without increasing claim authority. |

#### Cohere Fast Scope And Ground (`cohere_fast_scope_and_ground`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `scope_grounding`<br>`UnresolvedDomainScopeGroundingProjection` | `DomainScopeGroundingRequest` → `Generated[DomainScopeGrounding]` | Grounding establishes scope and provenance but creates no scientific warrant. |
| C | `grounding_disposition`<br>`EvidentialScopeGroundingDispositionAssessment` | `DomainScopeGrounding` → `Generated[ScopeGroundingDisposition]` | The disposition checks whether the bounded grounding can support the next lane. |

#### Conceptual Frontier Deepening (`conceptual_frontier_deepening`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `conceptual_frontier`<br>`EvidentialConceptualFrontierGrounding` | `FrozenConceptualContext` → `Generated[BoundedConceptualFrontier]` | Grounding bounds the search before abductive formation begins. |
| R | `conceptual_hypothesis`<br>`AbductiveConceptualHypothesisFormation` | `BoundedConceptualFrontier` → `Generated[DiscriminatingConceptualHypothesis]` | — |
| C | `refutation_assessment`<br>`RefutationalConceptualHypothesisAssessment` | `DiscriminatingConceptualHypothesis` → `Generated[ConceptualHypothesisRefutationAssessment]` | Refutation and selection prevent an attractive hypothesis from advancing alone. |
| C | `hypothesis_selection`<br>`EvidentialConceptualHypothesisSelection` | `ConceptualHypothesisSelectionInput` → `Generated[ConceptualHypothesisSelection]` | — |
| R | `conceptual_bridge`<br>`AnalogicalConceptualBridgeRevision` | `ConceptualHypothesisSelection` → `Generated[RevisedConceptualBridge]` | Transfer creates a bridge; deduction makes its formal consequence explicit. |
| R | `formal_claim`<br>`DeductiveFormalClaimDerivation` | `RevisedConceptualBridge` → `Generated[BridgeDerivedFormalClaim]` | — |
| C | `calibrated_candidate`<br>`EvidentialFormalizationReadinessAssessment` | `BridgeDerivedFormalClaim` → `Generated[FormalizationReadinessAssessment]` | The final assessment routes the claim; it does not itself prove it. |

#### Conceptual Hypothesis Exploration Loop (`conceptual_hypothesis_exploration_loop`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `obstruction_pressure`<br>`EvidentialConceptualObstructionAssessment` | `ConceptualFailureState` → `Generated[ConceptualObstructionPressure]` | Diagnosis bounds what the abductive repair must explain. |
| R | `mediation_hypothesis`<br>`AbductiveMediationHypothesisFormation` | `ConceptualObstructionPressure` → `Generated[ConceptualMediationHypothesis]` | — |
| R | `conceptual_bridge`<br>`AnalogicalConceptualBridgeTransfer` | `ConceptualMediationHypothesis` → `Generated[MediatingConceptualBridge]` | Analogy constructs a bridge; deduction exposes a consequence that can fail. |
| R | `bridge_consequence`<br>`DeductiveConceptualBridgeConsequenceDerivation` | `MediatingConceptualBridge` → `Generated[BridgeDerivedConsequence]` | — |
| C | `refutation_assessment`<br>`RefutationalBridgeConsequenceAssessment` | `BridgeDerivedConsequence` → `Generated[BridgeConsequenceRefutationAssessment]` | Refutation tests the consequence before the final routing calibration. |
| C | `refinement_routing`<br>`EvidentialConceptualRefinementRoutingAssessment` | `ConceptualRefinementRoutingInput` → `Generated[ConceptualRefinementRoutingAssessment]` | — |

#### Deep Review And Reorientation (`deep_review_and_reorientation`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `review_state`<br>`EvidentialReviewStateGrounding` | `ReviewEvidenceBundle` → `Generated[FormalizedReviewState]` | One formalized state prevents the challenge and repair branches from silently reviewing different evidence bases. |
| C | `defeater_assessment`<br>`RefutationalReviewDefeaterAssessment` | `FormalizedReviewState` → `Generated[ReviewDefeaterAssessment]` | These branches are complementary: one attacks, the other repairs. |
| R | `repair_options`<br>`AbductiveReorientationRepairFormation` | `FormalizedReviewState` → `Generated[ReorientationRepairOptions]` | — |
| C | `reorientation_decision`<br>`EvidentialReorientationDecisionAssessment` | `ReorientationDecisionInput` → `Generated[ReorientationDecisionAssessment]` | The final calibration must consider both bounded findings and repair options. |

#### Discovery Marathon Loop (`discovery_marathon_loop`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `search_scope`<br>`EvidentialDiscoveryScopeGrounding` | `DiscoveryRunContext` → `Generated[BoundedDiscoveryScope]` | Scope grounding prevents later formation from silently widening the run. |
| R | `discovery_hypothesis`<br>`AbductiveDiscoveryHypothesisFormation` | `BoundedDiscoveryScope` → `Generated[DiscriminatingDiscoveryHypothesis]` | Abduction proposes an explanation while induction extracts a pattern; neither is treated as confirmation of the other. |
| R | `discovery_pattern`<br>`InductiveDiscoveryPatternFormation` | `BoundedDiscoveryScope` → `Generated[ProvisionalDiscoveryPattern]` | — |
| R | `model_implications`<br>`ModelBasedDiscoveryHypothesisProbe` | `DiscoveryHypothesisProbeInput` → `Generated[HypothesisModelImplications]` | Both probes consume the same typed hypothesis-pattern join but ask different questions: implications under a model versus a contrast case. |
| R | `contrast_assessment`<br>`ContrastiveDiscoveryHypothesisProbe` | `DiscoveryHypothesisProbeInput` → `Generated[HypothesisContrastAssessment]` | — |
| C | `refutation_assessment`<br>`RefutationalDiscoveryHypothesisAssessment` | `DiscoveryRefutationInput` → `Generated[HypothesisRefutationAssessment]` | Refutation combines the two probes before routing sees the candidate. |
| C | `routing_assessment`<br>`EvidentialDiscoveryRoutingAssessment` | `DiscoveryRoutingInput` → `Generated[DiscoveryRoutingAssessment]` | Routing joins formation and refutation evidence into the next-cycle decision. |

#### Evidence To Proof Route Onramp (`evidence_to_proof_route_onramp`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `e0`<br>`EvidentialProofRouteGrounding` | `ProofRouteSourceBundle` → `Generated[ProofRouteEvidenceGround]` | Grounding and abduction create a source-constrained route hypothesis. |
| R | `a0`<br>`AbductiveProofRouteHypothesisFormation` | `ProofRouteEvidenceGround` → `Generated[ProofRouteHypothesis]` | — |
| R | `d0`<br>`DeductiveProofRouteConsequenceDerivation` | `ProofRouteHypothesis` → `Generated[ProofRouteDerivedConsequence]` | Deduction and evidence assessment make the route's consequences inspectable. |
| C | `e1`<br>`EvidentialProofRouteConsequenceAssessment` | `ProofRouteDerivedConsequence` → `Generated[ProofRouteConsequenceAssessment]` | — |
| R | `a1`<br>`AbductiveProofObligationEntrypointRevision` | `ProofRouteConsequenceAssessment` → `Generated[ProofObligationEntrypointHypothesis]` | Revision selects a proof entrypoint; refutation then challenges that entry. |
| C | `r0`<br>`RefutationalProofEntrypointAssessment` | `ProofObligationEntrypointHypothesis` → `Generated[EntrypointFalsificationAssessment]` | — |
| C | `e2`<br>`EvidentialProofRouteReadinessAssessment` | `ProofRouteReadinessInput` → `Generated[ProofRouteReadinessAssessment]` | The final join preserves both the proposed entrypoint and its falsification record. |

#### Manuscript Result Elaboration (`manuscript_result_elaboration`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `e0`<br>`EvidentialManuscriptResultScopeAssessment` | `PaperDraft` → `Generated[ManuscriptResultScope]` | Scope assessment prevents extension from silently enlarging the result. |
| R | `a0`<br>`AbductiveManuscriptExtensionHypothesisFormation` | `ManuscriptResultScope` → `Generated[ManuscriptExtensionHypothesis]` | Abduction proposes an extension only within that assessed scope. |
| C | `r0`<br>`RefutationalManuscriptExtensionAssessment` | `ManuscriptExtensionHypothesis` → `Generated[ExtensionValidityAssessment]` | Refutation tests the extension before readiness can integrate it. |
| C | `e1`<br>`EvidentialManuscriptReadinessAssessment` | `ManuscriptReadinessInput` → `Generated[ManuscriptReadinessAssessment]` | — |

#### Release Promotion Loop (`release_promotion_loop`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `release_proposal`<br>`UnresolvedReleaseProposalProjection` | `PromotionEvidencePacket` → `Generated[ClaimBoundedReleaseProposal]` | Proposal formation is claim-conserving and adds no epistemic warrant. |
| C | `promotion_disposition`<br>`EvidentialReleasePromotionDispositionAssessment` | `ClaimBoundedReleaseProposal` → `Generated[ReleasePromotionDisposition]` | The gate evaluates the bounded proposal and emits the cross-workflow route. |

#### Scientific Contribution Cultivation (`scientific_contribution_cultivation`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| R | `a0`<br>`AbductiveScientificContributionHypothesisFormation` | `ResultAtlasSlice` → `Generated[ScientificContributionHypothesis]` | Abduction interprets the result as a candidate contribution, not a fact. |
| C | `r0`<br>`RefutationalContributionSupportAssessment` | `ScientificContributionHypothesis` → `Generated[ContributionSupportAssessment]` | Refutation tests whether the proposed contribution is actually supported. |
| C | `e0`<br>`EvidentialContributionReadinessAssessment` | `ContributionReadinessInput` → `Generated[ContributionReadinessAssessment]` | Readiness joins hypothesis and support assessment and emits all three audits. |

#### Target Navigation Loop (`target_navigation_loop`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `dependency_frontier`<br>`UnresolvedTargetDependencyProjection` | `UnscopedResearchTarget` → `Generated[TargetDependencyFrontier]` | The unresolved projection maps dependencies but adds no warrant to the target. |
| C | `target_disposition`<br>`EvidentialTargetNavigationDispositionAssessment` | `TargetDependencyFrontier` → `Generated[TargetNavigationDisposition]` | Disposition assessment turns the mapped frontier into the next workflow route. |

#### Theorem Proof Delivery (`theorem_proof_delivery`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| R | `d0`<br>`DeductiveExactTheoremClaimDerivation` | `ExplicitPremises` → `Generated[ExactTheoremClaim]` | Deduction constructs the exact claim from explicit premises and obligations. |
| C | `r0`<br>`RefutationalExactTheoremClaimAssessment` | `ExactTheoremClaim` → `Generated[ExactClaimRefutationAssessment]` | Refutation tests exactly that claim rather than a weakened paraphrase. |
| C | `e0`<br>`EvidentialTheoremProofDispositionAssessment` | `TheoremProofDispositionInput` → `Generated[TheoremProofDispositionAssessment]` | Calibration joins claim and refutation to produce the gate and any certificate. |

#### Timeline Paper Independent Workflow (`timeline_paper_independent_workflow`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_claim_set`<br>`UnresolvedManuscriptClaimSetProjection` | `TimelineReasoningOutputs` → `Generated[BoundedManuscriptClaimSet]` | Projection creates presentation input but no new claim or evidence. |
| C | `paper_disposition`<br>`EvidentialTimelinePaperDispositionAssessment` | `BoundedManuscriptClaimSet` → `Generated[TimelinePaperDisposition]` | The paper gate evaluates whether the bounded set supports assembly. |

#### Ym Representational Dynamics Overlay (`ym_representational_dynamics_overlay`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `continuum_audit_input`<br>`UnresolvedContinuumAuditInputProjection` | `YangMillsTargetContext` → `Generated[ContinuumBoundaryAuditInput]` | The unresolved projection prepares an audit input but cannot cross the boundary. |
| C | `overlay_disposition`<br>`EvidentialYangMillsOverlayDispositionAssessment` | `ContinuumBoundaryAuditInput` → `Generated[YangMillsOverlayDisposition]` | The evidential gate determines whether the overlay remains boundary-safe. |

### Oncology Discovery

#### Bounded Ebr (`bounded_ebr`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_evidence`<br>`EvidentialEvidenceBounding` | `BoundedEbrRequest` → `Generated[BoundedEvidence]` | Admit relevant source items while retaining exclusions and limitations as the claim boundary. |
| R | `candidate_claim`<br>`AbductiveCandidateClaimFormation` | `BoundedEvidence` → `Generated[CandidateClaim]` | Form one explanatory claim whose grounds and uncertainties remain tied to the bounded evidence. |
| C | `review_verdict`<br>`RefutationalCandidateClaimReview` | `BoundedClaimReviewInput` → `Generated[ReviewVerdict]` | Search for objections and required revisions by testing the claim against admitted evidence and known limitations. |
| C | `claim_status`<br>`EvidentialBoundedClaimCalibration` | `BoundedClaimCalibrationInput` → `Generated[ClaimStatus]` | Assign a release ceiling from the surviving claim and review verdict without converting generated content into proof. |

#### Contextual Graph Ebr (`contextual_graph_ebr`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_evidence`<br>`EvidentialContextEvidenceBounding` | `ContextualGraphEbrRequest` → `Generated[BoundedContextEvidence]` | Bound evidence items and biological contexts while preserving exclusions and contextual limitations. |
| R | `support_pattern`<br>`InductiveContextSupportInference` | `BoundedContextEvidence` → `Generated[ContextSupportPattern]` | Induce a provisional support and counterpressure pattern from the bounded contextual evidence. |
| R | `candidate_explanation`<br>`AbductiveContextExplanationFormation` | `BoundedContextEvidence` → `Generated[ContextualCandidateExplanation]` | Form a candidate explanation directly from the same bounded evidence so it remains independent of the induced pattern. |
| R | `contextual_graph`<br>`ModelBasedContextualGraphConstruction` | `ContextualGraphConstructionInput` → `Generated[ContextualCausalGraphAssessment]` | Construct a contextual relation model only after joining the independently formed pattern and explanation. |
| R | `transport_assessment`<br>`AnalogicalGraphTransportAssessment` | `GraphTransportInput` → `Generated[GraphTransportAssessment]` | Assess which graph relations transfer across the bounded contexts and retain every stated transport limit. |
| C | `pressure_verdict`<br>`RefutationalContextualGraphPressure` | `ContextualPressureInput` → `Generated[ContextualPressureVerdict]` | Seek contextual defeaters by testing the graph against its transport failures and unsupported edges. |
| C | `claim_status`<br>`EvidentialContextualClaimCalibration` | `ContextualClaimCalibrationInput` → `Generated[ContextualClaimStatus]` | Calibrate the explanation's claim ceiling from the pressure verdict without treating transport as proof. |

#### Discovery Control (`discovery_control`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `search_scope`<br>`BoundDiscoverySearchScope` | `DiscoveryRunContext` → `Generated[DiscoverySearchScope]` | Turn the goal, target space, and knowledge slice into one testable search boundary before generating candidates. |
| R | `discovery_hypothesis`<br>`AbductiveDiscoveryHypothesisFormation` | `DiscoverySearchScope` → `Generated[DiscoveryHypothesis]` | Propose the best available explanation for the bounded question, including predictions and assumptions that later probes can challenge. |
| R | `discovery_pattern`<br>`InductiveDiscoveryPatternFormation` | `DiscoverySearchScope` → `Generated[DiscoveryPattern]` | Generalize a provisional pattern from the same bounded knowledge without depending on the abductive candidate. |
| R | `model_implications`<br>`ModelBasedDiscoveryHypothesisProbe` | `DiscoveryHypothesisProbeInput` → `Generated[DiscoveryModelImplications]` | Probe the hypothesis and induced pattern as a model to expose expected consequences, failed predictions, and model limits. |
| R | `contrast_assessment`<br>`ContrastiveDiscoveryHypothesisProbe` | `DiscoveryHypothesisProbeInput` → `Generated[DiscoveryContrastAssessment]` | Compare the focal hypothesis with rival explanations and identify observations that would discriminate among them. |
| C | `refutation_assessment`<br>`RefutationalDiscoveryHypothesisAssessment` | `DiscoveryRefutationInput` → `Generated[DiscoveryRefutationAssessment]` | Search across model failures and rival contrasts for defeaters, retaining the exact scope of implications that survive. |
| C | `routing_assessment`<br>`EvidentialDiscoveryRoutingAssessment` | `DiscoveryRoutingInput` → `Generated[DiscoveryRoutingAssessment]` | Calibrate a continue, pivot, or stop route from the hypothesis, empirical pattern, and bounded refutation result. |

#### Goal Oriented Discovery Development (`goal_oriented_discovery_development`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `control_discovery_goal`<br>`DiscoveryGoalControlJudgment` | `DiscoveryDevelopmentRequest` → `Generated[GoalOrientedControlPacket]` | DiscoveryDevelopmentRequest -> Generated[GoalOrientedControlPacket]: goal state, next actions, and stop conditions remain reviewable before HypothesisMemorySynthesis. |
| D | `curate_hypothesis_memory`<br>`HypothesisMemorySynthesis` | `GoalOrientedControlPacket` → `Generated[DiscoveryHypothesisMemory]` | GoalOrientedControlPacket -> Generated[DiscoveryHypothesisMemory]: active hypotheses, rejected hypotheses, and evidence links remain reviewable before DiscoveryNoveltyAssessment. |
| C | `assess_discovery_novelty`<br>`DiscoveryNoveltyAssessment` | `DiscoveryHypothesisMemory` → `Generated[DiscoveryNoveltyPowerAssessment]` | DiscoveryHypothesisMemory -> Generated[DiscoveryNoveltyPowerAssessment]: novelty status, supporting signals, and weaknesses remain reviewable before DeadEndPivotRecommendation. |
| C | `plan_dead_end_pivot`<br>`DeadEndPivotRecommendation` | `DiscoveryNoveltyPowerAssessment` → `Generated[DiscoveryDeadEndPivotPlan]` | DiscoveryNoveltyPowerAssessment -> Generated[DiscoveryDeadEndPivotPlan]: decision, pivot options, and discarded options remain reviewable before FrameworkGoalClosureJudgment. |
| C | `audit_discovery_closure`<br>`FrameworkGoalClosureJudgment` | `DiscoveryDeadEndPivotPlan` → `Generated[FrameworkGoalLoopClosureReport]` | DiscoveryDeadEndPivotPlan -> Generated[FrameworkGoalLoopClosureReport]: closure status, met criteria, and open issues remain reviewable before SkillMonotonicityJudgment. |
| C | `review_discovery_monotonicity`<br>`SkillMonotonicityJudgment` | `FrameworkGoalLoopClosureReport` → `Generated[SkillMonotonicityReview]` | FrameworkGoalLoopClosureReport -> Generated[SkillMonotonicityReview]: terminal fields classification, preserved contracts, and regression obligations remain visible for downstream decision or release review. |

#### Meta Feedback Skill Execution (`meta_feedback_skill_execution`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `assess_feedback_necessity`<br>`FeedbackNecessityJudgment` | `FrameworkFeedbackRequest` → `Generated[FeedbackNecessityAssessment]` | FrameworkFeedbackRequest -> Generated[FeedbackNecessityAssessment]: disposition, existing owners, and capability gaps remain reviewable before FeedbackSkillSpecificationSynthesis. |
| D | `specify_feedback_skill`<br>`FeedbackSkillSpecificationSynthesis` | `FeedbackNecessityAssessment` → `Generated[FeedbackSkillSpecification]` | FeedbackNecessityAssessment -> Generated[FeedbackSkillSpecification]: trigger contract, output contract, and validation requirements remain reviewable before FeedbackImplementationAccount. |
| D | `report_feedback_implementation`<br>`FeedbackImplementationAccount` | `FeedbackSkillSpecification` → `Generated[FeedbackImplementationReport]` | FeedbackSkillSpecification -> Generated[FeedbackImplementationReport]: changed surfaces, tests run, and residual risks remain reviewable before SkillMonotonicityJudgment. |
| C | `review_feedback_monotonicity`<br>`SkillMonotonicityJudgment` | `FeedbackImplementationReport` → `Generated[SkillMonotonicityReview]` | FeedbackImplementationReport -> Generated[SkillMonotonicityReview]: terminal fields classification, preserved contracts, and regression obligations remain visible for downstream decision or release review. |

#### Meta Framework Improvement (`meta_framework_improvement`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `route_framework_intent`<br>`FrameworkIntentClassification` | `MetaFrameworkChangeIntent` → `Generated[FrameworkIntentRoute]` | MetaFrameworkChangeIntent -> Generated[FrameworkIntentRoute]: intent classes, primary route, and next action remain reviewable before ExistingCapabilitySufficiencyAssessment. |
| C | `audit_existing_skill_sufficiency`<br>`ExistingCapabilitySufficiencyAssessment` | `FrameworkIntentRoute` → `Generated[ExistingSkillSufficiencyAudit]` | FrameworkIntentRoute -> Generated[ExistingSkillSufficiencyAudit]: coverage map, gap map, and sufficiency decision remain reviewable before ExternalKnowledgeNeedDecision. |
| C | `route_external_knowledge`<br>`ExternalKnowledgeNeedDecision` | `ExistingSkillSufficiencyAudit` → `Generated[ExternalKnowledgeSearchPlan]` | ExistingSkillSufficiencyAudit -> Generated[ExternalKnowledgeSearchPlan]: knowledge claims, search decision, and source classes remain reviewable before FrameworkWorkflowNoveltyJudgment. |
| C | `classify_workflow_novelty`<br>`FrameworkWorkflowNoveltyJudgment` | `ExternalKnowledgeSearchPlan` → `Generated[FrameworkWorkflowNoveltyDecision]` | ExternalKnowledgeSearchPlan -> Generated[FrameworkWorkflowNoveltyDecision]: novelty signals, decision, and rejected alternatives remain reviewable before FrameworkWorkflowDecompositionSynthesis. |
| D | `decompose_framework_workflow`<br>`FrameworkWorkflowDecompositionSynthesis` | `FrameworkWorkflowNoveltyDecision` → `Generated[FrameworkWorkflowDecomposition]` | FrameworkWorkflowNoveltyDecision -> Generated[FrameworkWorkflowDecomposition]: epistemic steps, ordered handoff, and artifact contracts remain reviewable before FrameworkTodoPlanningRecommendation. |
| D | `plan_skillset_todos`<br>`FrameworkTodoPlanningRecommendation` | `FrameworkWorkflowDecomposition` → `Generated[FrameworkSkillsetTodoPlan]` | FrameworkWorkflowDecomposition -> Generated[FrameworkSkillsetTodoPlan]: goal, ordered todos, and acceptance criteria remain reviewable before FrameworkHookIntegrationRecommendation. |
| D | `plan_workflow_hooks`<br>`FrameworkHookIntegrationRecommendation` | `FrameworkSkillsetTodoPlan` → `Generated[FrameworkWorkflowHookPlan]` | FrameworkSkillsetTodoPlan -> Generated[FrameworkWorkflowHookPlan]: stack id, stack order, and hook completeness checks remain reviewable before FrameworkAcceptanceCriteriaJudgment. |
| C | `elicit_success_criteria`<br>`FrameworkAcceptanceCriteriaJudgment` | `FrameworkWorkflowHookPlan` → `Generated[FrameworkSuccessCriteria]` | FrameworkWorkflowHookPlan -> Generated[FrameworkSuccessCriteria]: goal, deterministic criteria, and stop criteria remain reviewable before FrameworkValidationStrategyRecommendation. |
| D | `design_test_strategy`<br>`FrameworkValidationStrategyRecommendation` | `FrameworkSuccessCriteria` → `Generated[FrameworkTestStrategy]` | FrameworkSuccessCriteria -> Generated[FrameworkTestStrategy]: deterministic tests, generative probes, and test execution order remain reviewable before FrameworkImplementationAccountGeneration. |
| D | `report_todo_implementation`<br>`FrameworkImplementationAccountGeneration` | `FrameworkTestStrategy` → `Generated[FrameworkTodoImplementationReport]` | FrameworkTestStrategy -> Generated[FrameworkTodoImplementationReport]: implemented todos, changed files, and tests run remain reviewable before FrameworkImplementationCritique. |
| C | `review_implementation`<br>`FrameworkImplementationCritique` | `FrameworkTodoImplementationReport` → `Generated[FrameworkImplementationReview]` | FrameworkTodoImplementationReport -> Generated[FrameworkImplementationReview]: findings, supported claims, and loop closure readiness remain reviewable before FrameworkJudgmentQualityCritique. |
| C | `run_generative_validation`<br>`FrameworkJudgmentQualityCritique` | `FrameworkImplementationReview` → `Generated[FrameworkGenerativeValidationReport]` | FrameworkImplementationReview -> Generated[FrameworkGenerativeValidationReport]: probes run, quality findings, and unresolved judgments remain reviewable before FrameworkOutcomeAbduction. |
| R | `interpret_outcome_abductively`<br>`FrameworkOutcomeAbduction` | `FrameworkGenerativeValidationReport` → `Generated[FrameworkOutcomeAbductionReport]` | FrameworkGenerativeValidationReport -> Generated[FrameworkOutcomeAbductionReport]: observations, competing hypotheses, best explanation, and uncertainty remain reviewable before FrameworkRefinementRecommendation. |
| C | `orchestrate_refinement`<br>`FrameworkRefinementRecommendation` | `FrameworkOutcomeAbductionReport` → `Generated[FrameworkReflectionHistory]` | FrameworkOutcomeAbductionReport -> Generated[FrameworkReflectionHistory]: iteration limit, repairs made, remaining findings, and stop reason remain reviewable before FrameworkGoalClosureJudgment. |
| C | `audit_goal_loop_closure`<br>`FrameworkGoalClosureJudgment` | `FrameworkReflectionHistory` → `Generated[FrameworkGoalLoopClosureReport]` | FrameworkReflectionHistory -> Generated[FrameworkGoalLoopClosureReport]: unresolved items, closure gate, and recommended followup route remain reviewable before SkillMonotonicityJudgment. |
| C | `review_skill_monotonicity`<br>`SkillMonotonicityJudgment` | `FrameworkGoalLoopClosureReport` → `Generated[SkillMonotonicityReview]` | FrameworkGoalLoopClosureReport -> Generated[SkillMonotonicityReview]: terminal fields baseline contracts, proposed changes, and final guard decision remain visible for downstream decision or release review. |

#### Meta Second Order Framework Learning (`meta_second_order_framework_learning`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `route_second_order_learning`<br>`SecondOrderLearningClassification` | `CompletedFrameworkLoopEvidence` → `Generated[SecondOrderLearningRoute]` | CompletedFrameworkLoopEvidence -> Generated[SecondOrderLearningRoute]: route, evidence anchors, and restrictions remain reviewable before GoalCriteriaRefinement. |
| C | `refine_goal_criteria`<br>`GoalCriteriaRefinement` | `SecondOrderLearningRoute` → `Generated[SecondOrderGoalCriteria]` | SecondOrderLearningRoute -> Generated[SecondOrderGoalCriteria]: retained criteria, refined criteria, and rejected changes remain reviewable before EpistemicModelRefinement. |
| R | `refine_epistemic_model`<br>`EpistemicModelRefinement` | `SecondOrderGoalCriteria` → `Generated[SecondOrderEpistemicModel]` | SecondOrderGoalCriteria -> Generated[SecondOrderEpistemicModel]: retained assumptions, model refinements, and uncertainties remain reviewable before SkillEvolutionAssessment. |
| C | `detect_skill_evolution`<br>`SkillEvolutionAssessment` | `SecondOrderEpistemicModel` → `Generated[SecondOrderSkillEvolutionAssessment]` | SecondOrderEpistemicModel -> Generated[SecondOrderSkillEvolutionAssessment]: candidate changes, reuse options, and evidence gaps remain reviewable before CoreGoalDriftCritique. |
| C | `audit_core_goal_drift`<br>`CoreGoalDriftCritique` | `SecondOrderSkillEvolutionAssessment` → `Generated[CoreGoalDriftReport]` | SecondOrderSkillEvolutionAssessment -> Generated[CoreGoalDriftReport]: drift findings, preserved goals, and severity remain reviewable before DriftRemediationRecommendation. |
| D | `plan_drift_remediation`<br>`DriftRemediationRecommendation` | `CoreGoalDriftReport` → `Generated[DriftRemediationPlan]` | CoreGoalDriftReport -> Generated[DriftRemediationPlan]: repairs, validation obligations, and stop conditions remain reviewable before SkillMonotonicityJudgment. |
| C | `review_second_order_monotonicity`<br>`SkillMonotonicityJudgment` | `DriftRemediationPlan` → `Generated[SkillMonotonicityReview]` | DriftRemediationPlan -> Generated[SkillMonotonicityReview]: terminal fields classification, preserved contracts, and regression obligations remain visible for downstream decision or release review. |

#### Multisolver Coherence (`multisolver_coherence`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `admitted_payload`<br>`EvidentialSolverPayloadAdmission` | `MultisolverCoherenceRequest` → `Generated[AdmittedSolverPayload]` | Admit typed premises and a solver route while preserving rejected or unsupported inputs. |
| R | `materialized_consequences`<br>`DeductiveConsequenceMaterialization` | `AdmittedSolverPayload` → `Generated[MaterializedConsequences]` | Derive explicit consequences under the admitted premises and rules before solver synthesis. |
| R | `solver_result`<br>`ModelBasedSolverSynthesis` | `SolverSynthesisInput` → `Generated[TypedSolverResult]` | Synthesize a typed solver result from both the admitted payload and its explicit consequences. |
| C | `coherence_verdict`<br>`RefutationalSolverCoherenceReview` | `SolverCoherenceReviewInput` → `Generated[SolverCoherenceVerdict]` | Search for conflicts, omissions, and repair obligations by comparing the solver result with materialized consequences. |
| C | `inference_status`<br>`EvidentialInferenceStatusCalibration` | `MultisolverCalibrationInput` → `Generated[MultisolverInferenceStatus]` | Classify admitted, repaired, or blocked status from the solver result and coherence verdict. |

#### Oncology Usecase Skill Gap Planning (`oncology_usecase_skill_gap_planning`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| C | `critique_usecase_skill_gaps`<br>`UseCaseCapabilityGapCritique` | `OncologyUseCaseRequest` → `Generated[OncologyUseCaseSkillGapReview]` | OncologyUseCaseRequest -> Generated[OncologyUseCaseSkillGapReview]: covered needs, capability gaps, and blocked claims remain reviewable before PreclosureGapForecast. |
| C | `forecast_preclosure_gaps`<br>`PreclosureGapForecast` | `OncologyUseCaseSkillGapReview` → `Generated[PreclosureEvidenceGapForecast]` | OncologyUseCaseSkillGapReview -> Generated[PreclosureEvidenceGapForecast]: expected gaps, closure risks, and required evidence remain reviewable before GapDrivenSkillsetRecommendation. |
| D | `plan_gap_driven_skillset`<br>`GapDrivenSkillsetRecommendation` | `PreclosureEvidenceGapForecast` → `Generated[GapDrivenSkillsetPlan]` | PreclosureEvidenceGapForecast -> Generated[GapDrivenSkillsetPlan]: reuse actions, extension actions, and new skill actions remain reviewable before SkillEvolutionRecommendation. |
| D | `plan_gap_triggered_evolution`<br>`SkillEvolutionRecommendation` | `GapDrivenSkillsetPlan` → `Generated[GapTriggeredSkillEvolutionPlan]` | GapDrivenSkillsetPlan -> Generated[GapTriggeredSkillEvolutionPlan]: ordered changes, tests, and stop conditions remain reviewable before SkillMonotonicityJudgment. |
| C | `review_usecase_monotonicity`<br>`SkillMonotonicityJudgment` | `GapTriggeredSkillEvolutionPlan` → `Generated[SkillMonotonicityReview]` | GapTriggeredSkillEvolutionPlan -> Generated[SkillMonotonicityReview]: terminal fields classification, preserved contracts, and regression obligations remain visible for downstream decision or release review. |

#### Cross Tumor (`cross_tumor`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_contexts`<br>`EvidentialTumorContextBounding` | `CrossTumorCircuitRequest` → `Generated[BoundedTumorContexts]` | Bound the public sources and tumor contexts before making any cross-tumor comparison. |
| R | `circuit_pattern`<br>`InductiveCrossTumorCircuitInference` | `BoundedTumorContexts` → `Generated[CrossTumorCircuitPattern]` | Induce a recurring circuit pattern from only the admitted tumor contexts and sources. |
| R | `concordance_assessment`<br>`AnalogicalCrossTumorConcordance` | `CrossTumorConcordanceInput` → `Generated[CrossTumorConcordanceAssessment]` | Compare how the induced circuit corresponds across bounded tumors while retaining divergence and transport limits. |
| R | `circuit_model`<br>`ModelBasedCrossTumorCircuitConstruction` | `CrossTumorModelInput` → `Generated[CrossTumorCircuitModel]` | Construct a mechanistic circuit model that preserves both the induced pattern and observed cross-tumor divergence. |
| C | `validity_verdict`<br>`RefutationalCrossTumorValidityReview` | `CrossTumorValidityInput` → `Generated[CrossTumorExternalValidityVerdict]` | Seek external-validity defeaters by testing the model against discordant and context-limited findings. |
| C | `claim_status`<br>`EvidentialCrossTumorClaimCalibration` | `CrossTumorCalibrationInput` → `Generated[CrossTumorClaimStatus]` | Calibrate a transport-bounded claim from the model and its external-validity verdict. |

#### Melanoma Resistance (`melanoma_resistance`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `bounded_scope`<br>`EvidentialMelanomaScopeBounding` | `MelanomaResistanceRequest` → `Generated[BoundedMelanomaScope]` | Bound public evidence, melanoma context, and therapy setting before inferring resistance biology. |
| R | `program_pattern`<br>`InductiveResistanceProgramInference` | `BoundedMelanomaScope` → `Generated[MelanomaResistanceProgramPattern]` | Induce a resistance-program pattern from admitted observations while retaining gaps and context limits. |
| R | `ranked_targets`<br>`ModelBasedResistanceTargetRanking` | `MelanomaResistanceProgramPattern` → `Generated[RankedMelanomaResistanceTargets]` | Probe the program as a mechanistic model to rank targets with grounds, uncertainties, and alternatives. |
| C | `pressure_verdict`<br>`RefutationalResistanceProgramReview` | `MelanomaResistancePressureInput` → `Generated[MelanomaResistancePressureVerdict]` | Test the program and ranking together for counterevidence, bypass mechanisms, and required revisions. |
| C | `claim_status`<br>`EvidentialMelanomaClaimCalibration` | `MelanomaResistanceCalibrationInput` → `Generated[MelanomaResistanceClaimStatus]` | Calibrate the resistance claim from the program, ranked targets, and pressure verdict without exceeding public evidence. |

### Hardware Verification

#### Sva Generator (`sva_generator`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `extract_semantic_model`<br>`ExtractSvaSemanticModel` | `SvaGenerationRequest` → `Generated[SvaSemanticModel]` | Ground symbols, timing, relationships, and semantic intent before generation. Sample output: sample_outputs.prism::extract_semantic_model_sample_output |
| C | `generate_and_assess_candidate`<br>`GenerateAndAssessSvaCandidate` | `SvaSemanticModel` → `Generated[SvaCandidateAssessment]` | Generate the candidate SVA package and assess whether refinement is required. Sample output: sample_outputs.prism::generate_and_assess_candidate_sample_output |
| C | `critique_and_route_refinement`<br>`CritiqueAndRouteSvaRefinement` | `SvaCandidateAssessment` → `Generated[SvaRefinementDisposition]` | Critique, localize, refine, and represent the bounded dynamic rerouting decision. Sample output: sample_outputs.prism::critique_and_route_refinement_sample_output |
| D | `finalize_sva_package`<br>`FinalizeSvaPackage` | `SvaRefinementDisposition` → `Generated[SvaPackage]` | Publish the generated SVA package with its final assessment boundary. Sample output: sample_outputs.prism::finalize_sva_package_sample_output |

#### Sva Generator Complex (`sva_generator_complex`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `establish_design_evidence`<br>`GroundSvaEvidence` | `SvaVerificationRequest` → `Generated[SvaEvidenceModel]` | Unify source facts, circuit mechanisms, temporal contracts, and testability pressure before assertion design. Sample output: sample_outputs.prism::establish_design_evidence_sample_output |
| D | `generate_assertion_portfolio`<br>`PlanAndGenerateAssertions` | `SvaEvidenceModel` → `Generated[GeneratedAssertionPortfolio]` | Turn grounded evidence and explicit verification pressure into a positioned assertion strategy and generated bundle. Sample output: sample_outputs.prism::generate_assertion_portfolio_sample_output |
| C | `validate_assertion_portfolio`<br>`ValidateAssertionSemantics` | `GeneratedAssertionPortfolio` → `Generated[ValidatedAssertionPortfolio]` | Validate syntax, temporality, reachability, contextual fidelity, emulator limits, and artifact consistency. Sample output: sample_outputs.prism::validate_assertion_portfolio_sample_output |
| D | `assess_assertion_testability`<br>`DesignAssertionGuidedTests` | `ValidatedAssertionPortfolio` → `Generated[AssertionGuidedTestEvidence]` | Design scenarios, independent oracles, temporal episodes, execution routing, and quality review against validated assertions. Sample output: sample_outputs.prism::assess_assertion_testability_sample_output |
| C | `critique_assertion_portfolio`<br>`CritiqueAssertionPortfolio` | `ValidatedAssertionPortfolio` → `Generated[IndependentCriticFindings]` | Challenge traceability, temporal ownership, vacuity, portability, and resilience independently of test-scenario construction. Sample output: sample_outputs.prism::critique_assertion_portfolio_sample_output |
| C | `synthesize_refinement_closure`<br>`SynthesizeReflectionClosure` | `ClosureSynthesisInput` → `Generated[RefinedClosureEvidence]` | Join validation, test evidence, and critic findings before reflective localization, bounded refinement, and repair audit. Sample output: sample_outputs.prism::synthesize_refinement_closure_sample_output |
| D | `finalize_verification_package`<br>`FinalizeVerificationPackage` | `RefinedClosureEvidence` → `Generated[SvaVerificationPackage]` | Publish the reviewed assertions, test evidence, critic findings, and residual closure limits. Sample output: sample_outputs.prism::finalize_verification_package_sample_output |

#### Verification Debug Diagnosis (`verification_debug_diagnosis`)

| Class | Occurrence / method | Typed transformation | Authored function evidence |
|---|---|---|---|
| O | `intake_and_normalize_debug_evidence`<br>`IntakeAndNormalizeDebugEvidence` | `DebugDiagnosisRequest` → `Generated[DebugEvidenceIntake]` | Inventory, anticipate, and normalize the supplied debug evidence. Sample output: sample_outputs.prism::intake_and_normalize_debug_evidence_sample_output |
| O | `represent_and_detect_debug_findings`<br>`RepresentAndDetectDebugFindings` | `DebugEvidenceIntake` → `Generated[DebugFindingSet]` | Build typed representations and detect evidence-supported findings. Sample output: sample_outputs.prism::represent_and_detect_debug_findings_sample_output |
| R | `diagnose_and_plan_debug_probes`<br>`DiagnoseAndPlanDebugProbes` | `DebugFindingSet` → `Generated[DebugDiagnosisSynthesis]` | Synthesize the diagnosis, discriminating probes, and epistemic review. Sample output: sample_outputs.prism::diagnose_and_plan_debug_probes_sample_output |
| D | `finalize_debug_diagnosis`<br>`FinalizeDebugDiagnosis` | `DebugDiagnosisSynthesis` → `Generated[DebugDiagnosticPackage]` | Publish the calibrated debug diagnosis and retained evidence limits. Sample output: sample_outputs.prism::finalize_debug_diagnosis_sample_output |
