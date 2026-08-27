// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const syntaxRoot = path.resolve(__dirname, '..')
const workbenchRoot = path.resolve(syntaxRoot, '../prism-vscode-extension')
const syntaxManifest = require(path.join(syntaxRoot, 'package.json'))
const workbenchManifest = require(path.join(workbenchRoot, 'package.json'))

test('language support is the sole owner of Prism editor contributions', () => {
  assert.ok(syntaxManifest.contributes.languages?.some(language => language.id === 'prism'))
  assert.ok(syntaxManifest.contributes.grammars?.some(grammar => grammar.language === 'prism'))

  assert.equal(workbenchManifest.contributes.languages, undefined)
  assert.equal(workbenchManifest.contributes.grammars, undefined)
  assert.deepEqual(workbenchManifest.extensionDependencies, ['prism.prism-language-support'])

  const workbenchSource = fs.readFileSync(
    path.join(workbenchRoot, 'src/host/extension.ts'),
    'utf8',
  )
  assert.doesNotMatch(workbenchSource, /registerHoverProvider|registerDefinitionProvider|createDiagnosticCollection/)
})
