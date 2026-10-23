# Canonical causal inference and uncertainty quantification extension

Status: proposal for review; not yet incorporated into `taxonomy.md` or
`taxonomy.json`

## Purpose and boundary

This proposal extends the Prism component taxonomy with canonical categories
for causal inference and uncertainty quantification (UQ). It is intentionally
broader than the current workflow corpus. Categories may be retained as
well-defined extension points even when no current occurrence instantiates
them.

The extension keeps four questions separate:

1. **Causal reasoning:** what causal epistemic move licenses a claim?
2. **Causal computation:** what formal or numerical causal task is executed?
3. **Statistical inference:** what population or stochastic claim is inferred
   from data, and under which inferential paradigm?
4. **Uncertainty quantification:** how is uncertainty represented, decomposed,
   estimated, propagated, checked, or reported?

These are orthogonal facets. Running a causal-discovery algorithm is not by
itself a warranted causal conclusion. Calling a graph causal is not causal
discovery. Mentioning uncertainty is not UQ. An epistemic release label such as
“provisional” is not a probability, interval, or calibrated forecast.

## Identifier and status policy

- The strings in the **ID** columns are stable identifiers. Their spelling and
  meaning must not be silently reused; a replacement receives a new ID and the
  old one is deprecated with a mapping.
- Dotted prefixes identify facets, not an inheritance claim by themselves.
- `parent` gives the proposed taxonomic parent. Multiple inheritance is handled
  through co-labels rather than duplicate parentage.
- Corpus status is one of `supported`, `candidate`, or `absent`:
  - `supported`: an authored occurrence contract directly supports the class;
  - `candidate`: current wording suggests it, but required semantics are not
    sufficiently authored;
  - `absent`: no current occurrence supplies the inclusion evidence.

## A. Causal reasoning archetypes

These labels extend the existing `reasoning` facet. They classify an epistemic
move, not merely a procedure or subject matter.

| ID | Parent | Definition | Include when | Exclude when |
| --- | --- | --- | --- | --- |
| `reasoning.causal` | `reasoning` | Infers, explains, evaluates, or predicts using directional cause–effect commitments. | A causal model or explicit intervention/counterfactual assumptions license the conclusion. | Association, temporal order, a directed graph, or causal vocabulary is the only evidence. |
| `reasoning.causal.structure` | `reasoning.causal` | Infers which variables are causally related and in what direction. | The conclusion asserts causal adjacency, orientation, or equivalence under stated assumptions. | The component only constructs a supplied graph or finds predictive dependencies. |
| `reasoning.causal.interventional` | `reasoning.causal` | Infers consequences of setting or manipulating a variable. | The query and conclusion distinguish `do(X=x)` or an equivalent intervention from observation. | Ordinary conditional prediction or action recommendation lacks an intervention semantics. |
| `reasoning.causal.counterfactual` | `reasoning.causal` | Infers what would have occurred in an alternative world for the same unit or context. | Factual evidence is combined with a structural causal model or explicit potential-outcome semantics. | Scenario generation, hypothetical prose, or prospective intervention effects alone. |
| `reasoning.causal.attribution` | `reasoning.causal` | Attributes an observed event or outcome to a cause in its actual context. | Actual causation, necessity/sufficiency, probability of causation, or a comparable attribution criterion is explicit. | Population average effects or a narrative statement that one event preceded another. |
| `reasoning.causal.mediation` | `reasoning.causal` | Decomposes or explains an effect through mediating pathways. | Direct, indirect, path-specific, or mediator-dependent effects are defined under explicit assumptions. | “Mediator” means a conceptual bridge, intermediary artifact, or informal mechanism only. |
| `reasoning.causal.transport` | `reasoning.causal` | Infers whether and how causal conclusions carry to a target population or environment. | Source/target populations, selection differences, and transport assumptions are explicit. | Analogical transfer, external-validity review, or cross-context similarity without a causal transport model. |
| `reasoning.mechanistic` | `reasoning` | Explains behavior through organized entities, activities, and productive relations over conditions or time. | The account states components, activities, organization, and how they produce the phenomenon. | A biological subject, pathway vocabulary, correlation graph, or component list alone. |
| `reasoning.causal.mechanistic` | `reasoning.causal` | Uses an explicit productive mechanism as the causal license for an explanation or prediction. | Mechanistic organization supports a directional causal claim, intervention consequence, or failure explanation. | A mechanism is described without a causal conclusion, or a causal effect is estimated without a mechanistic account. |

