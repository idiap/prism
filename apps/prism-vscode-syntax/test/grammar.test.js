// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const grammar = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'syntaxes', 'prism.tmLanguage.json'), 'utf8'),
)
const languageConfiguration = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'language-configuration.json'), 'utf8'),
)

test('all TextMate regular expressions compile', () => {
  walkPatterns(grammar.patterns)
  walkPatterns(Object.values(grammar.repository))

  function walkPatterns(patterns) {
    for (const pattern of patterns) {
      for (const key of ['begin', 'end', 'match']) {
        if (pattern[key]) assert.doesNotThrow(() => new RegExp(pattern[key]), `${key}: ${pattern[key]}`)
      }
      if (pattern.patterns) walkPatterns(pattern.patterns)
    }
  }
})

test('grammar covers every normative syntax family', () => {
  const cases = [
    ['comment.line', '# explanation'],
    ['string.quoted.multi', '"""documentation"""'],
    ['string.quoted.single', "'x'"],
    ['keyword.control.import.from', 'from prism.data import Source, query'],
    ['meta.import.from.parenthesized', 'from prism.data import (\n    Source,\n)'],
    ['punctuation.section.parens.begin', 'from prism.data import ('],
    ['entity.name.namespace.alias', 'import geometry.vectors as vectors'],
    ['storage.type.class', 'type Probability = Float where 0.0 <= self and self <= 1.0'],
    ['entity.name.type.variant', '    | Some(value: T)'],
    ['storage.type.function', 'def length[T](items: List[T]) -> Nat:'],
    ['storage.type.class', 'agent reviewer(task: ReviewTask) -> Review:'],
    ['storage.type.function', 'reasoning Inspect(input: Analysis) -> Analysis:'],
    ['storage.type.function', 'workflow audit(repository: Repository) -> Review:'],
    ['storage.type.function', 'tool review_writer: Tool[ReviewWriter] = write_review'],
    ['meta.workflow.node', '        [parsed: source.parse]'],
    ['entity.name.label.workflow-node', '        [parsed: source.parse]'],
    ['entity.name.function.workflow-component', '        [parsed: source.parse]'],
    ['keyword.control.workflow.composition', '    sequence:'],
    ['keyword.control.workflow.composition', '    parallel:'],
    ['support.function.builtin', '    repeat refinement_policy(2):'],
    ['constant.numeric.integer', '    repeat refinement_policy(2):'],
    ['variable.other.constant.workflow-policy', '    repeat bounded_review:'],
    ['keyword.control.workflow.case', '        case Static:'],
    ['storage.type.function', 'theorem ready_from_parts(change: Change) : {} |- Ready(change) := by'],
    ['support.type.runtime', 'skills: Skills[ResearchTask, CritiqueTask]'],
    ['support.type.runtime', 'hooks: Hooks[Codex]'],
    ['variable.parameter', 'def area(width: Float, height: Float) -> Float:'],
    ['keyword.control.flow', '        case Some(item):'],
    ['keyword.other.refinement', 'type Probability = Float where 0.0 <= self'],
    ['support.type.builtin', 'Map[String, Result[Int, IOError]]'],
    ['support.type.assurance', 'Verified[A, Proof[P]]'],
    ['support.type.runtime', 'Workflow[Evidence[A], E]'],
    ['support.constant.effect', '! {File.Read, Process.Run, AI.Generate, Trace.Emit}'],
    ['keyword.operator.inference.material', 'observations |~[engineering_policy] Promising(design)'],
    ['keyword.operator.inference.strict', '{tests, approval} |- Ready(change)'],
    ['keyword.operator.quantifier', 'forall item'],
    ['support.function.tactic', '    exact And.intro(tests, approval)'],
    ['keyword.operator.logical.python', 'ready and approved or not blocked'],
    ['constant.language.python', 'enabled: Bool = True'],
    ['constant.language.python', 'value = None'],
    ['constant.numeric.float', 'threshold: Decimal = 0.95'],
    ['keyword.operator.function', '(Repository, Depth) -> Analysis'],
    ['keyword.operator.effect', '-> Time ! {Clock.Read}'],
    ['keyword.operator.proof.assignment', ':= by'],
    ['variable.other.property', 'reviewer.inspect(repository, access)'],
    ['keyword.control.flow', 'solve review_request using audit_flow'],
    ['entity.name.function.call', 'generate[Analysis](request, model, access)'],
    ['entity.name.type', 'generate[Analysis](request, model, access)'],
    ['support.function.predicate', 'Ready(change)'],
  ]

  for (const [scope, sample] of cases) {
    assert.ok(scopesFor(sample).some(candidate => candidate.includes(scope)), `${scope}: ${sample}`)
  }
})

