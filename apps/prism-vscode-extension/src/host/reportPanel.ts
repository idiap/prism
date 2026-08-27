// SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
// SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
//
// SPDX-License-Identifier: MIT

import * as vscode from 'vscode'

import {
  PrismIdeDiagnostic,
  PrismIdeRunResult,
  PrismInferenceOutput,
  PrismTraceEventOutput,
} from '../infoview-api/protocol'
import { PrismLogger } from './logger'
import { PrismWorkbenchViewState } from './state'

interface PrismReportPanelActions {
  selectRun(runId: string): void | Thenable<void> | Promise<void>
  deleteRun(runId: string): void | Thenable<void> | Promise<void>
  refresh(): void | Thenable<void> | Promise<void>
}

export class PrismReportPanelProvider implements vscode.WebviewViewProvider, vscode.Disposable {
  private view?: vscode.WebviewView
  private state?: PrismWorkbenchViewState
  private readonly disposables: vscode.Disposable[] = []

  constructor(
    private readonly logger: PrismLogger,
    private readonly actions: PrismReportPanelActions,
  ) {}

  resolveWebviewView(webviewView: vscode.WebviewView) {
    this.view = webviewView
    webviewView.webview.options = {
      enableScripts: true,
    }
    this.disposables.push(
      webviewView.webview.onDidReceiveMessage(message => {
        void this.handleMessage(message)
      }),
    )
    this.render()
  }

  refresh(state: PrismWorkbenchViewState) {
    this.state = state
    this.render()
  }

  dispose() {
    for (const disposable of this.disposables) {
      disposable.dispose()
    }
  }

  private async handleMessage(message: unknown): Promise<void> {
    if (!this.isRecord(message)) {
      return
    }
    const type = this.stringField(message, 'type')
    const runId = this.stringField(message, 'runId')
    try {
      if (type === 'selectRun' && runId) {
        await this.actions.selectRun(runId)
        return
      }
      if (type === 'deleteRun' && runId) {
        await this.actions.deleteRun(runId)
        return
      }
      if (type === 'refresh') {
        await this.actions.refresh()
      }
    } catch (error) {
      this.logger.error('reportPanel.messageFailed', 'Report Panel action failed.', {
        type,
        runId,
        error: error instanceof Error ? error.message : String(error),
      })
      vscode.window.showErrorMessage('PRISM Report action failed. Open the debug log for details.')
    }
  }

  private render() {
    if (!this.view) {
      return
    }
    this.view.webview.html = this.html(this.state)
  }