### Causal reasoning decision test

Assign a `reasoning.causal.*` label only if all applicable questions are
answerable from authored material:

1. What is the causal query: structure, effect, intervention, counterfactual,
   attribution, mediation, or transport?
2. What causal model or semantics defines that query?
3. Which assumptions license the move (for example, no unmeasured confounding,
   consistency, positivity, exclusion, invariance, or structural equations)?
4. What output is causal rather than merely associational or predictive?

Mechanistic reasoning uses a related but distinct test: the entities,
activities, organization, and productive relation must be recoverable. It can
be co-labeled with causal reasoning, but neither label entails the other.

## B. Causal-computation operations

These labels belong to an operational/method facet. They say what is computed;
they do not certify that the computation's assumptions are true or that its
output warrants belief.

| ID | Parent | Definition | Include when | Exclude when |
| --- | --- | --- | --- | --- |
| `operation.causal` | `operation` | Executes a method whose inputs and outputs are defined by an explicit causal formalism. | The causal model, query, and relevant assumptions are declared. | Generic graph, simulation, regression, or optimization code. |
| `operation.causal.discovery` | `operation.causal` | Learns causal adjacencies, orientations, or equivalence classes from data and/or interventions. | A structure-learning objective and assumptions such as faithfulness, acyclicity, or invariance are explicit. | Dependency discovery, feature importance, graph extraction, or manually authored structure. |
| `operation.causal.discovery.constraint-based` | `operation.causal.discovery` | Learns structure using conditional-independence constraints. | The independence tests and orientation rules are part of the method. | Any graph learner merely produces a DAG. |
| `operation.causal.discovery.score-based` | `operation.causal.discovery` | Searches causal structures using an explicit score and graph constraints. | The score, search space, and structural assumptions are specified. | Predictive model selection without causal structure semantics. |
| `operation.causal.discovery.functional` | `operation.causal.discovery` | Uses functional/noise restrictions to orient causes. | An additive-noise, non-Gaussian, nonlinear, temporal, or related identifiable functional model is explicit. | Structural equations are used only for simulation with fixed directions. |
| `operation.causal.discovery.invariance-based` | `operation.causal.discovery` | Learns causal structure from stability or change across environments. | Environment/intervention variation and invariance assumptions drive orientation or parent selection. | Ordinary cross-domain validation or transport review. |
| `operation.causal.identification` | `operation.causal` | Determines whether a causal estimand is uniquely expressible from available observational/interventional distributions. | The estimand, causal graph/model, observed data regime, and identification result are explicit. | Computing an estimate, choosing covariates heuristically, or claiming that adjustment “controls for” confounding. |
| `operation.causal.identification.adjustment` | `operation.causal.identification` | Derives a valid adjustment set or adjustment formula. | Back-door/generalized adjustment criteria and the resulting estimand are explicit. | Regression includes covariates without an identification argument. |
| `operation.causal.identification.front-door` | `operation.causal.identification` | Identifies an effect through a front-door mediator structure. | The front-door graph and its assumptions are explicit. | Any mediation analysis. |
| `operation.causal.identification.instrumental-variable` | `operation.causal.identification` | Identifies an effect using an instrument and its assumptions. | Relevance, exclusion, independence/exogeneity, and target estimand are stated. | A variable is merely called an instrument or predictor. |
| `operation.causal.identification.do-calculus` | `operation.causal.identification` | Transforms interventional expressions using do-calculus or an equivalent complete identification algorithm. | The derivation operates on causal distributions and returns an identifying functional or non-identifiability result. | Symbolic probability manipulation without intervention semantics. |
| `operation.causal.effect-estimation` | `operation.causal` | Numerically estimates an identified causal effect. | Estimand, identification strategy, estimator, uncertainty, and target population are explicit. | Association, prediction, effect-size reporting without causal identification, or identification without estimation. |
| `operation.causal.effect-estimation.heterogeneous` | `operation.causal.effect-estimation` | Estimates conditional, subgroup, or individual treatment-effect heterogeneity. | CATE/ITE or an equivalent conditional causal estimand is explicit. | Subgroup prediction or descriptive stratification. |
| `operation.causal.intervention-evaluation` | `operation.causal` | Evaluates outcomes under a specified intervention or policy. | Intervention, comparator, outcome, horizon, and causal semantics are explicit. | Recommendation, optimization, or simulation with no causal interpretation. |
| `operation.causal.policy-learning` | `operation.causal.intervention-evaluation` | Learns an intervention policy to optimize a causal utility or outcome. | Policy value and off-policy/experimental assumptions are defined. | Generic decision routing or reinforcement learning without a causal estimand. |
| `operation.causal.counterfactual-inference` | `operation.causal` | Computes unit/context-level counterfactual outcomes via abduction, action, and prediction or an equivalent formal semantics. | Factual observations and a structural/potential-outcome model define the alternative-world query. | What-if simulation on a model that is not interpreted counterfactually. |
| `operation.causal.mediation-analysis` | `operation.causal` | Estimates direct, indirect, or path-specific causal effects. | Mediator intervention semantics and identification assumptions are explicit. | Correlational path analysis or informal mediation language. |
| `operation.causal.transportability` | `operation.causal` | Identifies or estimates a causal quantity in a target domain using source-domain information. | Selection diagrams, domain indicators, invariance assumptions, or equivalent transport formulas are explicit. | Domain adaptation, analogy, transfer learning, or external-validity critique alone. |
| `operation.causal.mechanism-modeling` | `operation.causal` | Encodes and interrogates productive causal mechanisms. | State transitions, structural equations, reaction/process relations, or comparable mechanism semantics answer a causal query. | A mechanistic diagram is only assembled or narrated. |

