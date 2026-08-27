// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')
const {Prism} = require('prism-react-renderer')
const {prismDarkTheme, prismLightTheme} = require('../src/prism-themes')

require('../src/prism-language')

test('Prism documentation grammar highlights the language syntax', () => {
  const html = Prism.highlight(`
reasoning Inspect(input: Analysis) -> Supported[Finding]:
    sequence:
        [finding: inspect(input)] by Test
    return finding

def main() -> Bool ! {AI.Generate}:
    return True
`, Prism.languages.prism, 'prism')

  assert.match(html, /token keyword">reasoning</)
  assert.match(html, /token function">Inspect</)
  assert.match(html, /token class-name">Supported</)
  assert.match(html, /token keyword">sequence</)
  assert.match(html, /token keyword">by</)
  assert.match(html, /token effect-name constant">AI\.Generate</)
  assert.match(html, /token boolean">True</)
})

test('declaration keywords do not highlight matching import path segments', () => {
  const html = Prism.highlight(
    'from prism.reasoning.methods import Deductive',
    Prism.languages.prism,
    'prism',
  )

  assert.match(html, /token keyword">from</)
  assert.doesNotMatch(html, /token keyword">reasoning</)
})

test('reasoning examples distinguish semantic syntax families', () => {
  const html = Prism.highlight(`
type Input:
    text: String

type Status:
    | Accepted
    | Refuted

type CandidateMethod = Input -> Status

reasoning Review(source: Input) -> Status:
    sequence:
        [candidate: CandidateMethod(source)] by Test
    return candidate
`, Prism.languages.prism, 'prism')

  assert.match(html, /token class-name">Input</)
  assert.match(html, /token property">text</)
  assert.match(html, /token variant">Accepted</)
  assert.match(html, /token parameter">source</)
  assert.match(html, /token label">candidate</)
  assert.match(html, /token function">CandidateMethod</)
  assert.match(html, /token function">Test</)
  assert.match(html, /token operator">-></)
})

test('documentation themes style every Prism-specific token family', () => {
  const tokenTypes = ['class-name', 'function', 'keyword', 'label', 'operator', 'parameter', 'property', 'variant']

  for (const theme of [prismLightTheme, prismDarkTheme]) {
    const styledTypes = new Set(theme.styles.flatMap(style => style.types))
    for (const tokenType of tokenTypes) assert.ok(styledTypes.has(tokenType), tokenType)
    assert.notEqual(colorFor(theme, 'class-name'), colorFor(theme, 'property'))
    assert.notEqual(colorFor(theme, 'number'), colorFor(theme, 'property'))
  }
})

test('constructor properties remain distinct from bindings and numeric values', () => {
  const html = Prism.highlight(`
mission_specification = MissionConstraints(
    initial_x = 16.5,
    initial_altitude = 250.111,
)
`, Prism.languages.prism, 'prism')

  assert.match(html, /token variable">mission_specification</)
  assert.match(html, /token property">initial_x</)
  assert.match(html, /token property">initial_altitude</)
  assert.match(html, /token number">16\.5</)
  assert.match(html, /token number">250\.111</)
})

function colorFor(theme, tokenType) {
  return theme.styles
    .filter(style => style.types.includes(tokenType) && style.style.color)
    .at(-1)?.style.color
}
