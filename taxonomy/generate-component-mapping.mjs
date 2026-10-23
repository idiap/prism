import fs from "node:fs";

const catalogPath = new URL("../catalog/graphs.json", import.meta.url);
const outputPath = new URL("./component-mapping.csv", import.meta.url);
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));

function tokens(value) {
  return String(value || "")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .toLowerCase();
}

function includesAny(text, words) {
  return words.some((word) => text.includes(word));
}

function reasoningArchetype(method, text, operation) {
  const archetypes = [];
  const prefixes = [
    ["abduct", "abductive"],
    ["deduct", "deductive"],
    ["induct", "inductive"],
    ["analog", "analogical"],
    ["model based", "model_based"],
    ["contrast", "contrastive"],
    ["refutation", "refutational"],
  ];
  for (const [cue, label] of prefixes) {
    if (tokens(method).includes(cue)) archetypes.push(label);
  }
  if (/OutcomeAbduction/.test(method) && !archetypes.includes("abductive")) archetypes.push("abductive");
  if (/EpistemicModelRefinement/.test(method)) archetypes.push("conceptual", "model_based");
  if (/DiagnoseAndPlanDebugProbes/.test(method)) archetypes.push("diagnostic", "mechanistic_reasoning");
  if (/DiscoveryNoveltyAssessment|SkillEvolutionAssessment|ExistingCapabilitySufficiencyAssessment/.test(method)) {
    archetypes.push("comparative_analytical");
  }
  if (
    tokens(method).includes("evidential")
    && includesAny(operation, ["assessment_or_critique", "calibration", "selection_or_ranking"])
    && !includesAny(operation, ["routing_or_gating", "readiness_gating"])
  ) {
    archetypes.push("evidential_assessment");
  }
  if (
    includesAny(text, ["mechanistic", "mechanism", "circuit model", "resistance biology"])
    && (
      includesAny(operation, ["model_construction", "model_probing", "diagnostic_analysis", "falsification_or_pressure_test"])
      || (archetypes.includes("model_based") && operation.includes("selection_or_ranking"))
    )
  ) {
    archetypes.push("mechanistic_reasoning");
  }
  return [...new Set(archetypes)].join("|");
}

function operationMode(method) {
  const text = tokens(method);
  const compound = new Map([
    ["GenerateAndAssessSvaCandidate", "synthesis_or_construction|assessment_or_critique"],
    ["CritiqueAndRouteSvaRefinement", "assessment_or_critique|routing_or_gating|refinement"],
    ["PlanAndGenerateAssertions", "planning_or_recommendation|synthesis_or_construction"],
    ["FrameworkWorkflowDecompositionSynthesis", "decomposition|synthesis_or_construction"],
    ["RepresentAndDetectDebugFindings", "synthesis_or_construction|detection"],
    ["DiagnoseAndPlanDebugProbes", "diagnostic_analysis|planning_or_recommendation"],
  ]);
  if (compound.has(method)) return compound.get(method);
  if (/ReadinessAssessment$/.test(method)) return "readiness_gating";
  if (/Calibration$/.test(method)) return "calibration";
  if (/PayloadAdmission$/.test(method)) return "evidence_admission";
  if (/Inductive.*Formation$/.test(method)) return "pattern_inference";
  if (/Abductive.*Formation$/.test(method)) return "hypothesis_formation";
  if (/Ranking$/.test(method)) return "selection_or_ranking";
  if (/Construction$/.test(method)) return "model_construction";
  if (/Synthesis$/.test(method)) return "synthesis_or_construction";
  if (/Probe$/.test(method)) return "model_probing";
  if (/^Synthesize/.test(method)) return "synthesis_or_construction";
  const rules = [
    [["extract"], "extraction"],
    [["intake and normalize"], "normalization"],
    [["projection"], "projection"],
    [["bounding", "bound discovery"], "boundary_setting"],
    [["grounding", "ground sva evidence"], "grounding"],
    [["hypothesis formation", "candidate claim formation", "outcome abduction"], "hypothesis_formation"],
    [["derivation", "consequence materialization"], "derivation"],
    [["inference"], "pattern_inference"],
    [["model construction", "model synthesis", "model refinement"], "model_construction"],
    [["model based", "hypothesis probe"], "model_probing"],
    [["analogical", "transport", "concordance"], "analogy_or_transport"],
    [["contrastive"], "contrast"],
    [["refutational", "refutation", "defeater"], "falsification_or_pressure_test"],
    [["calibration"], "calibration"],
    [["routing", "route ", "disposition"], "routing_or_gating"],
    [["readiness"], "readiness_gating"],
    [["selection", "ranking"], "selection_or_ranking"],
    [["assessment", "audit", "judgment", "review", "critique", "validate"], "assessment_or_critique"],
    [["classification"], "classification"],
    [["decision"], "decision"],
    [["decomposition"], "decomposition"],
    [["recommendation", "plan ", "planning", "design"], "planning_or_recommendation"],
    [["synthesis", "generate", "construction", "specification", "account", "report"], "synthesis_or_construction"],
    [["finalize"], "finalization"],
    [["detect"], "detection"],
    [["forecast"], "forecasting"],
    [["refinement", "revision", "remediation"], "refinement"],
    [["control"], "control"],
  ];
  for (const [cues, label] of rules) if (includesAny(text, cues)) return label;
  return "other_authored_operation";
}

