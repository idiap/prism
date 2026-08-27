// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as vscode from 'vscode'

import { PrismIdeCheckResult, PrismIdeRunResult } from '../infoview-api/protocol'
import { PrismLogger } from './logger'
import { PrismSessionClient } from './prismSessionClient'

export interface PrismWorkbenchViewState {
  check?: PrismIdeCheckResult
  run?: PrismIdeRunResult
  runs: PrismIdeRunResult[]
  selectedRunId?: string
  statusMessage?: string
  running: boolean
}

export class PrismWorkbenchState implements vscode.Disposable {
  private readonly onDidChangeEmitter = new vscode.EventEmitter<PrismWorkbenchViewState>()
  readonly onDidChange = this.onDidChangeEmitter.event
  private readonly disposables: vscode.Disposable[] = []
  private refreshTimer?: NodeJS.Timeout
  private check?: PrismIdeCheckResult
  private run?: PrismIdeRunResult
  private runs: PrismIdeRunResult[] = []
  private selectedRunId?: string
  private statusMessage?: string
  private running = false

  constructor(
    private readonly client: PrismSessionClient,
    private readonly logger: PrismLogger,
  ) {
    this.disposables.push(
      vscode.window.onDidChangeActiveTextEditor(() => this.scheduleRefresh('activeEditor')),
      vscode.workspace.onDidOpenTextDocument(document => {
        if (this.isPrismDocument(document)) {
          this.scheduleRefresh('open')
        }
      }),
      vscode.workspace.onDidChangeTextDocument(event => {
        if (this.isPrismDocument(event.document)) {
          this.scheduleRefresh('change')
        }
      }),
      vscode.workspace.onDidSaveTextDocument(document => {
        if (this.isPrismDocument(document)) {
          this.scheduleRefresh('save')
        }
      }),
    )
  }