### Identification is not estimation

`operation.causal.identification` answers whether and how an estimand can be
expressed from an available data regime. `operation.causal.effect-estimation`
computes a value for that estimand from finite data. They should be separate
labels even if one component performs both. A numerical result without an
identification argument is not promoted to causal effect estimation.

## C. Probabilistic and statistical inference

These are reasoning archetypes when the output changes epistemic commitment;
the algorithm used should additionally receive an operational label.

| ID | Parent | Definition | Include when | Exclude when |
| --- | --- | --- | --- | --- |
| `reasoning.probabilistic` | `reasoning` | Draws or updates a conclusion using an explicit probability model or calculus. | Probabilities, likelihoods, distributions, or probabilistic graphical semantics license the conclusion. | Ranked alternatives, qualitative uncertainty, confidence language, or stochastic generation alone. |
| `reasoning.statistical` | `reasoning` | Infers properties of a population or data-generating process from sampled or noisy observations. | An estimand/hypothesis, sampling or generative assumptions, and a statistical procedure are recoverable. | Descriptive summaries, pattern recognition, or empirical claims without inferential procedure. |
| `reasoning.statistical.bayesian` | `reasoning.statistical` | Updates uncertainty about parameters, latent states, models, or predictions using prior and likelihood. | Prior, likelihood, conditioning data, and posterior target are explicit. | Subjective confidence or Bayes-like language without a Bayesian model. |
| `reasoning.statistical.frequentist` | `reasoning.statistical` | Uses repeated-sampling properties of estimators, tests, or confidence procedures. | Estimator/test, sampling model, target, and error or coverage criterion are explicit. | A confidence score, neural-network confidence, or credible interval. |
| `reasoning.statistical.likelihood-based` | `reasoning.statistical` | Uses likelihood comparison or optimization as the inferential license. | Likelihood and target parameters/models are explicit. | A loss function is informally called likelihood. |
| `reasoning.statistical.predictive` | `reasoning.statistical` | Infers a predictive distribution or statistically qualified future outcome. | Predictive target, data-generating assumptions, and out-of-sample uncertainty are explicit. | Point prediction or scenario generation without statistical uncertainty. |

