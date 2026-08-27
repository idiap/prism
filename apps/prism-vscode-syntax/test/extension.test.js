// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const assert = require('node:assert/strict')
const Module = require('node:module')
const test = require('node:test')

const { CompilerServiceClient } = require('../src/compiler-service')

test('compiler cache invalidation rechecks an unchanged document', async () => {
  const folder = { uri: Uri.file('/workspace') }
  const document = fakeDocument('/workspace/main.prism', 'value = valid\n')
  const compiler = new CompilerServiceClient({
    workspace: {
      getWorkspaceFolder() { return folder },
      workspaceFolders: [folder],
    },
  })
  let requests = 0
  compiler.request = async () => {
    requests += 1
    return requests === 1
      ? { status: 'invalid', diagnostics: [{ message: 'stale' }] }
      : validCheck([])
  }

  assert.equal((await compiler.checkDocument(document)).status, 'invalid')
  assert.equal((await compiler.checkDocument(document)).status, 'invalid')
  assert.equal(requests, 1)

  compiler.invalidate()

  assert.equal((await compiler.checkDocument(document)).status, 'valid')
  assert.equal(requests, 2)
})

test('compiler skips a workspace virtualenv that cannot import Prism', async () => {
  const compiler = new CompilerServiceClient({})
  const probes = []
  compiler.pythonCandidates = () => ['/workspace/.venv/bin/python', 'python']
  compiler.probePython = async candidate => {
    probes.push(candidate)
    if (candidate.includes('.venv')) throw new Error("No module named 'prism'")
  }

  assert.equal(await compiler.resolvePythonPath('/workspace'), 'python')
  assert.deepEqual(probes, ['/workspace/.venv/bin/python', 'python'])
})

test('compiler reports every failed interpreter probe with configuration guidance', async () => {
  const compiler = new CompilerServiceClient({})
  compiler.pythonCandidates = () => ['/workspace/.venv/bin/python', 'python']
  compiler.probePython = async candidate => {
    throw new Error(candidate === 'python' ? 'command not found' : "No module named 'prism'")
  }

  await assert.rejects(
    compiler.resolvePythonPath('/workspace'),
    error => error.message.includes('/workspace/.venv/bin/python')
      && error.message.includes('python: command not found')
      && error.message.includes('prism.languageServer.pythonPath'),
  )
})

test('backend startup failures produce one actionable warning and a diagnostic log', async () => {
  const document = fakeDocument('/workspace/main.prism', 'value = True\n')
  const documents = new Map([[document.uri.fsPath, document]])
  const registered = {}
  const vscode = fakeVscode(new Map(), documents, (kind, value) => { registered[kind] = value })
  const compiler = {
    async checkDocument() { throw new Error("No module named 'prism'") },
    invalidate() {},
    forget() {},
    dispose() {},
  }
  const originalLoad = Module._load
  Module._load = function load(request, parent, isMain) {
    if (request === 'vscode') return vscode
    return originalLoad.call(this, request, parent, isMain)
  }
  try {
    const extensionPath = require.resolve('../src/extension')
    delete require.cache[extensionPath]
    const extension = require(extensionPath)
    extension.activate({ subscriptions: [], prismCompilerService: compiler })
    await new Promise(resolve => setImmediate(resolve))

    assert.match(registered.output.lines.join('\n'), /No module named 'prism'/)
    assert.match(registered.warning.message, /could not start/)
    assert.deepEqual(registered.warning.actions, ['Set Python Path', 'Show Log'])

    await registered.hover.provideHover(
      document,
      { line: 0, character: 1 },
      { isCancellationRequested: false },
    )
    assert.equal(registered.output.lines.length, 2)
    assert.equal(registered.warning.count, 1)
  } finally {
    Module._load = originalLoad
  }
})

