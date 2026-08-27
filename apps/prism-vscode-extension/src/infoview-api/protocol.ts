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
  core_module?: {
    format: string
    calculus: string
    hash: string
    axioms: Record<string, string[]>
  } | null
}

export interface PrismTraceEventOutput {
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
