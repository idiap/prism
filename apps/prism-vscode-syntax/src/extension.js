// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

'use strict'

const vscode = require('vscode')
const { CompilerServiceClient } = require('./compiler-service')

/** @param {vscode.ExtensionContext} context */
function activate(context) {
  const selector = { language: 'prism' }
  const diagnostics = vscode.languages.createDiagnosticCollection('prism-syntax')
  const output = vscode.window.createOutputChannel('PRISM Language Support')
  const compiler = context.prismCompilerService || new CompilerServiceClient(vscode)
  const diagnosticRefreshes = new Map()
  let lastBackendError
  const reportBackendError = error => {
    const message = error instanceof Error ? error.message : String(error)
    output.appendLine(`[${new Date().toISOString()}] ${message}`)
    if (message === lastBackendError) return
    lastBackendError = message
    void vscode.window.showWarningMessage(
      'PRISM language features could not start. Select the Python interpreter from the Prism toolchain environment.',
      'Set Python Path',
      'Show Log',
    ).then(async choice => {
      if (choice === 'Set Python Path') {
        await vscode.commands.executeCommand('workbench.action.openSettings', 'prism.languageServer.pythonPath')
      } else if (choice === 'Show Log') {
        output.show(true)
      }
    })
  }
  const noteBackendSuccess = () => { lastBackendError = undefined }
  const definitionProvider = vscode.languages.registerDefinitionProvider(selector, {
    async provideDefinition(document, position, token) {
      if (token.isCancellationRequested) return undefined
      let result
      try {
        result = await compiler.definitionAt(document, position)
      } catch (error) {
        reportBackendError(error)
        return undefined
      }
      noteBackendSuccess()
      if (token.isCancellationRequested || !result?.targets?.length) return undefined
      const origin = rangeForProtocolSpan(result.origin)
      return result.targets.map(target => ({
        originSelectionRange: origin,
        targetUri: vscode.Uri.file(target.definition_path),
        targetRange: rangeForProtocolSpan(target.span),
        targetSelectionRange: rangeForProtocolSpan(target.span),
      }))
    },
  })
  const hoverProvider = vscode.languages.registerHoverProvider(selector, {
    async provideHover(document, position, token) {
      if (token.isCancellationRequested) return undefined
      let check
      try {
        check = await compiler.checkDocument(document)
      } catch (error) {
        reportBackendError(error)
        return undefined
      }
      noteBackendSuccess()
      if (token.isCancellationRequested || check?.status !== 'valid') return undefined
      const typed = typeSpanAtPosition(check.type_spans || [], position)
      if (!typed) return undefined
      const signature = typed.name
        ? `${typed.name}: ${typed.type_text}`
        : typed.type_text
      const markdown = new vscode.MarkdownString()
      markdown.appendCodeblock(signature, 'prism')
      return new vscode.Hover(markdown, rangeForProtocolSpan(typed.span))
    },
  })
  const completionProvider = vscode.languages.registerCompletionItemProvider(selector, {
    async provideCompletionItems(document, position, token) {
      if (token.isCancellationRequested) return undefined
      let items
      try {
        items = await compiler.completionAt(document, position)
      } catch (error) {
        reportBackendError(error)
        return undefined
      }
      noteBackendSuccess()
      if (token.isCancellationRequested) return undefined
      return (items || []).map(item => {
        const kind = item.kind === 'variant'
          ? vscode.CompletionItemKind.Method
          : vscode.CompletionItemKind.Field
        const completion = new vscode.CompletionItem(item.label, kind)
        completion.detail = item.detail || item.type_text
        return completion
      })
    },
  }, '.')
  const semanticTokensProvider = registerSemanticTokensProvider(
    selector,
    compiler,
    reportBackendError,
    noteBackendSuccess,
  )

  const refreshDiagnostics = async document => {
    if (!isPrismDocument(document)) return
    const key = document.uri.toString()
    const refresh = (diagnosticRefreshes.get(key) || 0) + 1
    diagnosticRefreshes.set(key, refresh)
    const version = document.version
    let check
    try {
      check = await compiler.checkDocument(document)
    } catch (error) {
      reportBackendError(error)
      return
    }
    noteBackendSuccess()
    if (document.version !== version || diagnosticRefreshes.get(key) !== refresh) return
    diagnostics.set(document.uri, (check?.diagnostics || []).map(issue => {
      const diagnostic = new vscode.Diagnostic(
        diagnosticRange(document, issue),
        issue.message,
        diagnosticSeverity(issue.severity),
      )
      diagnostic.code = issue.code
      diagnostic.source = 'Prism'
      return diagnostic
    }))
  }

  const refreshWorkspaceDiagnostics = () => {
    compiler.invalidate?.()
    for (const document of vscode.workspace.textDocuments) void refreshDiagnostics(document)
  }

  context.subscriptions.push(
    definitionProvider,
    hoverProvider,
    completionProvider,
    ...(semanticTokensProvider ? [semanticTokensProvider] : []),
    diagnostics,
    output,
    compiler,
    vscode.workspace.onDidOpenTextDocument(refreshDiagnostics),
    vscode.workspace.onDidChangeTextDocument(event => { void refreshDiagnostics(event.document) }),
    vscode.workspace.onDidSaveTextDocument(document => {
      if (isPrismDocument(document)) refreshWorkspaceDiagnostics()
    }),
    vscode.workspace.onDidCreateFiles(event => {
      if (event.files.some(isPrismUri)) refreshWorkspaceDiagnostics()
    }),
    vscode.workspace.onDidDeleteFiles(event => {
      if (event.files.some(isPrismUri)) refreshWorkspaceDiagnostics()
    }),
    vscode.workspace.onDidRenameFiles(event => {
      if (event.files.some(file => isPrismUri(file.oldUri) || isPrismUri(file.newUri))) {
        refreshWorkspaceDiagnostics()
      }
    }),
    vscode.workspace.onDidCloseTextDocument(document => {
      compiler.forget?.(document)
      diagnosticRefreshes.delete(document.uri.toString())
      diagnostics.delete(document.uri)
    }),
  )
  for (const document of vscode.workspace.textDocuments) void refreshDiagnostics(document)
}