  dispose() {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
    }
    for (const disposable of this.disposables) {
      disposable.dispose()
    }
    this.onDidChangeEmitter.dispose()
  }

  getViewState(): PrismWorkbenchViewState {
    return {
      check: this.check,
      run: this.run,
      runs: this.runs,
      selectedRunId: this.selectedRunId,
      statusMessage: this.statusMessage,
      running: this.running,
    }
  }

  scheduleRefresh(reason: string) {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
    }
    this.refreshTimer = setTimeout(() => {
      void this.refresh(reason)
    }, 150)
  }

  async refresh(reason: string): Promise<void> {
    const context = this.currentPrismEditorContext()
    if (!context) {
      this.check = undefined
      this.run = undefined
      this.runs = []
      this.selectedRunId = undefined
      this.statusMessage = 'Open a .prism document.'
      this.fireChange()
      return
    }
    try {
      this.check = await this.client.checkDocument(
        context.workspaceFolder,
        context.document.uri.fsPath,
        context.document.getText(),
      )
      this.runs = await this.runsForContext(context)
      this.run = this.selectedRunFrom(this.runs)
      this.statusMessage = this.check.status === 'valid'
        ? (this.run?.message || this.checkedStatusMessage())
        : 'Syntax or type errors found.'
      this.logger.debug('state.check', 'Checked PRISM document.', {
        reason,
        status: this.check.status,
        diagnostics: this.check.diagnostics.length,
        selectedRun: this.run?.run_id,
        runs: this.runs.length,
      })
    } catch (error) {
      this.run = undefined
      this.runs = []
      this.selectedRunId = undefined
      this.statusMessage = 'PRISM type checking failed. Open the debug log for details.'
      this.logger.error('state.checkFailed', 'PRISM type checking failed.', { error: this.describeError(error) })
    }
    this.fireChange()
  }

  async runCurrentDocument(model?: string): Promise<void> {
    const context = this.currentPrismEditorContext()
    if (!context) {
      vscode.window.showInformationMessage('Open a .prism document to run it.')
      return
    }
    this.running = true
    this.statusMessage = model ? `Running with ${model}...` : 'Running with fake material runner...'
    this.fireChange()
    try {
      this.run = await vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: model ? `PRISM: running with ${model}` : 'PRISM: running',
          cancellable: false,
        },
        () => this.client.runDocument(
          context.workspaceFolder,
          context.document.uri.fsPath,
          context.document.getText(),
          model ? 'litellm' : 'fake',
          model,
        ),
      )
      const completedRun = this.run
      this.selectedRunId = completedRun.run_id ?? undefined
      this.runs = await this.runsForContext(context)
      this.run = this.selectedRunFrom(this.runs) ?? completedRun
      this.statusMessage = completedRun.message
      this.logger.info('state.run', 'PRISM run finished.', {
        status: completedRun.status,
        model,
        outputStatus: completedRun.output?.status,
        runPath: completedRun.run_path,
      })
    } catch (error) {
      this.statusMessage = 'PRISM run failed. Open the debug log for details.'
      this.logger.error('state.runFailed', 'PRISM run failed.', { error: this.describeError(error) })
    } finally {
      this.running = false
      this.fireChange()
    }
  }

  clearRun() {
    this.run = undefined
    this.selectedRunId = undefined
    this.fireChange()
  }

  async selectRun(runId: string): Promise<void> {
    this.selectedRunId = runId
    const selected = this.runs.find(run => run.run_id === runId)
    if (selected) {
      this.run = selected
      this.fireChange()
      return
    }
    await this.refresh('command:selectRun')
  }

  async deleteRun(runId: string): Promise<void> {
    const context = this.currentPrismEditorContext()
    if (!context) {
      return
    }
    const run = this.runs.find(candidate => candidate.run_id === runId)
    const label = run?.run_created_at || runId
    const pick = await vscode.window.showWarningMessage(
      `Delete PRISM run ${label}?`,
      { modal: true },
      'Delete',
    )
    if (pick !== 'Delete') {
      return
    }
    try {
      const deleted = await this.client.deleteRunForDocument(
        context.workspaceFolder,
        context.document.uri.fsPath,
        runId,
      )
      if (!deleted) {
        vscode.window.showInformationMessage('PRISM run was not found.')
      }
      if (this.selectedRunId === runId) {
        this.selectedRunId = undefined
      }
      await this.refresh('command:deleteRun')
    } catch (error) {
      this.logger.error('state.deleteRunFailed', 'Could not delete persisted PRISM run.', {
        runId,
        error: this.describeError(error),
      })
      vscode.window.showErrorMessage('Could not delete PRISM run. Open the debug log for details.')
    }
  }

  private currentPrismEditorContext(): { document: vscode.TextDocument; workspaceFolder: vscode.WorkspaceFolder } | undefined {
    const editor = vscode.window.activeTextEditor
    if (!editor || !this.isPrismDocument(editor.document)) {
      return undefined
    }
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(editor.document.uri) || vscode.workspace.workspaceFolders?.[0]
    if (!workspaceFolder) {
      return undefined
    }
    return { document: editor.document, workspaceFolder }
  }

  private async runsForContext(context: {
    document: vscode.TextDocument
    workspaceFolder: vscode.WorkspaceFolder
  }): Promise<PrismIdeRunResult[]> {
    try {
      return await this.client.runsForDocument(context.workspaceFolder, context.document.uri.fsPath)
    } catch (error) {
      this.logger.warn('state.runsFailed', 'Could not load persisted PRISM runs.', {
        error: this.describeError(error),
      })
      return []
    }
  }

  private selectedRunFrom(runs: PrismIdeRunResult[]): PrismIdeRunResult | undefined {
    if (!runs.length) {
      this.selectedRunId = undefined
      return undefined
    }
    const selected = this.selectedRunId
      ? runs.find(run => run.run_id === this.selectedRunId)
      : undefined
    const run = selected ?? runs[0]
    this.selectedRunId = run.run_id ?? undefined
    return run
  }

  private checkedStatusMessage(): string {
    return 'Type check passed.'
  }

  private isPrismDocument(document?: vscode.TextDocument): boolean {
    if (!document) {
      return false
    }
    return document.languageId === 'prism' || document.uri.fsPath.toLowerCase().endsWith('.prism')
  }

  private describeError(error: unknown): string {
    return error instanceof Error ? error.stack || error.message : String(error)
  }

  private fireChange() {
    this.onDidChangeEmitter.fire(this.getViewState())
  }
}
