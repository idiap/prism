// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

export type PrismDiagnosticSeverity = 'error' | 'warning' | 'info'
export type PrismInferenceStatus = 'accepted' | 'rejected' | 'undetermined' | 'blocked'

export interface PrismIdeDiagnostic {
  code: string
  severity: PrismDiagnosticSeverity
  message: string
  line?: number | null
  character?: number | null
  end_line?: number | null
  end_character?: number | null
  line_text: string
}

export interface PrismIdeSymbolSpan {
  line: number
  character: number
  end_line?: number | null
  end_character?: number | null
}

export interface PrismIdeSymbol {
  name: string
  kind: string
  span: PrismIdeSymbolSpan
  detail: string
  module_path?: string | null
  definition_path?: string | null
  source_ref?: string | null
  metadata: Record<string, unknown>
}

export interface PrismIdeTypeSpan {
  span: PrismIdeSymbolSpan
  type_text: string
  kind: string
  name?: string | null
}

export interface PrismIdeCheckResult {
  status: 'valid' | 'invalid'
  document_path: string
  diagnostics: PrismIdeDiagnostic[]
  symbols: PrismIdeSymbol[]
  type_spans: PrismIdeTypeSpan[]
  occurrence_contracts: PrismOccurrenceContract[]
  core_module?: {
    format: string
    calculus: string
    hash: string
    axioms: Record<string, string[]>
  } | null
}

export interface PrismOccurrenceContract {
  identity: string
  owner_identity: string
  method_identity: string
  execution_kind: 'method' | 'structural' | 'workflow'
  classification: {
    state: string
    archetype_state: string
    references: { taxonomy: string; version: string; facet: string; taxon: string; status: string }[]
  }
  input_requirements: unknown[]
  requirements: unknown[]
  relation?: unknown
}

export interface PrismObservedValue {
  path: string[]
  reference: string | null
  producer: string
  assurance: string
  claim_disposition: string
  assumptions: string[]
  claim?: unknown
  certificate?: Record<string, unknown> | null
}

export interface PrismOccurrenceOutcome {
  execution: string
  contract: string
  observed: PrismObservedValue[]
}

export interface PrismProvenanceGraph {
  values: { identity: string; activity: string; dependencies: string[]; artifact?: unknown }[]
  activities: { identity: string; kind: string; operation: string; inputs: string[]; implementation_hash?: string; effect_record?: string; synthetic?: boolean }[]
}

export interface PrismTraceEventOutput {
  outcome?: PrismOccurrenceOutcome | null
  kind: string
  name: string
  status: PrismInferenceStatus
  assurance?: string | null
  provenance?: string | null
  metadata: Record<string, unknown>
}

export interface PrismEffectRecordOutput {
  invocation?: Record<string, unknown>
  observation?: Record<string, unknown>
  input_payload?: unknown
  output_payload?: unknown
  [key: string]: unknown
}

export interface PrismInferenceOutput {
  path?: string | null
  source_hash: string
  status: PrismInferenceStatus
  result: unknown
  trace: PrismTraceEventOutput[]
  diagnostics: unknown[]
  effect_records: Record<string, PrismEffectRecordOutput>
  metadata: Record<string, unknown>
  provenance?: PrismProvenanceGraph | null
  trace_version: string
}

export interface PrismIdeRunResult {
  status: 'completed' | 'failed'
  backend: 'fake' | 'litellm'
  model?: string | null
  document_path: string
  message: string
  diagnostics: PrismIdeDiagnostic[]
  output?: PrismInferenceOutput | null
  run_id?: string | null
  run_path?: string | null
  run_created_at?: string | null
}

export interface PrismIdeHealthResponse {
  status: string
}