Bayesian and frequentist labels identify inferential paradigms, not software
implementations. A Bayesian computation is also probabilistic; a frequentist
procedure receives `reasoning.probabilistic` only when probability calculus is
part of the occurrence's expressed epistemic move rather than merely a
background mathematical justification.

## D. Uncertainty quantification operations

UQ labels require an explicit uncertain quantity and a representation or
diagnostic. “Uncertain,” “tentative,” “bounded,” “needs review,” and “low
confidence” do not suffice.

| ID | Parent | Definition | Include when | Exclude when |
| --- | --- | --- | --- | --- |
| `operation.uq` | `operation` | Represents, estimates, decomposes, propagates, validates, or reports uncertainty in a quantity or model output. | The uncertain target and formal representation/diagnostic are explicit. | Qualitative caveats, epistemic status, evidence limitations, or workflow confidence only. |
| `operation.uq.characterization` | `operation.uq` | Specifies sources, representation, and magnitude of uncertainty. | An uncertain variable/parameter/model and its distribution, set, interval, or membership semantics are explicit. | A limitations list without quantified or formalized uncertainty. |
| `operation.uq.decomposition` | `operation.uq` | Separates distinguishable sources or contributions to uncertainty. | A defined decomposition attributes uncertainty to data, parameters, model form, measurement, or other sources. | Merely naming aleatoric and epistemic uncertainty. |
| `operation.uq.propagation` | `operation.uq` | Propagates input, parameter, or model uncertainty through a transformation or model. | An input uncertainty representation and output uncertainty result are both explicit. | Deterministic sensitivity analysis or repeated simulation with no uncertainty measure. |
| `operation.uq.calibration` | `operation.uq` | Tests or adjusts probabilistic forecasts so stated probabilities agree with observed frequencies under a declared protocol. | Forecast probabilities/distributions, outcomes, and reliability/calibration criterion are explicit. | Prism epistemic claim calibration, model-parameter calibration, threshold tuning, or equipment calibration. |
| `operation.uq.coverage-validation` | `operation.uq` | Evaluates whether intervals or prediction sets attain intended coverage. | Nominal and empirical/guaranteed coverage plus the sampling or exchangeability regime are explicit. | General model validation or an interval displayed without coverage semantics. |
| `operation.uq.sensitivity` | `operation.uq` | Quantifies how results change under perturbations to inputs, parameters, assumptions, missingness, or unmeasured confounding. | Perturbation space and effect on a target quantity are measured. | Refutational review or qualitative “what if” discussion alone. |
| `operation.uq.robustness` | `operation.uq` | Establishes stability of a conclusion over a declared uncertainty or model class. | The admissible perturbation/model class and stability criterion are explicit. | Informal robustness language or a single alternative specification. |
| `operation.uq.interval-construction` | `operation.uq` | Constructs an interval or set with explicit semantics. | Endpoints/set, target, construction method, and interpretation are authored. | Any numeric range, engineering tolerance, search bound, or min/max summary. |
| `operation.uq.model-averaging` | `operation.uq` | Integrates predictions or parameter claims across models while retaining model uncertainty. | Model weights/set and uncertainty combination rule are explicit. | Ensemble voting that reports only a point result. |
| `operation.uq.decision-under-uncertainty` | `operation.uq` | Selects an action using explicit uncertainty and utility/loss or risk constraints. | Actions, uncertain outcomes, preferences/loss, and decision rule are defined. | Workflow routing based on qualitative readiness or unsupported confidence. |

