// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as vscode from 'vscode'

import { PrismLogger } from './logger'
import { PrismSessionClient } from './prismSessionClient'
import { PrismReportPanelProvider } from './reportPanel'
import { PrismWorkbenchState } from './state'
import { PrismRunTreeProvider } from './treeProvider'

export async function activate(context: vscode.ExtensionContext) {
  const logger = new PrismLogger(vscode.window.createOutputChannel('PRISM Solver Debug'))
  const client = new PrismSessionClient(logger)
  const state = new PrismWorkbenchState(client, logger)
  const runPanel = new PrismRunTreeProvider()
  const reportPanel = new PrismReportPanelProvider(logger, {
    selectRun: runId => state.selectRun(runId),
    deleteRun: runId => state.deleteRun(runId),
    refresh: () => state.refresh('reportPanel.refresh'),
  })
  let availabilityChecked = false

  context.subscriptions.push(logger, client, state)

  const treeView = vscode.window.createTreeView('prism.runPanel', {
    treeDataProvider: runPanel,
    showCollapseAll: true,
  })
  context.subscriptions.push(treeView, reportPanel)
  context.subscriptions.push(vscode.window.registerWebviewViewProvider('prism.reportPanel', reportPanel))

  state.onDidChange(viewState => {
    runPanel.refresh(viewState.run, viewState.runs, viewState.selectedRunId, viewState.statusMessage)
    reportPanel.refresh(viewState)
    treeView.message = viewState.running ? 'Running...' : viewState.statusMessage
  })

  const ensurePrismAvailable = async (reason: string) => {
    if (availabilityChecked) {
      return
    }
    const folder = vscode.workspace.workspaceFolders?.[0]
    if (!folder) {
      return
    }
    availabilityChecked = true
    const availability = await client.checkAvailability(folder)
    if (availability.status === 'ok') {
      return
    }
    if (availability.status === 'python-missing') {
      const pick = await vscode.window.showWarningMessage(
        `PRISM could not find a Python interpreter at "${availability.pythonPath}".`,
        'Set Python Path',
      )
      if (pick === 'Set Python Path') {
        await vscode.commands.executeCommand('workbench.action.openSettings', 'prismSolver.pythonPath')
      }
      return
    }
    logger.warn('extension.prismMissing', 'PRISM is not importable for the selected interpreter.', {
      reason,
      detail: availability.detail,
    })
    const pick = await vscode.window.showWarningMessage(
      'PRISM is not importable for the selected Python interpreter.',
      'Set Python Path',
    )
    if (pick === 'Set Python Path') {
      await vscode.commands.executeCommand('workbench.action.openSettings', 'prismSolver.pythonPath')
    }
  }

  const onPrismDocumentDetected = (document?: vscode.TextDocument, reason = 'prismDocument') => {
    if (!isPrismDocument(document)) {
      return
    }
    void ensurePrismAvailable(reason)
    state.scheduleRefresh(reason)
  }

  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor(editor => onPrismDocumentDetected(editor?.document, 'activeEditor')),
    vscode.workspace.onDidOpenTextDocument(document => onPrismDocumentDetected(document, 'openDocument')),
    vscode.workspace.onDidChangeConfiguration(event => {
      if (event.affectsConfiguration('prismSolver.logging')) {
        logger.refreshConfiguration()
      }
    }),
    vscode.commands.registerCommand('prismSolver.openRunPanel', async () => {
      await vscode.commands.executeCommand('workbench.view.extension.prism')
      await vscode.commands.executeCommand('prism.runPanel.focus')
      state.scheduleRefresh('command:openRunPanel')
    }),
    vscode.commands.registerCommand('prismSolver.openReportPanel', async () => {
      await vscode.commands.executeCommand('workbench.view.extension.prism')
      await vscode.commands.executeCommand('prism.reportPanel.focus')
      state.scheduleRefresh('command:openReportPanel')
    }),
    vscode.commands.registerCommand('prismSolver.refreshRunPanel', async () => {
      await state.refresh('command:refreshRunPanel')
    }),
    vscode.commands.registerCommand('prismSolver.runCurrentDocumentWithModel', async () => {
      const model = await pickExecutionModel()
      if (!model) {
        return
      }
      await vscode.commands.executeCommand('workbench.view.extension.prism')
      await state.runCurrentDocument(model)
    }),
    vscode.commands.registerCommand('prismSolver.clearRunPanel', () => {
      state.clearRun()
    }),
    vscode.commands.registerCommand('prismSolver.selectRun', async (runId: unknown) => {
      const resolvedRunId = runIdFromCommandArgument(runId)
      if (resolvedRunId) {
        await state.selectRun(resolvedRunId)
      }
    }),
    vscode.commands.registerCommand('prismSolver.deleteRun', async (run: unknown) => {
      const runId = runIdFromCommandArgument(run)
      if (runId) {
        await state.deleteRun(runId)
      }
    }),
    vscode.commands.registerCommand('prismSolver.showDebugLog', () => {
      logger.show(true)
    }),
  )

  logger.info('extension.activate', 'PRISM Run Explorer extension activated.')
  state.scheduleRefresh('activate')
  onPrismDocumentDetected(vscode.window.activeTextEditor?.document, 'activate')
}

export function deactivate() {}

async function pickExecutionModel(): Promise<string | undefined> {
  const models = vscode.workspace
    .getConfiguration('prismSolver')
    .get<string[]>('execution.models', [])
    .map(model => model.trim())
    .filter(model => model.length > 0)
  if (models.length === 0) {
    const pick = await vscode.window.showInformationMessage(
      'No PRISM LiteLLM models are configured. Add model identifiers to "prismSolver.execution.models".',
      'Configure Models',
    )
    if (pick === 'Configure Models') {
      await vscode.commands.executeCommand('workbench.action.openSettings', 'prismSolver.execution.models')
    }
    return undefined
  }
  return vscode.window.showQuickPick(models, {
    placeHolder: 'Select a LiteLLM model for this PRISM run',
  })
}

function isPrismDocument(document?: vscode.TextDocument): boolean {
  if (!document) {
    return false
  }
  return document.languageId === 'prism' || (document.uri.scheme === 'file' && document.uri.fsPath.toLowerCase().endsWith('.prism'))
}

function runIdFromCommandArgument(value: unknown): string | undefined {
  if (typeof value === 'string' && value.length > 0) {
    return value
  }
  if (typeof value !== 'object' || value === null) {
    return undefined
  }
  const run = (value as { run?: { run_id?: unknown } }).run
  return typeof run?.run_id === 'string' && run.run_id.length > 0 ? run.run_id : undefined
}