  private html(state?: PrismWorkbenchViewState): string {
    const nonce = this.nonce()
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
  <title>PRISM Report</title>
  <style nonce="${nonce}">
    :root {
      color-scheme: light dark;
      --panel-border: var(--vscode-panel-border, rgba(127, 127, 127, 0.35));
      --muted: var(--vscode-descriptionForeground);
      --accent: var(--vscode-focusBorder);
      --soft-bg: var(--vscode-editorWidget-background);
      --strong-bg: var(--vscode-sideBar-background);
      --code-bg: var(--vscode-textCodeBlock-background);
      --accepted: var(--vscode-testing-iconPassed);
      --rejected: var(--vscode-testing-iconFailed);
      --blocked: var(--vscode-testing-iconQueued);
      --undetermined: var(--vscode-testing-iconUnset);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      padding: 0;
      background: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
      line-height: 1.45;
    }

    button {
      font: inherit;
    }

    main {
      display: flex;
      flex-direction: column;
      gap: 14px;
      padding: 14px;
      min-width: 0;
    }

    h1, h2, h3, h4, p {
      margin: 0;
    }

    h1 {
      font-size: 18px;
      font-weight: 650;
    }

    h2 {
      font-size: 15px;
      font-weight: 650;
    }

    h3 {
      font-size: 13px;
      font-weight: 650;
    }

    h4 {
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    .topbar,
    .section,
    .run-manager,
    details.node,
    .empty {
      border: 1px solid var(--panel-border);
      border-radius: 6px;
      background: var(--strong-bg);
    }

    .topbar {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 12px;
    }

    .title-stack {
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;
    }

    .subtitle,
    .muted {
      color: var(--muted);
    }

    .subtitle {
      overflow-wrap: anywhere;
    }

    .toolbar {
      display: flex;
      gap: 8px;
      flex: 0 0 auto;
    }

    .small-button,
    .run-button,
    .delete-button {
      border: 1px solid var(--vscode-button-border, transparent);
      border-radius: 4px;
      cursor: pointer;
    }

    .small-button {
      padding: 4px 8px;
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }

    .small-button:hover,
    .run-item:hover {
      filter: brightness(1.08);
    }

    .run-manager {
      min-width: 0;
    }

    .run-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .run-item {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 32px;
      gap: 0;
      align-items: stretch;
      overflow: hidden;
      border: 1px solid var(--vscode-button-border, transparent);
      border-radius: 4px;
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }

    .run-button {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 3px;
      min-width: 0;
      border: 0;
      border-radius: 0;
      padding: 8px;
      background: transparent;
      color: inherit;
      text-align: left;
    }

    .run-item.selected {
      border-color: var(--accent);
      background: var(--vscode-list-activeSelectionBackground);
      color: var(--vscode-list-activeSelectionForeground);
    }

    .run-label,
    .summary-text,
    .statement,
    .reason-text,
    .pre-wrap {
      overflow-wrap: anywhere;
      word-break: normal;
    }

    .delete-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 32px;
      border: 0;
      border-radius: 0;
      padding: 0;
      background: transparent;
      color: inherit;
    }

    .delete-button:hover {
      background: var(--vscode-toolbar-hoverBackground);
      color: var(--vscode-inputValidation-errorForeground);
    }

    .delete-button svg {
      width: 16px;
      height: 16px;
      stroke: currentColor;
    }

    .section {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 12px;
    }

    .meta-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
    }

    .io-grid {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }

    .meta-item,
    .io-block,
    .highlight,
    .reason-card,
    .kv-table,
    .json-block {
      border: 1px solid var(--panel-border);
      border-radius: 5px;
      background: var(--soft-bg);
    }

    .meta-item,
    .io-block,
    .highlight,
    .reason-card {
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 9px;
      min-width: 0;
    }

    .highlight {
      border-left: 3px solid var(--accent);
      background: color-mix(in srgb, var(--soft-bg) 88%, var(--accent));
    }

    .label {
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      text-transform: uppercase;
    }

    .statement {
      font-size: 14px;
      font-weight: 620;
    }

    .summary-line {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      min-width: 0;
    }

    .summary-text {
      color: var(--muted);
      flex-basis: 100%;
      min-width: 0;
    }

    details.node {
      overflow: hidden;
    }

    details.node > summary {
      display: grid;
      grid-template-columns: 16px minmax(0, 1fr);
      gap: 7px;
      align-items: start;
      cursor: pointer;
      list-style: none;
      padding: 10px 12px;
    }

    details.node > summary::-webkit-details-marker {
      display: none;
    }

    .chevron {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      margin-top: 2px;
      color: var(--muted);
    }

    .chevron svg {
      width: 14px;
      height: 14px;
      stroke: currentColor;
    }

    .chevron-open {
      display: none;
    }

    details.node[open] > summary .chevron-closed {
      display: none;
    }

    details.node[open] > summary .chevron-open {
      display: inline-flex;
    }

    .summary-content {
      min-width: 0;
    }

    details.node > .node-body {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 0 12px 12px;
    }

    .node-stack {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .depth-1 {
      margin-left: 10px;
    }

    .depth-2 {
      margin-left: 20px;
    }

    .depth-3,
    .depth-4,
    .depth-5 {
      margin-left: 30px;
    }

    .status {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--panel-border);
      border-radius: 999px;
      padding: 1px 7px;
      font-size: 11px;
      font-weight: 650;
      line-height: 1.6;
    }

    .status.accepted {
      border-color: var(--accepted);
      color: var(--accepted);
    }