## E. Uncertainty source and representation facets

These labels describe what uncertainty means and how it is encoded. They are
not reasoning archetypes.

### Source of uncertainty

| ID | Parent | Include test | Important exclusion |
| --- | --- | --- | --- |
| `uncertainty.source.aleatoric` | `uncertainty.source` | Irreducible variability/noise in the modeled data-generating process is represented. | “Random” generation or observed disagreement alone. |
| `uncertainty.source.epistemic` | `uncertainty.source` | Reducible uncertainty due to limited knowledge, data, parameters, or model choice is represented. | Prism epistemic status or a statement that evidence is incomplete. |
| `uncertainty.source.parameter` | `uncertainty.source.epistemic` | Uncertainty over model parameters is estimated or propagated. | Parameter variation used only for optimization. |
| `uncertainty.source.model-form` | `uncertainty.source.epistemic` | Alternative model structures/specifications contribute explicitly to uncertainty. | Comparing models only by score. |
| `uncertainty.source.measurement` | `uncertainty.source` | Observation/instrument error is modeled. | Data-quality notes without an error model. |
| `uncertainty.source.sampling` | `uncertainty.source` | Finite-sample variability is represented by a sampling distribution, resampling, or equivalent. | Dataset incompleteness described qualitatively. |
| `uncertainty.source.numerical` | `uncertainty.source` | Approximation, discretization, solver, or floating-point error is quantified. | Runtime failure or solver disagreement without an error estimate. |
| `uncertainty.source.structural-causal` | `uncertainty.source.epistemic` | Uncertainty over causal graph, identification assumptions, or structural functions is represented. | A list of causal caveats. |

Aleatoric and epistemic are modeling judgments, not intrinsic labels attached to
a variable forever. The same variation can be treated differently under a
different model or information state; therefore record the declared modeling
context.

### Representation of uncertainty

| ID | Parent | Include test | Important exclusion |
| --- | --- | --- | --- |
| `uncertainty.representation.distribution` | `uncertainty.representation` | A normalized probability distribution over a declared quantity is provided. | Scores that do not have probability semantics. |
| `uncertainty.representation.likelihood` | `uncertainty.representation` | A likelihood function over parameters/models for observed data is provided. | Any optimization objective. |
| `uncertainty.representation.posterior` | `uncertainty.representation.distribution` | A posterior distribution conditional on stated evidence is provided. | A confidence distribution or normalized score. |
| `uncertainty.representation.standard-error` | `uncertainty.representation` | Sampling variability of an estimator is represented by a standard error. | Standard deviation of observations. |
| `uncertainty.representation.confidence-interval` | `uncertainty.representation` | A frequentist interval procedure with stated target and coverage level is used. | Bayesian credible intervals and informal confidence ranges. |
| `uncertainty.representation.credible-interval` | `uncertainty.representation` | A posterior-probability interval with stated target and probability mass is used. | Frequentist confidence intervals. |
| `uncertainty.representation.prediction-interval` | `uncertainty.representation` | An interval/set targets a future observation or outcome under stated coverage/probability semantics. | Parameter intervals or heuristic forecast ranges. |
| `uncertainty.representation.deterministic-bounds` | `uncertainty.representation` | Proven or assumed lower/upper bounds contain the target under declared conditions. | Confidence intervals, min/max observations, or workflow scope bounds. |
| `uncertainty.representation.imprecise-probability` | `uncertainty.representation` | Sets of probabilities, lower/upper probabilities, credal sets, belief functions, or possibility measures encode partial probabilistic knowledge. | A single probability distribution or an arbitrary numeric interval. |
| `uncertainty.representation.fuzzy-membership` | `uncertainty.representation` | Graded membership in a vague set is represented by a membership function. | Probability of an event, model confidence, or scalar similarity. |
| `uncertainty.representation.ensemble` | `uncertainty.representation` | Variation across an explicitly defined ensemble represents uncertainty. | Multiple candidates are generated but disagreement is not interpreted or quantified. |

