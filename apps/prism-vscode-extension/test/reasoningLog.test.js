// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

const assert = require('node:assert/strict')
const test = require('node:test')
const { renderReasoningLog } = require('../dist/host/reasoningLog')

function event(instance, assurance = 'unchecked', disposition = 'not_applicable') {
  return {
    kind: 'workflow-node', name: 'collect<script>', status: 'accepted',
    metadata: { occurrence_instance_id: instance, declared_contract: {
      identity: 'plan::collect', method_identity: 'module::collect', execution_kind: 'structural',
      classification: { state: 'unclassified', archetype_state: 'not_applicable', references: [] },
      requirements: [{ assurance: { kind: 'unchecked' }, origin: { producers: ['unconstrained'] } }],
    }, result: { claim: { identity: 'module::Ready' }, validator: 'module::check', validator_hash: 'validator123' } },
    outcome: { execution: 'completed', contract: 'satisfied', observed: [
      { path: [], reference: 'derived', producer: 'computed', assurance, claim_disposition: disposition, assumptions: [], claim: { identity: 'module::Ready' }, certificate: { validator: 'module::check', validator_hash: 'validator123' } },
    ] },
  }
}
function output(trace) {
  return { trace_version: '11', trace, provenance: {
    values: [{ identity: 'derived', activity: 'compute', dependencies: [] }, { identity: 'input', activity: 'generate', dependencies: [] }],
    activities: [{ identity: 'compute', kind: 'computed', operation: 'collect', inputs: ['input'] },
      { identity: 'generate', kind: 'generated', operation: 'narrate', inputs: [], effect_record: 'effect123', synthetic: true }],
  } }
}

test('structural steps show explicit unchecked states and real generated ancestry', () => {
  const html = renderReasoningLog(output([event('run/1')]))
  for (const text of ['module::collect', 'structural', 'unclassified', 'not_applicable', 'unchecked', 'unconstrained', 'derived', 'generated', 'effect123', 'synthetic']) assert.ok(html.includes(text), text)
  assert.ok(html.includes('collect&lt;script&gt;'))
  assert.ok(!html.includes('<script>'))
})

test('execution completion is independent of contract and claim rejection', () => {
  const rejected = event('run/2', 'unchecked', 'rejected')
  rejected.outcome.contract = 'rejected'
  const html = renderReasoningLog(output([rejected]))
  assert.match(html, /Execution: completed/)
  assert.match(html, /Contract: rejected/)
  assert.match(html, /assurance unchecked; claim rejected/)
})

test('accepted validation exposes its exact claim and validator reference', () => {
  const html = renderReasoningLog(output([event('run/3', 'validated', 'accepted')]))
  for (const text of ['assurance validated', 'claim accepted', 'module::Ready', 'module::check', 'validator123']) assert.ok(html.includes(text), text)
})

test('loop instances stay distinct even when their source occurrence is identical', () => {
  const html = renderReasoningLog(output([event('run/1'), event('run/2')]))
  assert.match(html, /data-occurrence-instance="run\/1"/)
  assert.match(html, /data-occurrence-instance="run\/2"/)
  assert.equal((html.match(/class="node reasoning-step"/g) || []).length, 2)
})

test('unsupported traces are rejected before interpreting semantic state', () => {
  const old = { ...output([event('old')]), trace_version: '10' }
  const html = renderReasoningLog(old)
  assert.match(html, /Unsupported trace version 10/)
  assert.ok(!html.includes('Contract: satisfied'))
})

test('relation certificates retain proof hashes, assumptions, and their exact target instance', () => {
  const relation = event('ignored', 'proved', 'accepted')
  relation.kind = 'reasoning-relation'
  relation.metadata = { relation_instance_id: 'run/2/relation', target_occurrence_instance: 'run/2',
    declared_relation: { identity: 'module::Approves', certificate_type: { name: 'Proof' } },
    certificate: { type: { kind: 'Eq', left: 7, right: 7 }, term_hash: 'proof123', type_hash: 'claim123', environment_hash: 'env123' } }
  relation.outcome.observed[0].assumptions = ['module::axiom']
  relation.outcome.observed[0].claim = { kind: 'Eq', left: 7, right: 7 }
  relation.outcome.observed[0].certificate = { proof_hash: 'proof123', proposition_hash: 'claim123', environment_hash: 'env123' }
  const html = renderReasoningLog(output([relation]))
  for (const text of ['run/2/relation', 'target: run/2', 'module::Approves', 'proof123', 'claim123', 'env123', 'module::axiom']) assert.ok(html.includes(text), text)
})

test('support and inconclusive assessments show their policy without implying proof', () => {
  for (const [assurance, disposition] of [['supported', 'accepted'], ['unchecked', 'inconclusive']]) {
    const assessment = { claim: { identity: 'module::Explains' }, policy_identity: 'module::policy', policy_hash: 'policy123', evidence_reference: 'evidence123' }
    const item = event('run/1', assurance, disposition)
    item.outcome.observed[0].claim = assessment.claim
    item.outcome.observed[0].certificate = assessment
    const html = renderReasoningLog(output([item]))
    for (const text of [assurance, disposition, 'module::Explains', 'policy123', 'evidence123']) assert.ok(html.includes(text), text)
    assert.ok(!html.includes('assurance proved'))
  }
})