function family(method, archetype, operation) {
  if (/^(GenerateAndAssessSvaCandidate|PlanAndGenerateAssertions|SynthesizeReflectionClosure)$/.test(method)) {
    return "discourse_and_artifact_organization";
  }
  if (/^CritiqueAndRouteSvaRefinement$/.test(method)) return "evaluation_and_judgment";
  if (/^RepresentAndDetectDebugFindings$/.test(method)) return "information_and_evidence_operation";
  if (archetype.includes("refutational")) return "evaluation_and_judgment";
  if (includesAny(archetype, ["abductive", "deductive", "inductive", "analogical", "model_based", "contrastive", "diagnostic", "causal_reasoning", "mechanistic_reasoning"])) {
    return "core_reasoning";
  }
  if (includesAny(operation, ["extraction", "normalization", "projection", "boundary_setting", "grounding", "admission", "detection"])) {
    return "information_and_evidence_operation";
  }
  if (includesAny(operation, ["routing", "gating", "readiness", "control", "decision", "planning", "recommendation", "classification"]) || /Closure|Monotonicity|Drift/.test(method)) {
    return "workflow_control_and_governance";
  }
  if (includesAny(operation, ["assessment", "critique", "calibration", "selection", "ranking", "forecasting"])) {
    return "evaluation_and_judgment";
  }
  if (includesAny(operation, ["synthesis", "construction", "decomposition", "finalization", "refinement"])) {
    return "discourse_and_artifact_organization";
  }
  return "other_composite_operation";
}

function discourseFunction(method, operation) {
  const organizational = new Set([
    "projection", "classification", "decomposition", "planning_or_recommendation",
    "synthesis_or_construction", "finalization", "refinement", "routing_or_gating",
  ]);
  const discourseRoles = operation.split("|").filter((role) => organizational.has(role));
  if (/Presentation/.test(method)) discourseRoles.push("presentation");
  if (/ClaimFormation|HypothesisFormation/.test(method)) discourseRoles.push("claim_or_hypothesis_formation");
  return [...new Set(discourseRoles)].join("|");
}

function substrate(project, workflow, method, text) {
  const joined = `${tokens(workflow)} ${tokens(method)} ${text}`;
  if (project === "spectra") {
    return joined.includes("debug") ? "hardware_debug_evidence" : "formal_temporal_hardware_artifact";
  }
  if (includesAny(joined, ["proof", "theorem", "formal claim", "derivation"])) return "formal_symbolic_claims";
  if (includesAny(joined, ["tumor", "melanoma", "resistance", "biological", "circuit", "oncology", "ebr"])) {
    return includesAny(joined, ["mechanistic", "circuit", "resistance"]) ? "scientific_empirical_and_mechanistic" : "scientific_empirical_evidence";
  }
  if (includesAny(joined, ["conceptual", "discourse", "bridge", "obstruction"])) return "conceptual_semantic_structure";
  if (includesAny(joined, ["framework", "skill", "workflow", "implementation", "todo", "feedback", "goal oriented"])) return "workflow_and_software_artifacts";
  if (includesAny(joined, ["manuscript", "release", "review", "claim set", "timeline paper"])) return "evidence_trace_and_scientific_artifact";
  if (includesAny(joined, ["discovery", "hypothesis", "evidence"])) return "scientific_conceptual_and_evidential";
  return "typed_domain_artifacts";
}

