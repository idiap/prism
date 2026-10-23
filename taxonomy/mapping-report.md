# Prism component taxonomy mapping report (version 0.6)

## Scope

This mapping is an empirical test of the proposed faceted taxonomy against the
current catalog. It covers all **152 occurrence nodes** in **33 workflows** and
**3 projects**. Inputs, result nodes, and graph-only control markers are excluded
because the unit of analysis is an authored workflow component.

The machine-readable mapping is [`component-mapping.csv`](component-mapping.csv).
It is regenerated from `catalog/graphs.json` by running:

```console
node taxonomy/generate-component-mapping.mjs
```

The generated key `(project_id, workflow_id, occurrence_id)` is unique for all
152 rows. `workflow_source` and `source_line` provide source provenance. The
mapping also retains method, type, relation, commentary, and bound skill names
so that classifications can be reviewed against authored evidence.

## Facets

The mapping deliberately does not call every component reasoning. Its facets
answer independent questions:

- `primary_family`: the component's dominant functional family.
- `operational_roles`: the operation performed, such as extraction, projection,
  hypothesis formation, derivation, assessment, synthesis, or routing.
- `reasoning_archetypes`: inferential strategy when the source supports one.
  It is blank when no reasoning archetype is authored.
- `discourse_functions`: an organization or construction function when present.
- `substrate`: the kind of material over which the component operates.
- `computational_character`: a deprecated compatibility summary retained until
  the new constraint-regime, determinacy, procedure-family, and statefulness
  facets receive a focused row-level audit.
- `confidence`: confidence in the mapping, not confidence in a workflow result.
- `rationale`: the authored cues used for the assignment.

Multi-valued facets use `|`. Blank means not applicable or not supported, not
missing data.

## Coverage

| Primary family | Physics Discovery | Oncology Discovery | Hardware Verification | Total |
| --- | ---: | ---: | ---: | ---: |
| Core reasoning | 19 | 18 | 1 | 38 |
| Workflow control and governance | 18 | 20 | 1 | 39 |
| Information and evidence operation | 14 | 6 | 4 | 24 |
| Evaluation and judgment | 14 | 22 | 3 | 39 |
| Discourse and artifact organization | 0 | 6 | 6 | 12 |
| **Total** | **65** | **72** | **15** | **152** |

The largest operational roles are assessment or critique (25), falsification or
pressure testing (15), routing or gating (14), hypothesis formation (12), and
planning or recommendation (11). The corpus also exercises derivation,
induction, analogy/transport, calibration, grounding, projection, synthesis,
selection/ranking, decomposition, extraction, normalization, detection, and
finalization.

Sixty-six components have at least one supported reasoning archetype; 86 remain
intentionally untyped on this facet. The strongest archetype signals are
refutational (16), abductive (13), evidential assessment (9), model-based (7),
deductive (6), inductive (5), analogical (4), and mechanistic (4), with smaller
comparative, contrastive, conceptual, and diagnostic groups. Archetype counts
overlap when a component has more than one supported value.

For the legacy computational-character field, the mapping identifies 50
structured judgments, 33 heuristic or model-guided operations, 33 heuristic
structured transformations, 15 structured adversarial searches, and 1 hybrid
rule-checking and judgment operation. Twenty components remain
`not_explicitly_authored`. No component is now called deterministic solely from
a deductive, projection, extraction, or finalization name.

## Initial interpretation

The corpus supports a layered taxonomy rather than a single tree:

1. **Information/evidence operations** prepare or constrain material through
   extraction, normalization, admission, bounding, grounding, and projection.
2. **Core reasoning** transforms warranted inputs through abductive, deductive,
   inductive, analogical, model-based, contrastive, conceptual, diagnostic, or
   mechanistic operations. Refutational and evidential assessments can instead
   be primary evaluations when their product is a verdict or claim status.
3. **Evaluation/judgment** calibrates, assesses, critiques, refutes, ranks, or
   selects existing outputs. These components may still carry a reasoning
   archetype—most notably `refutational` or `evidential_assessment`—when the
   evaluation itself performs a supported epistemic test.
4. **Discourse/artifact organization** decomposes, synthesizes, refines, and
   packages claims or technical artifacts.
5. **Workflow control/governance** chooses routes, gates readiness, plans work,
   checks closure, and guards evolution across iterations.

The `substrate` facet supplies the proposed material/formal distinction without
confusing it with operation. Formal-symbolic claims and formal temporal hardware
artifacts are form-governed substrates. Scientific empirical, mechanistic,
conceptual-semantic, evidence-trace, and workflow/software artifacts require
content-sensitive or “material” interpretation to varying degrees. This is a
starting distinction, not a claim that every component is exclusively material
or formal.

## Gaps and cautions

- **No explicit probabilistic component is authored.** The corpus contains
  uncertainty, ranking, and evidential calibration, but no method or commentary
  names a probability model, likelihood, Bayesian update, or stochastic
  procedure. These are therefore not relabeled probabilistic.
- **Retrieval is not an explicit occurrence-level operation.** Skill roles may
  retrieve knowledge, but component methods primarily expose admission,
  grounding, bounding, and selection. Skill behavior should not be promoted to
  the occurrence taxonomy without an authored component contract.
- **Determinism requires a complete procedure.** None of the current occurrence
  contracts is classified deterministic merely from a deductive, projection,
  extraction, or finalization name. The new `execution_determinacy` facet should
  remain empty or `unknown` until the operative procedure and environment are
  authored.
- **Evidence-related work is decomposed.** Evidence admission, grounding, and
  bounding are operations; empirical evidence can be a warrant basis;
  `evidential_assessment` is reserved for evidence-to-claim status inference;
  readiness and routing remain control operations.
- **Compound components remain compound.** Hardware methods such as candidate
  generation-and-assessment or reflective closure combine operations. The CSV
  records their dominant role and uses a lower confidence tier where the method
  does not cleanly isolate one function.
- **Material versus formal needs a sharper definition.** The substrate facet
  makes the distinction inspectable, but a later ontology should specify whether
  “material inference” means content-sensitive validity, domain dependence, or
  empirical warrant before treating it as an archetype.
- **Confidence is taxonomic confidence only.** It reflects how explicitly method,
  commentary, types, and relations support the label. It does not assess the
  correctness of the underlying workflow output.

## Recommended next audit

Populate the new computational facets first, but only from authored procedures:
constraint regime, execution determinacy, procedure family, and statefulness.
Then audit workflow topology directly from graph relations and object type/role
from each occurrence contract. The 86 blank `reasoning_archetypes` rows should
remain blank unless new evidence establishes a genuine inferential function.
The 20 `not_explicitly_authored` compatibility rows identify where executable
semantics would most improve classification.