test('all documented keyword, type, effect, tactic, and operator spellings are covered', () => {
  assertEach('storage.type.class', ['type', 'agent'], token => {
    const samples = {
      type: 'type Sample = String',
      agent: 'agent Sample()',
    }
    return samples[token]
  })
  assertEach('storage.type.function', ['def', 'reasoning', 'workflow', 'tool', 'theorem'], token => {
    const samples = {
      def: 'def sample() -> Unit:',
      reasoning: 'reasoning Sample() -> Unit:',
      workflow: 'workflow sample() -> Unit:',
      tool: 'tool sample: Tool[Sample] = sample_impl',
      theorem: 'theorem sample() : {} |- P := by',
    }
    return samples[token]
  })
  assertEach('keyword.control.flow', ['return', 'if', 'else', 'match', 'case', 'try', 'solve', 'execute', 'using', 'sequence', 'parallel', 'choice', 'repeat', 'fails'])
  assertEach('support.function.tactic', ['exact', 'assumption', 'intro', 'apply', 'constructor', 'cases', 'induction', 'rewrite', 'unfold', 'simp', 'decide'])
  assertEach('support.type.builtin', ['Bool', 'Nat', 'Int', 'Float', 'Decimal', 'Char', 'String', 'Bytes', 'Unit', 'Never', 'Time', 'Duration', 'Type', 'Prop', 'List', 'Set', 'Map', 'Option', 'Result'])
  assertEach('support.type.assurance', ['Generated', 'Evidence', 'Supported', 'Validated', 'Proof', 'Verified'])
  assertEach('support.type.runtime', [
    'CoreTerm', 'ProofSyntax', 'Claim', 'Workflow', 'RefinementPolicy',
    'Relation',
    'Skill', 'Skills', 'Tool', 'Tools', 'Hooks', 'Codex', 'Claude',
  ])
  assertEach('support.constant.effect', ['File.Read', 'File.Write', 'Data.Read', 'Data.Write', 'Network.Request', 'Process.Run', 'Tool.Call', 'MCP.Call', 'AI.Generate', 'Clock.Read', 'Random.Sample', 'Trace.Emit'])
  assertEach('keyword.operator.logical.python', ['and', 'or', 'not'])
  assertEach('keyword.operator.quantifier', ['forall item', 'exists item'])
  const functionScopes = scopesFor('def analyze_normative_claim() -> Bool:')
  assert.ok(functionScopes.includes('storage.type.function.python'))
  assert.ok(functionScopes.includes('entity.name.function.python'))
  const typeScopes = scopesFor('type NormativeError:')
  assert.ok(typeScopes.includes('storage.type.class.python'))
  assert.ok(typeScopes.includes('entity.name.type.class.python'))
  assert.notEqual(typeScopes.indexOf('storage.type.class.python'), typeScopes.indexOf('entity.name.type.class.python'))
  assert.ok(scopesFor('value = try check(True)').includes('keyword.control.flow.python'))
  assert.ok(scopesFor('value = try check(True)').includes('constant.language.python'))
  assert.ok(scopesFor('from .safety.rules import Safe').includes('entity.name.namespace.prism'))
  assert.ok(!scopesFor('claim old_form').some(scope => scope.startsWith('keyword.declaration')))
  assert.ok(!scopesFor('source old_form').some(scope => scope.startsWith('keyword.declaration')))
  assert.ok(!scopesFor('resource old_form').some(scope => scope.startsWith('keyword.declaration')))
  assert.ok(!scopesFor('connection old_form').some(scope => scope.startsWith('keyword.declaration')))
  assert.ok(!scopesFor('handler old_form').some(scope => scope.startsWith('keyword.declaration')))
})

test('language configuration supports significant indentation and all delimiters', () => {
  assert.equal(languageConfiguration.comments.lineComment, '#')
  assert.equal(languageConfiguration.folding.offSide, true)
  assert.ok(languageConfiguration.indentationRules.increaseIndentPattern)
  assert.deepEqual(languageConfiguration.brackets, [['{', '}'], ['[', ']'], ['(', ')']])
  assert.ok(languageConfiguration.autoClosingPairs.some(pair => pair.open === "'" && pair.close === "'"))
  assert.ok(languageConfiguration.autoClosingPairs.some(pair => pair.open === '"' && pair.close === '"'))
})

function scopesFor(sample) {
  const scopes = []
  visit([...grammar.patterns, ...Object.values(grammar.repository)])
  return scopes

  function visit(patterns) {
    for (const pattern of patterns) {
      const expression = pattern.match || pattern.begin
      if (expression) {
        const match = new RegExp(expression).exec(sample)
        if (match) {
          if (pattern.name) scopes.push(pattern.name)
          for (const [capture, descriptor] of Object.entries(pattern.captures || pattern.beginCaptures || {})) {
            if (match[Number(capture)] !== undefined) scopes.push(descriptor.name)
          }
        }
      }
      if (pattern.patterns) visit(pattern.patterns)
    }
  }
}

function assertEach(scope, tokens, sampleFor = token => token) {
  for (const token of tokens) {
    assert.ok(
      scopesFor(sampleFor(token)).some(candidate => candidate.includes(scope)),
      `${scope}: ${token}`,
    )
  }
}