function registerSemanticTokensProvider(selector, compiler, reportBackendError, noteBackendSuccess) {
  if (!vscode.languages.registerDocumentSemanticTokensProvider) return undefined
  const tokenTypes = ['keyword', 'function', 'type', 'parameter', 'variable', 'property', 'label', 'operator']
  const tokenModifiers = ['declaration']
  const legend = new vscode.SemanticTokensLegend(tokenTypes, tokenModifiers)
  return vscode.languages.registerDocumentSemanticTokensProvider(selector, {
    async provideDocumentSemanticTokens(document, token) {
      if (token.isCancellationRequested) return undefined
      let check
      try {
        check = await compiler.checkDocument(document)
      } catch (error) {
        reportBackendError(error)
        return undefined
      }
      noteBackendSuccess()
      if (token.isCancellationRequested || check?.status !== 'valid') return undefined
      const builder = new vscode.SemanticTokensBuilder(legend)
      for (const item of check.semantic_tokens || []) {
        builder.push(rangeForProtocolSpan(item.span), item.token_type, item.modifiers || [])
      }
      return builder.build()
    },
  }, legend)
}

function deactivate() {
}

function isPrismDocument(document) {
  return document.languageId === 'prism'
    || isPrismUri(document.uri)
}

function isPrismUri(uri) {
  return uri.scheme === 'file' && uri.fsPath.toLowerCase().endsWith('.prism')
}

function typeSpanAtPosition(typeSpans, position) {
  return typeSpans
    .filter(item => positionInProtocolSpan(position, item.span))
    .sort((left, right) => protocolSpanSize(left.span) - protocolSpanSize(right.span))[0]
}

function positionInProtocolSpan(position, span) {
  const endLine = span.end_line ?? span.line
  const endCharacter = span.end_character ?? span.character + 1
  if (position.line < span.line || position.line > endLine) return false
  if (position.line === span.line && position.character < span.character) return false
  return position.line !== endLine || position.character < endCharacter
}

function protocolSpanSize(span) {
  const endLine = span.end_line ?? span.line
  const endCharacter = span.end_character ?? span.character + 1
  return (endLine - span.line) * 1000000 + Math.max(1, endCharacter - span.character)
}

function rangeForProtocolSpan(span) {
  return new vscode.Range(
    span.line,
    span.character,
    span.end_line ?? span.line,
    span.end_character ?? span.character + 1,
  )
}

function diagnosticRange(document, diagnostic) {
  const lines = document.getText().split(/\r?\n/)
  const line = Math.max(0, Math.min(diagnostic.line ?? 0, lines.length - 1))
  const endLine = Math.max(line, Math.min(diagnostic.end_line ?? line, lines.length - 1))
  const character = Math.max(0, Math.min(diagnostic.character ?? 0, lines[line]?.length ?? 0))
  const endCharacter = Math.max(
    character,
    Math.min(diagnostic.end_character ?? character + 1, lines[endLine]?.length ?? character + 1),
  )
  return new vscode.Range(line, character, endLine, endCharacter)
}

function diagnosticSeverity(severity) {
  if (severity === 'warning') return vscode.DiagnosticSeverity.Warning
  if (severity === 'info') return vscode.DiagnosticSeverity.Information
  return vscode.DiagnosticSeverity.Error
}

module.exports = { activate, deactivate }
