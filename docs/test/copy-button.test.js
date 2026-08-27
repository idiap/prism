// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const buttonStyles = fs.readFileSync(
  path.join(__dirname, '..', 'src', 'theme', 'CodeBlock', 'Buttons', 'styles.module.css'),
  'utf8',
)

test('copy button group has visible coordinates above code content', () => {
  assert.match(buttonStyles, /right:\s*0\.75rem/)
  assert.match(buttonStyles, /top:\s*0\.75rem/)
  assert.match(buttonStyles, /z-index:\s*1/)
  assert.doesNotMatch(buttonStyles, /calc\(var\(--ifm-pre-padding\)/)
})