    .status.rejected {
      border-color: var(--rejected);
      color: var(--rejected);
    }

    .status.blocked {
      border-color: var(--blocked);
      color: var(--blocked);
    }

    .status.undetermined {
      border-color: var(--undetermined);
      color: var(--undetermined);
    }

    .ref,
    .pill,
    code {
      border-radius: 4px;
      background: var(--code-bg);
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
    }

    .ref,
    .pill {
      display: inline-flex;
      max-width: 100%;
      padding: 1px 5px;
      overflow-wrap: anywhere;
    }

    .pill-list {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      min-width: 0;
    }

    .judgment {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 0;
    }

    .operator {
      align-self: flex-start;
      border-radius: 4px;
      padding: 1px 5px;
      background: var(--vscode-badge-background);
      color: var(--vscode-badge-foreground);
      font-family: var(--vscode-editor-font-family);
    }

    .reason-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .reason-meta {
      color: var(--muted);
      font-size: 12px;
    }

    .kv-table {
      display: grid;
      grid-template-columns: minmax(96px, 0.35fr) minmax(0, 1fr);
      overflow: hidden;
    }

    .kv-key,
    .kv-value {
      padding: 7px 8px;
      border-bottom: 1px solid var(--panel-border);
    }

    .kv-key {
      color: var(--muted);
      background: var(--soft-bg);
      font-weight: 600;
      overflow-wrap: anywhere;
    }