Imprecise probability and fuzzy membership must remain distinct. Imprecise
probability represents incomplete knowledge about probabilities; fuzzy sets
represent graded category membership or vagueness. Neither is a synonym for
“unclear.”

## Co-label policy

1. **Reasoning and operation may co-occur.** A component that derives an
   identified causal estimand can receive both `reasoning.causal` and
   `operation.causal.identification`. A utility that merely executes a supplied
   adjustment formula receives the operation label, not automatically the
   reasoning label.
2. **Causal discovery is not generic causal reasoning by default.** Co-label
   `reasoning.causal.structure` only when the occurrence interprets the learned
   equivalence class/graph as a causal conclusion under explicit assumptions.
3. **Identification and estimation are independent.** Assign both only when the
   component both derives an identifying functional and estimates it. Otherwise
   retain the narrower label.
4. **Mechanistic and causal are independent.** A productive mechanistic
   explanation may be `reasoning.mechanistic` plus
   `reasoning.causal.mechanistic`; a causal estimate can lack a mechanism, and a
   mechanism inventory can avoid causal inference.
5. **Transport has three meanings.** Use existing analogical/transport reasoning
   for correspondence-based transfer, `reasoning.causal.transport` for a causal
   epistemic conclusion, and `operation.causal.transportability` for a formal
   transport computation. Do not infer either causal label from “cross-domain.”
6. **Bayesian is statistical and usually probabilistic.** Assign
   `reasoning.statistical.bayesian` with `reasoning.probabilistic` when a
   posterior update licenses the conclusion. Do not assign it to subjective
   confidence statements.
7. **UQ operations require representation labels.** Every `operation.uq.*`
   annotation should name at least one uncertain target and normally one
   `uncertainty.representation.*` label. Sensitivity/robustness may instead name
   an explicit perturbation set and response measure.
8. **UQ calibration is not epistemic calibration.** Existing Prism
   `epistemic-calibration` assigns qualitative claim status or a release ceiling.
   `operation.uq.calibration` tests numerical probabilistic reliability. They
   may co-occur only if both outputs are genuinely produced.
9. **Uncertainty source is not uncertainty method.** “Aleatoric” and
   “epistemic” state a modeled source; add propagation, decomposition,
   calibration, or another UQ operation only when it is performed.
10. **Causal UQ composes explicitly.** A causal effect with a confidence or
    credible interval receives causal effect-estimation, the corresponding
    statistical paradigm, interval-construction, and the specific interval
    representation. None subsumes the others.

## Corpus status

The review target is the current 152-occurrence, 33-workflow corpus described in
`taxonomy/mapping-report.md`. This proposal does not remap those occurrences.

