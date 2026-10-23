// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import type { PrismInferenceOutput, PrismOccurrenceContract } from '../infoview-api/protocol'

const escapeHtml = (value: unknown): string => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]!))
const json = (value: unknown): string => `<pre class="json-block">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`
const object = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' ? value as Record<string, unknown> : {}

export function renderReasoningLog(output: PrismInferenceOutput, renderValue = json): string {
  if (output.trace_version !== '11') {
    return `<section role="alert">Unsupported trace version ${escapeHtml(output.trace_version)}; expected 11. Run the program again.</section>`
  }
  const values = new Map(output.provenance?.values.map(value => [value.identity, value]) ?? [])
  const activities = new Map(output.provenance?.activities.map(activity => [activity.identity, activity]) ?? [])
  function ancestry(reference: string | null): unknown[] {
    const pending = reference ? [reference] : []
    const visited = new Set<string>()
    const found = new Map<string, unknown>()
    while (pending.length) {
      const identity = pending.pop()!
      if (visited.has(identity)) continue
      visited.add(identity)
      const value = values.get(identity)
      if (!value) continue
      pending.push(...value.dependencies)
      const activity = activities.get(value.activity)
      if (activity && !found.has(activity.identity)) {
        found.set(activity.identity, activity)
        pending.push(...activity.inputs)
      }
    }
    return [...found.values()]
  }
  const steps = output.trace.filter(event => event.kind === 'workflow-node' || event.kind === 'reasoning-relation')
  if (!steps.length) return ''
  return `<section class="section" aria-label="Reasoning log"><h2>Reasoning Log</h2><div class="node-stack">${steps.map(event => {
    const contract = event.metadata.declared_contract as PrismOccurrenceContract | undefined
    const instance = event.metadata.occurrence_instance_id ?? event.metadata.relation_instance_id ?? 'not_applicable'
    const outcome = event.outcome
    const classification = contract?.classification
    const target = event.metadata.target_occurrence_instance
    return `<details class="node reasoning-step" data-occurrence-instance="${escapeHtml(instance)}">
<summary><span>${escapeHtml(event.name)}</span> <span>Execution: ${escapeHtml(outcome?.execution ?? 'not_applicable')}</span> <span>Contract: ${escapeHtml(outcome?.contract ?? 'not_applicable')}</span></summary>
<div class="node-body"><p>Instance: ${escapeHtml(instance)}${target ? `; target: ${escapeHtml(target)}` : ''}</p>
<p>Reasoning: ${escapeHtml(contract?.method_identity ?? object(event.metadata.declared_relation).identity ?? event.name)}; family: ${escapeHtml(contract?.execution_kind ?? 'relation')}; classification: ${escapeHtml(classification?.state ?? 'not_applicable')}; archetype: ${escapeHtml(classification?.archetype_state ?? 'not_applicable')}</p>
${classification ? json(classification.references) : ''}
<details><summary>Declared contract</summary>${json(contract ?? event.metadata.declared_relation ?? 'not_applicable')}</details>
${outcome?.observed.map(observed => `<details><summary>${escapeHtml(observed.path.join('.') || 'result')}: producer ${escapeHtml(observed.producer)}; assurance ${escapeHtml(observed.assurance)}; claim ${escapeHtml(observed.claim_disposition)}</summary>
<p>Value reference: ${escapeHtml(observed.reference ?? 'not_applicable')}</p>${json({ claim: observed.claim ?? 'not_applicable', certificate: observed.certificate ?? 'not_applicable' })}
<p>Assumptions: ${escapeHtml(observed.assumptions.join(', ') || 'none')}</p><details><summary>Production and upstream ancestry</summary>${json(ancestry(observed.reference))}</details></details>`).join('') ?? '<p>Observed assurance: not_applicable</p>'}
<details><summary>Result</summary>${renderValue(event.metadata.result ?? event.metadata.certificate)}</details></div></details>`
  }).join('')}</div></section>`
}