test('definitions, hovers, semantic tokens, and diagnostics use compiler results', async () => {
  const files = new Map([
    ['/workspace/lib/geometry.prism', `type Point:
    x: Float
    y: Float

def distance(left: Point, right: Point) -> Float:
    return left.x - right.x

def inspect(point: Point) -> Float:
    return point.x

`],
    ['/workspace/main.prism', `from lib.geometry import (
    Point,
    distance as measure,
)
import lib.geometry as geometry

origin = Point(x = 0.0, y = 0.0)
result = geometry.distance(origin, origin)
span = measure(origin, origin)
coordinate = origin.x
draft = generate[Point](origin, model, model_access)
checked = validate(draft)
statement = claim("origin exists")
term = elaborate_proof[Point]("rfl")
`],
    ['/workspace/reasoning.prism', 'reasoning Review(source: String) -> Status:\n    [status: Evidential(source)]\n    on status.\n    return status\n'],
  ])
  const documents = new Map([...files].map(([file, source]) => [file, fakeDocument(file, source)]))
  const generatedSource = `flow = workflows.pipeline(source, backend, tool_access, context_access)\n`
  const generatedDocument = fakeDocument('/workspace/generated.prism', generatedSource)
  documents.set('/workspace/generated.prism', generatedDocument)
  const invalidDocument = fakeDocument('/workspace/invalid.prism', 'value = point.unknown\n')
  documents.set('/workspace/invalid.prism', invalidDocument)
  const checks = new Map([
    ['/workspace/lib/geometry.prism', validCheck([
      typedSpan(8, 11, 8, 16, 'Point', 'NameExpr', 'point'),
      typedSpan(8, 11, 8, 18, 'Float', 'FieldExpr', 'point.x'),
    ])],
    ['/workspace/main.prism', validCheck([
      typedSpan(7, 9, 7, 26, '(left: Point, right: Point) -> Float', 'FieldExpr', 'geometry.distance'),
    ], [
      intrinsicSymbol('elaborate_proof', '/python/prism/language/developer/api.py', 12, 9),
    ])],
    ['/workspace/generated.prism', validCheck([
      typedSpan(0, 0, 0, 4, 'Workflow[Generated[DraftArtifact], ToolError, Tool.Call]', 'Binding', 'flow'),
      typedSpan(0, 7, 0, 25, '(source: Source) -> Workflow[Generated[DraftArtifact], ToolError, Tool.Call]', 'FieldExpr', 'workflows.pipeline'),
    ], [], [{
      span: { line: 0, character: 0, end_line: 0, end_character: 4 },
      token_type: 'variable',
      modifiers: ['declaration'],
    }])],
    ['/workspace/invalid.prism', {
      status: 'invalid',
      type_spans: [],
      diagnostics: [{
        code: 'PrismTypeError',
        severity: 'error',
        message: 'type `Point` has no field `unknown`',
        line: 0,
        character: 0,
        end_line: 0,
        end_character: 21,
      }],
    }],
  ])
  const compiler = fakeCompiler(checks, new Map([
    [definitionKey('/workspace/main.prism', 6, 10), definitionResult(6, 9, '/workspace/lib/geometry.prism', 0, 5)],
    [definitionKey('/workspace/main.prism', 6, 16), definitionResult(6, 15, '/workspace/lib/geometry.prism', 1, 4)],
    [definitionKey('/workspace/main.prism', 7, 20), definitionResult(7, 18, '/workspace/lib/geometry.prism', 4, 4)],
    [definitionKey('/workspace/main.prism', 0, 7), definitionResult(0, 5, '/workspace/lib/geometry.prism', 0, 0)],
    [definitionKey('/workspace/main.prism', 2, 17), definitionResult(2, 4, '/workspace/lib/geometry.prism', 4, 4)],
    [definitionKey('/workspace/main.prism', 8, 8), definitionResult(8, 7, '/workspace/lib/geometry.prism', 4, 4)],
    [definitionKey('/workspace/main.prism', 9, 20), definitionResult(9, 20, '/workspace/lib/geometry.prism', 1, 4)],
    [definitionKey('/workspace/main.prism', 13, 10), definitionResult(13, 7, '/python/prism/language/developer/api.py', 12, 9)],
  ]))
  const registered = {}
  const vscode = fakeVscode(files, documents, (kind, value) => { registered[kind] = value })
  const originalLoad = Module._load
  Module._load = function load(request, parent, isMain) {
    if (request === 'vscode') return vscode
    return originalLoad.call(this, request, parent, isMain)
  }
  try {
    const extensionPath = require.resolve('../src/extension')
    delete require.cache[extensionPath]
    const extension = require(extensionPath)
    extension.activate({ subscriptions: [], prismCompilerService: compiler })
    const provider = registered.definition
    assert.ok(provider)

    const main = documents.get('/workspace/main.prism')
    const token = { isCancellationRequested: false }
    await assertTarget(provider, main, 6, 10, '/workspace/lib/geometry.prism', 0, 5, token) // Point
    await assertTarget(provider, main, 6, 16, '/workspace/lib/geometry.prism', 1, 4, token) // x =
    await assertTarget(provider, main, 7, 20, '/workspace/lib/geometry.prism', 4, 4, token) // geometry.distance
    await assertTarget(provider, main, 0, 7, '/workspace/lib/geometry.prism', 0, 0, token) // module path
    await assertTarget(provider, main, 2, 17, '/workspace/lib/geometry.prism', 4, 4, token) // import alias
    await assertTarget(provider, main, 8, 8, '/workspace/lib/geometry.prism', 4, 4, token) // imported alias use
    await assertTarget(provider, main, 9, 20, '/workspace/lib/geometry.prism', 1, 4, token) // imported value field
    await assertTarget(
      provider,
      main,
      13,
      10,
      '/python/prism/language/developer/api.py',
      12,
      9,
      token,
    ) // compiler intrinsic

    const geometry = documents.get('/workspace/lib/geometry.prism')
    const parameterHover = await registered.hover.provideHover(geometry, { line: 8, character: 12 }, token)
    assert.match(parameterHover.contents.value, /point: Point/)
    const fieldHover = await registered.hover.provideHover(geometry, { line: 8, character: 17 }, token)
    assert.match(fieldHover.contents.value, /point\.x: Float/)
    const importedFunctionHover = await registered.hover.provideHover(main, { line: 7, character: 20 }, token)
    assert.match(importedFunctionHover.contents.value, /geometry\.distance: \(left: Point, right: Point\) -> Float/)
    const workflowHover = await registered.hover.provideHover(generatedDocument, { line: 0, character: 2 }, token)
    assert.match(workflowHover.contents.value, /flow: Workflow\[Generated\[DraftArtifact\], ToolError, Tool.Call\]/)
    const semanticTokens = await registered.semantic.provideDocumentSemanticTokens(generatedDocument, token)
    assert.deepEqual(semanticTokens.items[0], {
      range: new Range(0, 0, 0, 4),
      tokenType: 'variable',
      tokenModifiers: ['declaration'],
    })
    const reasoningDocument = documents.get('/workspace/reasoning.prism')
    const completions = await registered.completion.provideCompletionItems(
      reasoningDocument,
      { line: 2, character: 14 },
      token,
    )
    assert.deepEqual(
      completions.map(item => [item.label, item.kind, item.detail]),
      [
        ['proof_accepted', 2, 'ProofAccepted(proof: Proof[OddSumTheorem])'],
        ['quarantined', 2, 'Quarantined(report: CalibrationReport)'],
      ],
    )

    await new Promise(resolve => setImmediate(resolve))
    const fileDiagnostics = registered.diagnostics.values.get(invalidDocument.uri.toString())
    assert.equal(fileDiagnostics.length, 1)
    assert.equal(fileDiagnostics[0].code, 'PrismTypeError')
    assert.match(fileDiagnostics[0].message, /Point.*unknown/)

    checks.set('/workspace/invalid.prism', validCheck([]))
    registered.save(documents.get('/workspace/lib/geometry.prism'))
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(compiler.invalidations, 1)
    assert.deepEqual(registered.diagnostics.values.get(invalidDocument.uri.toString()), [])
  } finally {
    Module._load = originalLoad
  }
})