| Proposed area | Status | Corpus evidence and decision |
| --- | --- | --- |
| Mechanistic reasoning | `supported` | `ModelBasedCrossTumorCircuitConstruction`, `ModelBasedResistanceTargetRanking`, `RefutationalResistanceProgramReview`, `GroundSvaEvidence`, and `DiagnoseAndPlanDebugProbes` contain authored mechanistic cues. Existing mappings already use `causal_mechanistic`, although future review should separate the two dimensions. |
| Generic causal reasoning | `candidate` | `ModelBasedContextualGraphConstruction` emits a `ContextualCausalGraphAssessment`, and several oncology/hardware occurrences use causal or mechanistic language. The current contracts do not expose a causal query plus identification assumptions strongly enough for automatic promotion. |
| Causal discovery / structure learning | `absent` | No occurrence authors a structure-learning objective, conditional-independence regime, causal score, functional-noise assumptions, or learned equivalence class. Graph construction is not discovery. |
| Causal identification | `absent` | No explicit causal estimand, adjustment criterion, instrument, do-calculus derivation, or identifiability result is authored. |
| Causal effect estimation | `absent` | No ATE/CATE/ITE or equivalent estimand-estimator contract is authored. Target ranking is not effect estimation. |
| Intervention evaluation / policy learning | `absent` | Existing routing and planning select workflow actions, not interventions under a causal model. |
| Counterfactual reasoning/computation | `absent` | `ContrastiveDiscoveryHypothesisProbe` and the `counterfactual-route-prober` skill name suggest contrastive probing, but no occurrence contract defines a same-unit alternative-world quantity. |
| Causal mediation | `absent` | `AbductiveMediationHypothesisFormation` concerns conceptual mediation, not natural direct/indirect effects or a causal mediator estimand. |
| Causal transportability | `absent` | `AnalogicalGraphTransportAssessment` and cross-tumor concordance assess bounded correspondence/external validity, but do not author selection diagrams or a transport formula. Keep their current analogical labels. |
| Probabilistic inference | `absent` | No explicit probability distribution, likelihood, posterior, probabilistic graph, or probability-calculus output is authored. |
| Statistical inference | `absent` | Inductive pattern formation occurs, but no estimator, sampling model, hypothesis test, or inferential target is authored. |
| Bayesian / frequentist inference | `absent` | No prior-likelihood-posterior contract, repeated-sampling procedure, test, p-value, confidence procedure, or coverage target appears. |
| Quantitative UQ | `absent` | The corpus retains uncertainties and claim ceilings qualitatively, but does not estimate, propagate, decompose, or formally represent uncertainty. |
| UQ calibration | `absent` | Current “calibration” labels are epistemic release/status judgments. They must not be relabeled as probabilistic reliability calibration. |
| Sensitivity / robustness analysis | `candidate` | Refutational pressure, alternative probes, and external-validity critique test fragility qualitatively. No perturbation space and quantitative response measure are authored. |
| Aleatoric / epistemic decomposition | `absent` | “Epistemic” is used for claim status and model refinement, not a quantified decomposition of predictive uncertainty. |
| Confidence/credible/prediction intervals | `absent` | Current bounds refer to evidence or workflow scope, not interval procedures with probability or coverage semantics. |
| Deterministic bounds | `candidate` | Some formal contracts may impose exact constraints, but no current occurrence is annotated as a UQ operation producing guaranteed bounds on an uncertain target. |
| Imprecise probability / fuzzy uncertainty | `absent` | No credal set, lower/upper probability, belief/possibility measure, or fuzzy membership function is authored. |

## Minimal annotation evidence

Future Prism occurrences should expose enough fields to justify these labels.
At minimum:

- causal task: query/estimand, causal model, assumptions, data regime,
  identification result, estimator (if any), and target population;
- statistical task: target, sampling/generative model, method, diagnostics, and
  uncertainty representation;
- UQ task: uncertain target, source taxonomy, representation, operation,
  calibration/coverage semantics, and retained limitations;
- mechanistic task: entities, activities, organization, conditions/time, and
  the productive relation supporting the conclusion.

Absence of one of these fields does not make a workflow invalid. It means the
more specific canonical taxon should remain unassigned until the corresponding
semantics are authored.

## Recommended integration sequence

1. Add the stable IDs as provisional extension taxa without remapping the
   current corpus.
2. Split the existing composite `causal_mechanistic` archetype into separately
   auditable causal and mechanistic annotations while preserving a migration
   alias.
3. Add operational-method and uncertainty-representation facets to the JSON
   schema before assigning UQ subclasses.
4. Audit only the current mechanistic candidates; retain all quantitative
   causal and UQ categories as `absent` unless workflow contracts gain the
   required semantics.
5. Add validation rules for co-labels: causal effect estimation requires an
   estimand and identification reference; interval labels require semantics and
   level; UQ calibration requires forecasts and outcomes; causal transport
   requires explicit source and target domains.