function computationalCharacter(method, archetype, operation) {
  if (/ValidateAssertionSemantics/.test(method)) return "hybrid_rule_checking_and_judgment";
  if (archetype === "deductive") return "not_explicitly_authored";
  if (includesAny(archetype, ["abductive", "inductive", "analogical", "contrastive", "model_based", "diagnostic", "causal_reasoning", "mechanistic_reasoning"])) return "heuristic_or_model_guided";
  if (archetype.includes("refutational")) return "structured_adversarial_search";
  if (archetype.includes("evidential_assessment") || includesAny(operation, ["assessment", "calibration", "selection", "ranking", "routing", "gating", "readiness", "decision"])) return "structured_judgment";
  if (includesAny(operation, ["extraction", "normalization", "projection", "synthesis", "construction", "refinement", "planning", "recommendation", "forecasting", "finalization"])) return "heuristic_structured_transformation";
  return "not_explicitly_authored";
}

function confidence(method, archetype, operation, commentary) {
  const explicitArchetype = /^(Abductive|Deductive|Inductive|Analogical|ModelBased|Contrastive|Refutational|Evidential)/.test(method);
  if (explicitArchetype && commentary) return "high";
  if (/^(Extract|Unresolved|IntakeAndNormalize|Finalize|Validate)/.test(method) && commentary) return "high";
  if (operation !== "other_authored_operation" && commentary) return "medium_high";
  if (explicitArchetype || operation !== "other_authored_operation") return "medium";
  return "low";
}

function rationale(method, archetype, operation, commentary) {
  const cues = [];
  if (archetype) cues.push(`reasoning evidence supports ${archetype.replaceAll("|", "/")}`);
  cues.push(`operational evidence supports ${operation.replaceAll("_", " ")}`);
  if (commentary) cues.push("authored commentary constrains the interpretation");
  else cues.push("no authored commentary; classification is limited to method and type names");
  return `${method}: ${cues.join("; ")}.`;
}

const rows = [];
for (const project of catalog.projects) {
  for (const workflow of project.workflows) {
    for (const node of workflow.graph.nodes.filter((item) => item.kind === "occurrence")) {
      const evidenceText = tokens(`${node.commentary} ${node.input_type} ${node.output_type} ${node.relation}`);
      const operation = operationMode(node.method);
      const archetype = reasoningArchetype(node.method, evidenceText, operation);
      rows.push({
        project_id: project.id,
        project_label: project.label,
        workflow_id: workflow.id,
        workflow_label: workflow.label,
        workflow_source: workflow.source || "",
        occurrence_id: node.id,
        method: node.method,
        source_line: node.source_span?.line || "",
        input_type: node.input_type,
        output_type: node.output_type,
        relation: node.relation,
        commentary: node.commentary,
        skill_names: (node.skills || []).map((skill) => skill.name).join("|"),
        primary_family: family(node.method, archetype, operation),
        operational_roles: operation,
        reasoning_archetypes: archetype,
        discourse_functions: discourseFunction(node.method, operation),
        substrate: substrate(project.id, workflow.label, node.method, evidenceText),
        computational_character: computationalCharacter(node.method, archetype, operation),
        confidence: confidence(node.method, archetype, operation, node.commentary),
        rationale: rationale(node.method, archetype, operation, node.commentary),
      });
    }
  }
}

const columns = Object.keys(rows[0]);
const csv = (value) => {
  const rendered = String(value ?? "");
  return /[",\r\n]/.test(rendered) ? `"${rendered.replaceAll('"', '""')}"` : rendered;
};
fs.writeFileSync(outputPath, `${columns.join(",")}\n${rows.map((row) => columns.map((column) => csv(row[column])).join(",")).join("\n")}\n`);
console.log(`Wrote ${rows.length} occurrence mappings to ${outputPath.pathname}`);