function fakeCompiler(checks, definitions) {
  return {
    invalidations: 0,
    async checkDocument(document) {
      return checks.get(document.uri.fsPath) || validCheck([])
    },
    async definitionAt(document, position) {
      return definitions.get(definitionKey(document.uri.fsPath, position.line, position.character))
    },
    async completionAt(document) {
      if (document.uri.fsPath !== '/workspace/reasoning.prism') return []
      return [
        {
          label: 'proof_accepted',
          kind: 'variant',
          detail: 'ProofAccepted(proof: Proof[OddSumTheorem])',
          type_text: 'OddSumProofStatus',
        },
        {
          label: 'quarantined',
          kind: 'variant',
          detail: 'Quarantined(report: CalibrationReport)',
          type_text: 'OddSumProofStatus',
        },
      ]
    },
    invalidate() { this.invalidations += 1 },
    forget() {},
    dispose() {},
  }
}

function definitionKey(file, line, character) {
  return `${file}:${line}:${character}`
}

function definitionResult(originLine, originCharacter, targetPath, targetLine, targetCharacter) {
  return {
    origin: {
      line: originLine,
      character: originCharacter,
      end_line: originLine,
      end_character: originCharacter + 1,
    },
    targets: [{
      definition_path: targetPath,
      span: {
        line: targetLine,
        character: targetCharacter,
        end_line: targetLine,
        end_character: targetCharacter + 1,
      },
    }],
  }
}