    .kv-value {
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .kv-key:last-of-type,
    .kv-value:last-of-type {
      border-bottom: 0;
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .json-block {
      padding: 9px;
      overflow: auto;
      background: var(--code-bg);
      font-family: var(--vscode-editor-font-family);
      font-size: 12px;
    }

    .empty {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 18px;
    }

    @media (max-width: 360px) {
      main {
        padding: 10px;
      }

      .topbar {
        flex-direction: column;
      }

      .toolbar {
        width: 100%;
      }

      .small-button {
        flex: 1;
      }

      .run-item {
        grid-template-columns: minmax(0, 1fr);
      }

      .delete-button {
        min-height: 28px;
      }

    }
  </style>
</head>
<body>
  ${this.renderBody(state)}
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    document.addEventListener('click', event => {
      const button = event.target.closest('button[data-action]');
      if (!button) {
        return;
      }
      const type = button.dataset.action;
      const runId = button.dataset.runId;
      vscode.postMessage({ type, runId });
    });
  </script>
</body>
</html>`
  }

  private renderBody(state?: PrismWorkbenchViewState): string {
    if (!state?.run) {
      return `<main>
  <section class="empty">
    <h1>Report</h1>
    <p class="muted">${this.escapeHtml(state?.statusMessage || 'Run a .prism file to populate the Report panel.')}</p>
    <div class="toolbar">
      <button class="small-button" data-action="refresh">Refresh</button>
    </div>
  </section>
</main>`
    }

    const run = state.run
    return `<main>
  ${this.renderTopbar(run, state)}
  ${this.renderRunManager(state.runs, run, state.selectedRunId)}
  ${this.renderRunDiagnostics(run.diagnostics)}
  ${run.output ? this.renderOutput(run.output) : this.renderNoOutput(run)}
</main>`
  }

  private renderTopbar(run: PrismIdeRunResult, state: PrismWorkbenchViewState): string {
    const status = state.running ? 'Running...' : (state.statusMessage || run.message || 'PRISM report')
    return `<section class="topbar">
  <div class="title-stack">
    <h1>Report</h1>
    <p class="subtitle">${this.escapeHtml(status)}</p>
  </div>
  <div class="toolbar">
    <button class="small-button" data-action="refresh">Refresh</button>
  </div>
</section>`
  }

  private renderRunManager(runs: PrismIdeRunResult[], selectedRun: PrismIdeRunResult, selectedRunId?: string): string {
    if (runs.length <= 1) {
      return ''
    }
    const selectedId = selectedRunId || selectedRun.run_id
    const items = runs.map(run => {
      const selected = Boolean(run.run_id && run.run_id === selectedId)
      const runIdAttribute = run.run_id ? ` data-run-id="${this.escapeAttribute(run.run_id)}"` : ''
      const disabled = run.run_id ? '' : ' disabled'
      const deleteButton = run.run_id
        ? `<button class="delete-button" data-action="deleteRun" data-run-id="${this.escapeAttribute(run.run_id)}" title="Remove this persisted run" aria-label="Remove this persisted run">${this.trashIcon()}</button>`
        : ''
      return `<li class="run-item${selected ? ' selected' : ''}">
  <button class="run-button" data-action="selectRun"${runIdAttribute}${disabled}>
    <span class="run-label">${this.escapeHtml(this.runLabel(run))}</span>
    <span class="muted">${this.escapeHtml(this.runDescription(run, selected))}</span>
  </button>
  ${deleteButton}
</li>`
    }).join('')
    return `<details class="node run-manager" aria-label="Persisted PRISM runs" open>
  <summary>
    ${this.chevronIcons()}
    <span class="summary-content summary-line">
      <h2>Runs</h2>
      <span class="muted">${runs.length} persisted runs</span>
    </span>
  </summary>
  <div class="node-body">
    <ul class="run-list">${items}</ul>
  </div>
</details>`
  }

  private renderOutput(output: PrismInferenceOutput): string {
    return `${this.renderReasoningLog(output.trace)}
${this.renderOutputDiagnostics(output.diagnostics)}`
  }

  private renderReasoningLog(events: PrismTraceEventOutput[]): string {
    const steps = events.filter(event => (
      event.kind === 'workflow-node'
      && this.stringField(event.metadata, 'method_type') !== undefined
    ))
    if (!steps.length) {
      return ''
    }
    const reasoning = this.stringField(steps[0].metadata, 'reasoning')
      || events.find(event => event.kind === 'reasoning-started')?.name
    const reasoningLabel = reasoning?.split('.').pop()
    return `<section class="section" aria-label="Reasoning log">
  <div class="summary-line">
    <h2>Reasoning Log</h2>
    ${reasoningLabel ? `<span class="muted">${this.escapeHtml(reasoningLabel)}</span>` : ''}
    <span class="muted">${steps.length} steps</span>
  </div>
  <div class="node-stack">
    ${steps.map((step, index) => this.renderReasoningStep(
      step,
      index,
      index === steps.length - 1,
    )).join('')}
  </div>
</section>`
  }

  private renderReasoningStep(
    event: PrismTraceEventOutput,
    index: number,
    isFinalStep: boolean,
  ): string {
    const outputType = this.stringField(event.metadata, 'output_type')
    const hasResult = Object.prototype.hasOwnProperty.call(event.metadata, 'result')
    return `<details class="node reasoning-step">
  <summary>
    ${this.chevronIcons()}
    <span class="summary-content summary-line">
      <span class="ref">Step ${index + 1}</span>
      <span>${this.escapeHtml(event.name)}</span>
      ${this.statusBadge(isFinalStep || event.status !== 'accepted' ? event.status : undefined)}
      ${outputType ? `<span class="summary-text">${this.escapeHtml(outputType)}</span>` : ''}
    </span>
  </summary>
  <div class="node-body">
    <span class="label">Result</span>
    ${hasResult
      ? this.renderValue(event.metadata.result)
      : '<span class="muted">No result was recorded for this step.</span>'}
  </div>
</details>`
  }

  private renderRunDiagnostics(diagnostics: PrismIdeDiagnostic[]): string {
    if (!diagnostics.length) {
      return ''
    }
    return `<section class="section">
  <div class="summary-line">
    <h2>Run diagnostics</h2>
    <span class="muted">${diagnostics.length}</span>
  </div>
  ${diagnostics.map(diagnostic => `<div class="io-block">
    <div class="summary-line">
      <span class="status ${this.statusClass(diagnostic.severity)}">${this.escapeHtml(diagnostic.severity)}</span>
      <span class="ref">${this.escapeHtml(diagnostic.code)}</span>
    </div>
    <div class="statement">${this.escapeHtml(diagnostic.message)}</div>
    ${diagnostic.line_text ? `<pre class="pre-wrap muted">${this.escapeHtml(diagnostic.line_text)}</pre>` : ''}
  </div>`).join('')}
</section>`
  }

  private renderOutputDiagnostics(diagnostics: unknown[] | undefined | null): string {
    const items = this.arrayField(diagnostics)
    if (!items.length) {
      return ''
    }
    return `<section class="section">
  <div class="summary-line">
    <h2>Output diagnostics</h2>
    <span class="muted">${items.length}</span>
  </div>
  ${items.map(item => this.renderValue(item)).join('')}
</section>`
  }

  private renderNoOutput(run: PrismIdeRunResult): string {
    return `<section class="empty">
  <h2>No output</h2>
  <p class="muted">${this.escapeHtml(run.message || 'This run did not produce PRISM output.')}</p>
</section>`
  }

  private renderValue(value: unknown): string {
    if (typeof value === 'string') {
      return `<pre class="json-block">${this.escapeHtml(value)}</pre>`
    }
    if (value === null || value === undefined) {
      return '<span class="muted">None</span>'
    }
    if (typeof value === 'number' || typeof value === 'boolean') {
      return `<span>${this.escapeHtml(String(value))}</span>`
    }
    return `<pre class="json-block">${this.escapeHtml(this.stringifyValue(value))}</pre>`
  }

  private statusBadge(status: string | undefined | null): string {
    if (!status) {
      return ''
    }
    return `<span class="status ${this.statusClass(status)}">${this.escapeHtml(status)}</span>`
  }

  private statusClass(status: string): string {
    switch (status) {
      case 'accepted':
      case 'completed':
        return 'accepted'
      case 'rejected':
      case 'failed':
      case 'error':
        return 'rejected'
      case 'blocked':
      case 'warning':
        return 'blocked'
      default:
        return 'undetermined'
    }
  }

  private runLabel(run: PrismIdeRunResult): string {
    return run.run_created_at || run.run_id || 'Persisted run'
  }

  private runDescription(run: PrismIdeRunResult, selected: boolean): string {
    const backend = run.model ? `${run.backend} ${run.model}` : run.backend
    return selected ? `${backend} selected` : `${backend} ${run.status}`
  }

  private trashIcon(): string {
    return `<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
  <path d="M3 6h18"></path>
  <path d="M8 6V4h8v2"></path>
  <path d="M19 6l-1 14H6L5 6"></path>
  <path d="M10 11v5"></path>
  <path d="M14 11v5"></path>
</svg>`
  }

  private chevronIcons(): string {
    return `<span class="chevron chevron-closed" aria-hidden="true">${this.chevronRightIcon()}</span><span class="chevron chevron-open" aria-hidden="true">${this.chevronDownIcon()}</span>`
  }

  private chevronRightIcon(): string {
    return `<svg viewBox="0 0 16 16" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false">
  <path d="M6 4l4 4-4 4"></path>
</svg>`
  }

  private chevronDownIcon(): string {
    return `<svg viewBox="0 0 16 16" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false">
  <path d="M4 6l4 4 4-4"></path>
</svg>`
  }

  private arrayField<T>(value: T[] | undefined | null): T[] {
    return Array.isArray(value) ? value : []
  }

  private stringifyValue(value: unknown): string {
    try {
      return JSON.stringify(value, null, 2) ?? String(value)
    } catch {
      return String(value)
    }
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value)
  }

  private stringField(value: Record<string, unknown>, key: string): string | undefined {
    const field = value[key]
    return typeof field === 'string' && field.length > 0 ? field : undefined
  }

  private escapeHtml(value: unknown): string {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  private escapeAttribute(value: unknown): string {
    return this.escapeHtml(value)
  }

  private nonce(): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let value = ''
    for (let index = 0; index < 32; index += 1) {
      value += chars.charAt(Math.floor(Math.random() * chars.length))
    }
    return value
  }
}