function validCheck(typeSpans, symbols = [], semanticTokens = []) {
  return { status: 'valid', type_spans: typeSpans, symbols, semantic_tokens: semanticTokens, diagnostics: [] }
}

function intrinsicSymbol(name, definitionPath, line, character) {
  return {
    name,
    kind: 'Intrinsic',
    span: {
      line,
      character,
      end_line: line,
      end_character: character + name.length,
    },
    detail: '',
    definition_path: definitionPath,
    metadata: {},
  }
}

function typedSpan(line, character, endLine, endCharacter, typeText, kind, name) {
  return {
    span: { line, character, end_line: endLine, end_character: endCharacter },
    type_text: typeText,
    kind,
    name,
  }
}

async function assertTarget(provider, document, line, character, file, targetLine, targetCharacter, token) {
  const links = await provider.provideDefinition(document, { line, character }, token)
  assert.ok(links?.length, `${line}:${character} has a definition`)
  assert.ok(
    links.some(link => link.targetUri.fsPath === file
      && link.targetSelectionRange.start.line === targetLine
      && link.targetSelectionRange.start.character === targetCharacter),
    `${line}:${character} -> ${file}:${targetLine}:${targetCharacter}; got ${links.map(link => `${link.targetUri.fsPath}:${link.targetSelectionRange.start.line}:${link.targetSelectionRange.start.character}`).join(', ')}`,
  )
}

function fakeDocument(file, source) {
  return {
    uri: Uri.file(file),
    languageId: 'prism',
    version: 1,
    getText() { return source },
  }
}

function fakeVscode(files, documents, register) {
  const workspaceFolder = { uri: Uri.file('/workspace') }
  const warning = { count: 0 }
  return {
    FileType: { File: 1 },
    CompletionItem,
    CompletionItemKind: { Field: 1, Method: 2 },
    Diagnostic,
    DiagnosticSeverity: { Error: 0 },
    Hover,
    Location,
    MarkdownString,
    Position,
    Range,
    SemanticTokensBuilder,
    SemanticTokensLegend,
    Uri,
    commands: {
      async executeCommand(command, setting) {
        register('command', { command, setting })
      },
    },
    window: {
      createOutputChannel(name) {
        const output = {
          name,
          lines: [],
          appendLine(line) { this.lines.push(line) },
          show() {},
          dispose() {},
        }
        register('output', output)
        return output
      },
      showWarningMessage(message, ...actions) {
        warning.count += 1
        warning.message = message
        warning.actions = actions
        register('warning', warning)
        return Promise.resolve(undefined)
      },
    },
    languages: {
      registerDefinitionProvider(_selector, provider) {
        register('definition', provider)
        return { dispose() {} }
      },
      registerCompletionItemProvider(_selector, provider) {
        register('completion', provider)
        return { dispose() {} }
      },
      registerHoverProvider(_selector, provider) {
        register('hover', provider)
        return { dispose() {} }
      },
      registerDocumentSemanticTokensProvider(_selector, provider) {
        register('semantic', provider)
        return { dispose() {} }
      },
      createDiagnosticCollection() {
        const values = new Map()
        const collection = {
          values,
          set(uri, diagnostics) { values.set(uri.toString(), diagnostics) },
          delete(uri) { values.delete(uri.toString()) },
          dispose() { values.clear() },
        }
        register('diagnostics', collection)
        return collection
      },
    },
    workspace: {
      textDocuments: [...documents.values()],
      workspaceFolders: [workspaceFolder],
      getConfiguration() {
        return { get(_key, fallback) { return fallback } }
      },
      getWorkspaceFolder(uri) {
        return uri.fsPath.startsWith('/workspace/') ? workspaceFolder : undefined
      },
      async openTextDocument(uri) {
        const document = documents.get(uri.fsPath)
        if (!document) throw new Error(`missing document ${uri.fsPath}`)
        return document
      },
      fs: {
        async stat(uri) {
          if (!files.has(uri.fsPath)) throw new Error('ENOENT')
          return { type: 1 }
        },
      },
      async findFiles() {
        return [...files.keys()].map(Uri.file)
      },
      onDidCloseTextDocument() { return { dispose() {} } },
      onDidOpenTextDocument() { return { dispose() {} } },
      onDidChangeTextDocument() { return { dispose() {} } },
      onDidSaveTextDocument(listener) {
        register('save', listener)
        return { dispose() {} }
      },
      onDidCreateFiles() { return { dispose() {} } },
      onDidDeleteFiles() { return { dispose() {} } },
      onDidRenameFiles() { return { dispose() {} } },
    },
  }
}

class Uri {
  constructor(fsPath) { this.fsPath = fsPath; this.scheme = 'file' }
  static file(file) { return new Uri(file) }
  toString() { return `file://${this.fsPath}` }
}

class Position {
  constructor(line, character) { this.line = line; this.character = character }
}

class Range {
  constructor(startLine, startCharacter, endLine, endCharacter) {
    if (startLine instanceof Position) {
      this.start = startLine
      this.end = startCharacter
    } else {
      this.start = new Position(startLine, startCharacter)
      this.end = new Position(endLine, endCharacter)
    }
  }
}

class Location {
  constructor(uri, rangeOrPosition) {
    this.uri = uri
    this.range = rangeOrPosition instanceof Position
      ? new Range(rangeOrPosition, rangeOrPosition)
      : rangeOrPosition
  }
}

class CompletionItem {
  constructor(label, kind) { this.label = label; this.kind = kind }
}

class MarkdownString {
  constructor() { this.value = '' }
  appendCodeblock(value, language) {
    this.value += `\`\`\`${language}\n${value}\n\`\`\``
    return this
  }
}

class Hover {
  constructor(contents, range) { this.contents = contents; this.range = range }
}

class Diagnostic {
  constructor(range, message, severity) {
    this.range = range
    this.message = message
    this.severity = severity
  }
}

class SemanticTokensLegend {
  constructor(tokenTypes, tokenModifiers) {
    this.tokenTypes = tokenTypes
    this.tokenModifiers = tokenModifiers
  }
}

class SemanticTokensBuilder {
  constructor() { this.items = [] }
  push(range, tokenType, tokenModifiers) {
    this.items.push({ range, tokenType, tokenModifiers })
  }
  build() { return { items: this.items } }
}
